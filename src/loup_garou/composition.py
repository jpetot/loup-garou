import random
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from loup_garou.roles import Camp, Catalogue, Niveau, Role

JOUEURS_MIN = 5
JOUEURS_MAX = 30
FAMILIARITE_MIN = -5
FAMILIARITE_MAX = 5
ID_VILLAGEOIS = "villageois"
ID_LOUP = "loup-garou"
ID_CUPIDON = "cupidon"
ID_ANGE = "ange"
ID_LOUP_BLANC = "loup-blanc"
ROLES_DE_BASE = frozenset({ID_VILLAGEOIS, ID_LOUP})

PENALITE_PAR_LOUP_SUPPLEMENTAIRE = -2
PART_VILLAGE_MIN = 2 / 3
LOUPS_MIN_AVEC_CUPIDON = 3
AUTRES_LOUPS_MIN_AVEC_LOUP_BLANC = 2
PALIERS_CAMPS_SOLO = ((16, 2), (12, 1))
COMBINAISONS_INTERDITES = ((ID_CUPIDON, ID_ANGE),)


class Experience(StrEnum):
    DEBUTANT = "debutant"
    CONFIRME = "confirme"
    EXPERT = "expert"


PART_ROLES_SPECIAUX = {
    Experience.DEBUTANT: 0.35,
    Experience.CONFIRME: 0.55,
    Experience.EXPERT: 0.75,
}
CIBLE_PAR_EXPERIENCE = {
    Experience.DEBUTANT: 2.0,
    Experience.CONFIRME: 0.0,
    Experience.EXPERT: -2.0,
}
MARGE_PART_ROLES_SPECIAUX = 0.25
POIDS_TIRAGE = {Niveau.CLASSIQUE: 3.0, Niveau.AVANCE: 1.0, Niveau.EXPERT: 1.0}
NIVEAUX_PERMIS = {
    Experience.DEBUTANT: {Niveau.CLASSIQUE},
    Experience.CONFIRME: {Niveau.CLASSIQUE, Niveau.AVANCE},
    Experience.EXPERT: {Niveau.CLASSIQUE, Niveau.AVANCE, Niveau.EXPERT},
}


@dataclass(frozen=True)
class Reglages:
    joueurs: int
    experience: Experience
    familiarite: int

    def __post_init__(self) -> None:
        if not JOUEURS_MIN <= self.joueurs <= JOUEURS_MAX:
            raise ValueError(f"Le nombre de joueurs doit être entre {JOUEURS_MIN} et {JOUEURS_MAX}")
        if not FAMILIARITE_MIN <= self.familiarite <= FAMILIARITE_MAX:
            raise ValueError(
                f"La familiarité doit être entre {FAMILIARITE_MIN} et {FAMILIARITE_MAX}"
            )

    @property
    def cible(self) -> float:
        return CIBLE_PAR_EXPERIENCE[self.experience]


def camps_solo_autorises(joueurs: int) -> int:
    return next((n for seuil, n in PALIERS_CAMPS_SOLO if joueurs >= seuil), 0)


def penalite_meute(nombre_de_loups: int) -> float:
    return PENALITE_PAR_LOUP_SUPPLEMENTAIRE * max(0, nombre_de_loups - 1)


@dataclass(frozen=True)
class Composition:
    cartes: tuple[Role, ...]
    reglages: Reglages

    @property
    def ids(self) -> list[str]:
        return [r.id for r in self.cartes]

    @property
    def nombre_de_loups(self) -> int:
        return sum(r.compte_comme_loup for r in self.cartes)

    @property
    def poids_des_roles(self) -> float:
        return sum(r.poids for r in self.cartes)

    @property
    def penalite_meute(self) -> float:
        return penalite_meute(self.nombre_de_loups)

    @property
    def score(self) -> float:
        return self.poids_des_roles + self.penalite_meute + self.reglages.familiarite

    @property
    def ecart(self) -> float:
        return self.score - self.reglages.cible

    def decompte(self) -> list[tuple[Role, int]]:
        compte = Counter(self.ids)
        uniques = {r.id: r for r in self.cartes}
        ordre_camps = list(Camp)
        return sorted(
            ((uniques[i], n) for i, n in compte.items()),
            key=lambda paire: (ordre_camps.index(paire[0].camp), paire[0].nom),
        )

    def avertissements(self) -> list[str]:
        joueurs = self.reglages.joueurs
        ids = set(self.ids)
        n_cartes = len(self.cartes)
        n_loups = self.nombre_de_loups
        messages = []
        if n_cartes != joueurs:
            messages.append(f"{n_cartes} cartes pour {joueurs} joueurs.")
        for role, n in self.decompte():
            if role.unique and n > 1:
                messages.append(f"{role.nom} est un rôle unique ({n} cartes).")
            if role.groupe > 1 and n % role.groupe:
                messages.append(f"{role.nom} se joue par {role.groupe}.")
        if n_loups == 0:
            messages.append("Aucun loup-garou.")
        n_village = sum(r.camp == Camp.VILLAGE for r in self.cartes)
        if n_cartes and n_village < PART_VILLAGE_MIN * n_cartes:
            messages.append("Moins de 2/3 des rôles sont dans le camp du village.")
        n_simples = self.ids.count(ID_VILLAGEOIS)
        if n_simples < n_loups:
            messages.append(f"Moins de simples villageois ({n_simples}) que de loups ({n_loups}).")
        n_solos = sum(r.ajoute_un_camp_solo for r in self.cartes)
        if n_solos > camps_solo_autorises(joueurs):
            messages.append(
                f"{n_solos} camp(s) solo pour {joueurs} joueurs : "
                "1 dès 12 joueurs, 2 dès 16 (Cupidon compte pour un)."
            )
        if ID_CUPIDON in ids and n_loups < LOUPS_MIN_AVEC_CUPIDON:
            messages.append(f"Cupidon demande au moins {LOUPS_MIN_AVEC_CUPIDON} loups.")
        if ID_LOUP_BLANC in ids and n_loups - 1 < AUTRES_LOUPS_MIN_AVEC_LOUP_BLANC:
            messages.append(
                "Le loup-garou blanc demande au moins "
                f"{AUTRES_LOUPS_MIN_AVEC_LOUP_BLANC} autres loups."
            )
        noms = {r.id: r.nom for r in self.cartes}
        for a, b in COMBINAISONS_INTERDITES:
            if a in ids and b in ids:
                messages.append(f"Combinaison déconseillée : {noms[a]} et {noms[b]}.")
        return messages


def plage_de_loups(joueurs: int) -> tuple[int, int]:
    return max(1, round(joueurs / 5)), max(1, joueurs // 3)


def composition_depuis_ids(catalogue: Catalogue, ids: list[str], reglages: Reglages) -> Composition:
    roles = [catalogue.get(i) for i in ids]
    return Composition(cartes=tuple(r for r in roles if r is not None), reglages=reglages)


def _ordre_pondere(roles: list[Role], rng: random.Random) -> list[Role]:
    return sorted(roles, key=lambda r: rng.random() ** (1 / POIDS_TIRAGE[r.niveau]), reverse=True)


@dataclass(frozen=True)
class Contraintes:
    imposes: frozenset[str] = frozenset()
    exclus: frozenset[str] = frozenset()

    @classmethod
    def depuis(cls, imposes: list[str] | None, exclus: list[str] | None) -> Contraintes:
        return cls(
            frozenset(imposes or ()) - ROLES_DE_BASE, frozenset(exclus or ()) - ROLES_DE_BASE
        )

    def imposer(self, role_id: str) -> Contraintes:
        if role_id in ROLES_DE_BASE:
            return self
        return Contraintes(self.imposes | {role_id}, self.exclus - {role_id})

    def exclure(self, role_id: str) -> Contraintes:
        if role_id in ROLES_DE_BASE:
            return self
        return Contraintes(self.imposes - {role_id}, self.exclus | {role_id})

    def liberer(self, role_id: str) -> Contraintes:
        return Contraintes(self.imposes - {role_id}, self.exclus - {role_id})


@dataclass(frozen=True)
class _Pioche:
    reglages: Reglages
    villageois: Role
    loup: Role
    imposes: tuple[Role, ...]
    loups_speciaux: tuple[Role, ...]
    speciaux: tuple[Role, ...]


def _tirer(pioche: _Pioche, rng: random.Random) -> list[Role]:
    joueurs = pioche.reglages.joueurs
    cartes_imposees = [r for r in pioche.imposes for _ in range(r.groupe)]
    loups_imposes = [r for r in cartes_imposees if r.camp == Camp.LOUPS]
    autres_imposes = [r for r in cartes_imposees if r.camp != Camp.LOUPS]

    n_loups = max(rng.randint(*plage_de_loups(joueurs)), len(loups_imposes))
    cartes = loups_imposes + [pioche.loup] * (n_loups - len(loups_imposes))
    if not loups_imposes and pioche.loups_speciaux and rng.random() < 0.4:
        cartes[0] = rng.choice(pioche.loups_speciaux)
    cartes.extend(autres_imposes)

    places = joueurs - n_loups
    part = PART_ROLES_SPECIAUX[pioche.reglages.experience] + rng.uniform(
        -0.1, MARGE_PART_ROLES_SPECIAUX
    )
    pris = len(autres_imposes)
    objectif = max(pris, min(round(places * part), places - n_loups))
    for role in _ordre_pondere(list(pioche.speciaux), rng):
        if pris + role.groupe <= objectif:
            cartes.extend([role] * role.groupe)
            pris += role.groupe
    cartes.extend([pioche.villageois] * max(0, joueurs - len(cartes)))
    return cartes


def generer(
    catalogue: Catalogue,
    reglages: Reglages,
    graine: int,
    contraintes: Contraintes = Contraintes(),
    essais: int = 600,
) -> Composition:
    villageois = catalogue.get(ID_VILLAGEOIS)
    loup = catalogue.get(ID_LOUP)
    if villageois is None or loup is None:
        raise ValueError("Le catalogue doit contenir le simple villageois et le loup-garou")

    imposes = [r for i in sorted(contraintes.imposes) if (r := catalogue.get(i)) is not None]
    ids_imposes = {r.id for r in imposes}
    permis = [
        r
        for r in catalogue.filtrer()
        if r.cartes_supplementaires == 0
        and r.niveau in NIVEAUX_PERMIS[reglages.experience]
        and r.id not in ROLES_DE_BASE | contraintes.exclus | ids_imposes
    ]
    imposes += [r for r in permis if r.essentiel]
    pioche = _Pioche(
        reglages=reglages,
        villageois=villageois,
        loup=loup,
        imposes=tuple(imposes),
        loups_speciaux=tuple(r for r in permis if r.camp == Camp.LOUPS),
        speciaux=tuple(r for r in permis if r.camp != Camp.LOUPS and not r.essentiel),
    )

    rng = random.Random(graine)
    meilleure: Composition | None = None
    meilleure_cle: tuple[int, float] | None = None
    for _ in range(essais):
        candidate = Composition(cartes=tuple(_tirer(pioche, rng)), reglages=reglages)
        cle = (len(candidate.avertissements()), abs(candidate.ecart))
        if meilleure_cle is None or cle < meilleure_cle:
            meilleure, meilleure_cle = candidate, cle
    assert meilleure is not None
    return meilleure
