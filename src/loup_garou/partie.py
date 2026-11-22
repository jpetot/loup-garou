import random
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Session, col, select

from loup_garou.composition import ID_LOUP, Reglages
from loup_garou.db import Evenement, Participation, Partie, Personne
from loup_garou.roles import Catalogue, Role

MARQUEURS_COMMUNS = {
    "amoureux": "❤️",
    "protégé": "🛡️",
    "charmé": "🎵",
    "muet": "🤐",
    "marqué": "🐦",
    "devenu loup": "🐺",
    "neutralisé": "🚫",
    "modèle": "👤",
}
MARQUEURS_DE_LA_NUIT = frozenset({"protégé", "muet", "marqué"})
MARQUEUR_AMOUREUX = "amoureux"
MARQUEUR_DEVENU_LOUP = "devenu loup"
MARQUEUR_NEUTRALISE = "neutralisé"
TAILLE_DU_JOURNAL = 50


class Phase(StrEnum):
    NUIT = "nuit"
    JOUR = "jour"


class Statut(StrEnum):
    PREPARATION = "preparation"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"


class Gagnant(StrEnum):
    VILLAGE = "village"
    LOUPS = "loups"
    SOLITAIRE = "solitaire"
    AMOUREUX = "amoureux"


class ErreurPartie(ValueError):
    pass


@dataclass(frozen=True)
class Joueur:
    participation: Participation
    nom: str
    role: Role

    @property
    def id(self) -> int:
        assert self.participation.id is not None
        return self.participation.id

    @property
    def vivant(self) -> bool:
        return self.participation.vivant

    @property
    def marqueurs(self) -> list[str]:
        return self.participation.marqueurs

    @property
    def est_loup(self) -> bool:
        return self.role.compte_comme_loup or MARQUEUR_DEVENU_LOUP in self.marqueurs


@dataclass(frozen=True)
class Appel:
    titre: str
    role: Role
    joueurs: list[Joueur]

    @property
    def tous_morts(self) -> bool:
        return not any(j.vivant for j in self.joueurs)

    @property
    def pouvoir_perdu(self) -> bool:
        return all(MARQUEUR_NEUTRALISE in j.marqueurs for j in self.joueurs)


def creer_partie(session: Session, reglages: Reglages, cartes: list[str]) -> Partie:
    if len(cartes) != reglages.joueurs:
        raise ErreurPartie(f"{len(cartes)} cartes pour {reglages.joueurs} joueurs")
    partie = Partie(
        joueurs=reglages.joueurs,
        experience=reglages.experience,
        familiarite=reglages.familiarite,
        cartes=list(cartes),
    )
    session.add(partie)
    session.commit()
    session.refresh(partie)
    return partie


def attribuer_au_hasard(cartes: list[str], rng: random.Random) -> list[str]:
    roles = list(cartes)
    rng.shuffle(roles)
    return roles


def _personne(session: Session, nom: str) -> Personne:
    personne = session.exec(select(Personne).where(Personne.nom == nom)).first()
    if personne is None:
        personne = Personne(nom=nom)
        session.add(personne)
        session.flush()
    return personne


def demarrer(session: Session, partie: Partie, noms: list[str], roles: list[str]) -> None:
    noms = [n.strip() for n in noms]
    if len(noms) != partie.joueurs or any(not n for n in noms):
        raise ErreurPartie(f"Il faut le nom des {partie.joueurs} joueurs.")
    doublons = {n for n in noms if [m.casefold() for m in noms].count(n.casefold()) > 1}
    if doublons:
        raise ErreurPartie(f"Noms en double : {', '.join(sorted(doublons))}.")
    if Counter(roles) != Counter(partie.cartes):
        raise ErreurPartie("Les rôles attribués ne correspondent pas à la composition.")
    for place, (nom, role_id) in enumerate(zip(noms, roles, strict=True), start=1):
        personne = _personne(session, nom)
        assert personne.id is not None and partie.id is not None
        session.add(
            Participation(
                partie_id=partie.id, personne_id=personne.id, place=place, role_id=role_id
            )
        )
    partie.statut = Statut.EN_COURS
    session.add(partie)
    _journaliser(session, partie, "La partie commence.")
    session.commit()


def noms_connus(session: Session) -> list[str]:
    return list(session.exec(select(Personne.nom).order_by(Personne.nom)))


def joueurs(session: Session, partie: Partie, catalogue: Catalogue) -> list[Joueur]:
    lignes = session.exec(
        select(Participation, Personne)
        .join(Personne, col(Participation.personne_id) == col(Personne.id))
        .where(Participation.partie_id == partie.id)
        .order_by(col(Participation.place))
    )
    resultat = []
    for participation, personne in lignes:
        role = catalogue.get(participation.role_id)
        if role is None:
            raise ErreurPartie(f"Rôle inconnu : {participation.role_id}")
        resultat.append(Joueur(participation=participation, nom=personne.nom, role=role))
    return resultat


def appels_de_la_nuit(numero: int, liste: list[Joueur], catalogue: Catalogue) -> list[Appel]:
    par_role: dict[str, list[Joueur]] = {}
    for joueur in liste:
        par_role.setdefault(joueur.role.id, []).append(joueur)

    appels = []
    loup = catalogue.get(ID_LOUP)
    loups = [j for j in liste if j.est_loup]
    if loup is not None and loups and loup.appele_la_nuit(numero):
        appels.append(Appel(titre="Loups-garous", role=loup, joueurs=loups))
    for role_id, porteurs in par_role.items():
        role = porteurs[0].role
        if role_id != ID_LOUP and role.appele_la_nuit(numero):
            appels.append(Appel(titre=role.nom, role=role, joueurs=porteurs))
    return sorted(appels, key=lambda a: a.role.ordre_nuit or 0)


def rappels(liste: list[Joueur]) -> list[str]:
    messages = []
    amoureux = [j for j in liste if MARQUEUR_AMOUREUX in j.marqueurs]
    morts = [j for j in amoureux if not j.vivant]
    vivants = [j for j in amoureux if j.vivant]
    if morts and vivants:
        noms = ", ".join(j.nom for j in vivants)
        messages.append(f"{morts[0].nom} est mort : {noms} meurt de chagrin.")
    return messages


def _journaliser(session: Session, partie: Partie, texte: str) -> None:
    assert partie.id is not None
    session.add(
        Evenement(partie_id=partie.id, numero=partie.numero, phase=partie.phase, texte=texte)
    )


def journal(session: Session, partie: Partie) -> list[Evenement]:
    return list(
        session.exec(
            select(Evenement)
            .where(Evenement.partie_id == partie.id)
            .order_by(col(Evenement.id).desc())
            .limit(TAILLE_DU_JOURNAL)
        )
    )


def _verifier_en_cours(partie: Partie) -> None:
    if partie.statut != Statut.EN_COURS:
        raise ErreurPartie("La partie n'est pas en cours.")


def basculer_vivant(session: Session, partie: Partie, joueur: Joueur) -> str | None:
    _verifier_en_cours(partie)
    participation = joueur.participation
    participation.vivant = not participation.vivant
    session.add(participation)
    if participation.vivant:
        _journaliser(session, partie, f"{joueur.nom} ({joueur.role.nom}) revient en jeu.")
        rappel = None
    else:
        _journaliser(session, partie, f"{joueur.nom} ({joueur.role.nom}) meurt.")
        rappel = f"{joueur.nom} : {joueur.role.a_la_mort}" if joueur.role.a_la_mort else None
    session.commit()
    return rappel


def basculer_marqueur(session: Session, partie: Partie, joueur: Joueur, marqueur: str) -> None:
    _verifier_en_cours(partie)
    if marqueur not in MARQUEURS_COMMUNS and marqueur not in joueur.role.marqueurs:
        raise ErreurPartie(f"Marqueur inconnu : {marqueur}")
    participation = joueur.participation
    if marqueur in participation.marqueurs:
        participation.marqueurs = [m for m in participation.marqueurs if m != marqueur]
        _journaliser(session, partie, f"{joueur.nom} : {marqueur} retiré.")
    else:
        participation.marqueurs = [*participation.marqueurs, marqueur]
        _journaliser(session, partie, f"{joueur.nom} : {marqueur}.")
    session.add(participation)
    session.commit()


def noter(session: Session, joueur: Joueur, texte: str) -> None:
    joueur.participation.notes = texte
    session.add(joueur.participation)
    session.commit()


def ajouter_au_journal(session: Session, partie: Partie, texte: str) -> None:
    if texte.strip():
        _journaliser(session, partie, texte.strip())
        session.commit()


def changer_de_phase(session: Session, partie: Partie, liste: list[Joueur]) -> None:
    _verifier_en_cours(partie)
    if partie.phase == Phase.NUIT:
        partie.phase = Phase.JOUR
    else:
        partie.phase = Phase.NUIT
        partie.numero += 1
        for joueur in liste:
            restants = [m for m in joueur.marqueurs if m not in MARQUEURS_DE_LA_NUIT]
            if restants != joueur.marqueurs:
                joueur.participation.marqueurs = restants
                session.add(joueur.participation)
    session.add(partie)
    _journaliser(session, partie, f"Début : {partie.phase} {partie.numero}.")
    session.commit()


def terminer(session: Session, partie: Partie, gagnant: Gagnant) -> None:
    _verifier_en_cours(partie)
    partie.statut = Statut.TERMINEE
    partie.gagnant = gagnant
    partie.termine_le = datetime.now(UTC)
    session.add(partie)
    _journaliser(session, partie, f"Fin de la partie : victoire {gagnant}.")
    session.commit()
