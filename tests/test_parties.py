import random
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from loup_garou import partie as jeu
from loup_garou.app import creer_app
from loup_garou.composition import Experience, Reglages
from loup_garou.db import creer_moteur
from loup_garou.roles import catalogue_par_defaut

CATALOGUE = catalogue_par_defaut()
CARTES = ["loup-garou", "loup-garou", "voyante", "sorciere", "cupidon", "chasseur", "villageois"]
NOMS = ["Alice", "Bruno", "Chloé", "David", "Emma", "Fanny", "Gaël"]


@pytest.fixture
def session(tmp_path: Path):
    with Session(creer_moteur(f"sqlite:///{tmp_path / 'test.db'}")) as s:
        yield s


def partie_demarree(session: Session):
    partie = jeu.creer_partie(session, Reglages(7, Experience.CONFIRME, 0), CARTES)
    jeu.demarrer(session, partie, NOMS, CARTES)
    return partie, {j.nom: j for j in jeu.joueurs(session, partie, CATALOGUE)}


def test_demarrer_enregistre_les_joueurs(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    assert partie.statut == jeu.Statut.EN_COURS
    assert joueurs["Alice"].role.id == "loup-garou"
    assert jeu.noms_connus(session) == sorted(NOMS)


@pytest.mark.parametrize(
    ("noms", "roles", "message"),
    [
        (NOMS[:-1] + [""], CARTES, "nom des 7"),
        (NOMS[:-1] + ["alice"], CARTES, "double"),
        (NOMS, CARTES[:-1] + ["voyante"], "ne correspondent pas"),
    ],
)
def test_demarrer_refuse_une_preparation_invalide(
    session: Session, noms: list[str], roles: list[str], message: str
) -> None:
    partie = jeu.creer_partie(session, Reglages(7, Experience.CONFIRME, 0), CARTES)
    with pytest.raises(jeu.ErreurPartie, match=message):
        jeu.demarrer(session, partie, noms, roles)


def test_attribuer_au_hasard_garde_les_cartes() -> None:
    assert sorted(jeu.attribuer_au_hasard(CARTES, random.Random(1))) == sorted(CARTES)


def test_appels_de_la_premiere_nuit_puis_de_la_deuxieme(session: Session) -> None:
    _, joueurs = partie_demarree(session)
    liste = list(joueurs.values())
    nuit1 = [a.titre for a in jeu.appels_de_la_nuit(1, liste, CATALOGUE)]
    assert nuit1 == ["Cupidon", "Voyante", "Loups-garous", "Sorcière"]
    nuit2 = [a.titre for a in jeu.appels_de_la_nuit(2, liste, CATALOGUE)]
    assert "Cupidon" not in nuit2
    loups = jeu.appels_de_la_nuit(1, liste, CATALOGUE)[2]
    assert [j.nom for j in loups.joueurs] == ["Alice", "Bruno"]


def test_un_joueur_devenu_loup_est_appele_avec_les_loups(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    jeu.basculer_marqueur(session, partie, joueurs["Gaël"], "devenu loup")
    liste = jeu.joueurs(session, partie, CATALOGUE)
    loups = next(a for a in jeu.appels_de_la_nuit(2, liste, CATALOGUE) if a.titre == "Loups-garous")
    assert "Gaël" in [j.nom for j in loups.joueurs]


def test_loup_blanc_appele_les_nuits_paires(session: Session) -> None:
    cartes = ["loup-garou", "loup-garou", "loup-blanc", "voyante", "villageois"]
    partie = jeu.creer_partie(session, Reglages(5, Experience.EXPERT, 0), cartes)
    jeu.demarrer(session, partie, NOMS[:5], cartes)
    liste = jeu.joueurs(session, partie, CATALOGUE)
    titres = lambda n: [a.titre for a in jeu.appels_de_la_nuit(n, liste, CATALOGUE)]  # noqa: E731
    assert "Loup-garou blanc" not in titres(1)
    assert "Loup-garou blanc" in titres(2)


def test_mort_du_chasseur_donne_un_rappel(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    rappel = jeu.basculer_vivant(session, partie, joueurs["Fanny"])
    assert rappel is not None and "tire" in rappel
    assert not jeu.joueurs(session, partie, CATALOGUE)[5].vivant


def test_mort_d_un_amoureux_rappelle_le_chagrin(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    jeu.basculer_marqueur(session, partie, joueurs["Chloé"], "amoureux")
    jeu.basculer_marqueur(session, partie, joueurs["Gaël"], "amoureux")
    jeu.basculer_vivant(session, partie, joueurs["Chloé"])
    rappels = jeu.rappels(jeu.joueurs(session, partie, CATALOGUE))
    assert rappels == ["Chloé est mort : Gaël meurt de chagrin."]


def test_marqueur_inconnu_refuse(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    with pytest.raises(jeu.ErreurPartie):
        jeu.basculer_marqueur(session, partie, joueurs["Alice"], "potion de vie utilisée")
    jeu.basculer_marqueur(session, partie, joueurs["David"], "potion de vie utilisée")


def test_nouvelle_nuit_efface_les_marqueurs_de_la_nuit(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    jeu.basculer_marqueur(session, partie, joueurs["Emma"], "protégé")
    jeu.basculer_marqueur(session, partie, joueurs["Emma"], "amoureux")
    liste = jeu.joueurs(session, partie, CATALOGUE)
    jeu.changer_de_phase(session, partie, liste)
    assert (partie.phase, partie.numero) == ("jour", 1)
    assert "protégé" in jeu.joueurs(session, partie, CATALOGUE)[4].marqueurs
    jeu.changer_de_phase(session, partie, jeu.joueurs(session, partie, CATALOGUE))
    assert (partie.phase, partie.numero) == ("nuit", 2)
    assert jeu.joueurs(session, partie, CATALOGUE)[4].marqueurs == ["amoureux"]


def test_terminer_bloque_les_actions(session: Session) -> None:
    partie, joueurs = partie_demarree(session)
    jeu.terminer(session, partie, jeu.Gagnant.VILLAGE)
    assert partie.gagnant == "village"
    with pytest.raises(jeu.ErreurPartie):
        jeu.basculer_vivant(session, partie, joueurs["Alice"])
    assert jeu.journal(session, partie)[0].texte.startswith("Fin de la partie")


def test_parcours_complet_dans_l_app(tmp_path: Path) -> None:
    client = TestClient(creer_app(f"sqlite:///{tmp_path / 'app.db'}"))
    reglages = {"joueurs": "7", "experience": "confirme", "familiarite": "0"}
    creation = client.post("/parties", data=reglages | {"roles": CARTES}, follow_redirects=False)
    assert creation.status_code == 303
    preparation = creation.headers["location"]

    hasard = client.post(preparation, data={"noms": NOMS, "action": "hasard"})
    roles = re.findall(r'<option value="([^"]+)" selected>', hasard.text)
    assert sorted(roles) == sorted(CARTES)

    erreur = client.post(preparation, data={"noms": NOMS[:6], "roles": roles})
    assert erreur.status_code == 422

    demarrage = client.post(preparation, data={"noms": NOMS, "roles": roles})
    assert "Nuit 1" in demarrage.text
    assert "Ordre d" in demarrage.text

    partie_url = preparation.removesuffix("/preparation")
    jour = client.post(f"{partie_url}/phase")
    assert "Jour 1" in jour.text
    fin = client.post(f"{partie_url}/terminer", data={"gagnant": "loups"})
    assert "Partie terminée" in fin.text
    assert "Loups-garous" in client.get("/parties").text
