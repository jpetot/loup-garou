import pytest

from loup_garou.roles import Camp, Niveau, catalogue_par_defaut, charger_roles

ROLE_MINIMAL = """
- id: {id}
  nom: Test
  camp: village
  extension: base
  niveau: classique
  unique: true
  poids_min: {pmin}
  poids_max: {pmax}
  pouvoir: Aucun
"""


def test_catalogue_par_defaut_se_charge() -> None:
    catalogue = catalogue_par_defaut()
    assert len(catalogue) >= 25
    loup = catalogue.get("loup-garou")
    assert loup is not None
    assert loup.camp == Camp.LOUPS
    assert loup.poids < 0


def test_poids_min_superieur_au_max_refuse() -> None:
    with pytest.raises(ValueError, match="poids_min > poids_max"):
        charger_roles(ROLE_MINIMAL.format(id="x", pmin=3, pmax=1))


def test_identifiants_en_double_refuses() -> None:
    yaml = ROLE_MINIMAL.format(id="x", pmin=1, pmax=1) * 2
    with pytest.raises(ValueError, match="double"):
        charger_roles(yaml)


def test_filtrer_par_camp_niveau_et_texte() -> None:
    catalogue = catalogue_par_defaut()
    loups = catalogue.filtrer(camp=Camp.LOUPS)
    assert loups and all(r.camp == Camp.LOUPS for r in loups)
    classiques = catalogue.filtrer(niveau=Niveau.CLASSIQUE)
    assert all(r.niveau == Niveau.CLASSIQUE for r in classiques)
    assert [r.id for r in catalogue.filtrer(recherche="POTION")] == ["sorciere"]


def test_ordre_de_nuit_trie_et_sans_roles_passifs() -> None:
    ordre = catalogue_par_defaut().ordre_de_nuit()
    valeurs = [r.ordre_nuit for r in ordre]
    assert valeurs == sorted(v for v in valeurs if v is not None)
    assert "chasseur" not in {r.id for r in ordre}
