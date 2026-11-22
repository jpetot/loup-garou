import pytest

from loup_garou.composition import (
    Contraintes,
    Experience,
    Reglages,
    camps_solo_autorises,
    composition_depuis_ids,
    generer,
    penalite_meute,
)
from loup_garou.roles import Camp, Niveau, catalogue_par_defaut

CATALOGUE = catalogue_par_defaut()
CONFIRMES = Reglages(10, Experience.CONFIRME, 0)
TOUS_LES_REGLAGES = [
    Reglages(j, e, f) for j in (5, 8, 12, 16, 22, 30) for e in Experience for f in (-5, 0, 5)
]


def compo(ids: list[str], reglages: Reglages = CONFIRMES):
    return composition_depuis_ids(CATALOGUE, ids, reglages)


@pytest.mark.parametrize("reglages", TOUS_LES_REGLAGES, ids=str)
def test_composition_generee_respecte_les_regles(reglages: Reglages) -> None:
    composition = generer(CATALOGUE, reglages, graine=42)
    assert len(composition.cartes) == reglages.joueurs
    assert composition.avertissements() == []
    assert all(r.cartes_supplementaires == 0 for r in composition.cartes)
    assert "voyante" in composition.ids


@pytest.mark.parametrize("joueurs", [10, 12, 15, 20])
@pytest.mark.parametrize("experience", list(Experience))
def test_composition_generee_equilibree(joueurs: int, experience: Experience) -> None:
    composition = generer(CATALOGUE, Reglages(joueurs, experience, 0), graine=1)
    assert abs(composition.ecart) <= 1


@pytest.mark.parametrize("joueurs", [8, 12, 20])
def test_debutants_ne_recoivent_que_des_roles_classiques(joueurs: int) -> None:
    reglages = Reglages(joueurs, Experience.DEBUTANT, 0)
    for graine in range(10):
        composition = generer(CATALOGUE, reglages, graine=graine)
        assert all(r.niveau == Niveau.CLASSIQUE for r in composition.cartes)


def test_meme_graine_meme_composition() -> None:
    assert generer(CATALOGUE, CONFIRMES, 7).ids == generer(CATALOGUE, CONFIRMES, 7).ids


def test_penalite_de_meute_du_memo() -> None:
    assert [penalite_meute(n) for n in (1, 2, 3)] == [0, -2, -4]
    assert compo(["loup-garou"] * 3).poids_des_roles + penalite_meute(3) == -22


def test_score_ajoute_meute_et_familiarite() -> None:
    reglages = Reglages(10, Experience.CONFIRME, 3)
    composition = compo(["loup-garou", "loup-garou", "voyante", "villageois"], reglages)
    assert composition.score == (-12 + 9 + 1) - 2 + 3


def test_cible_selon_experience() -> None:
    cibles = [Reglages(10, e, 0).cible for e in Experience]
    assert cibles == sorted(cibles, reverse=True)
    assert Reglages(10, Experience.CONFIRME, 0).cible == 0


def test_loup_blanc_compte_comme_loup_mais_reste_solitaire() -> None:
    loup_blanc = CATALOGUE.get("loup-blanc")
    assert loup_blanc is not None
    assert loup_blanc.compte_comme_loup
    assert loup_blanc.camp == Camp.SOLITAIRE


@pytest.mark.parametrize(("joueurs", "attendu"), [(11, 0), (12, 1), (15, 1), (16, 2), (30, 2)])
def test_camps_solo_autorises(joueurs: int, attendu: int) -> None:
    assert camps_solo_autorises(joueurs) == attendu


def test_reglages_hors_limites_refuses() -> None:
    with pytest.raises(ValueError):
        Reglages(4, Experience.CONFIRME, 0)
    with pytest.raises(ValueError):
        Reglages(10, Experience.CONFIRME, 6)


@pytest.mark.parametrize(
    ("ids", "joueurs", "fragment"),
    [
        (["voyante", "loup-garou"], 5, "2 cartes pour 5 joueurs"),
        (["voyante", "voyante"], 2, "rôle unique"),
        (["deux-soeurs", "loup-garou", "villageois"], 3, "par 2"),
        (["villageois"] * 3, 3, "Aucun loup-garou"),
        (["loup-garou"] * 2 + ["villageois"] * 3, 5, "2/3"),
        (
            ["loup-garou"] * 2 + ["voyante"] * 1 + ["sorciere", "chasseur", "villageois"],
            6,
            "simples",
        ),
        (["cupidon", "loup-garou", "loup-garou"] + ["villageois"] * 9, 12, "Cupidon demande"),
        (["loup-blanc", "loup-garou"] + ["villageois"] * 10, 12, "loup-garou blanc demande"),
        (["joueur-de-flute"] + ["loup-garou"] * 3 + ["villageois"] * 7, 11, "camp(s) solo"),
        (["cupidon", "ange"] + ["loup-garou"] * 3 + ["villageois"] * 11, 16, "déconseillée"),
    ],
)
def test_avertissements(ids: list[str], joueurs: int, fragment: str) -> None:
    reglages = Reglages(max(joueurs, 5), Experience.CONFIRME, 0)
    messages = " ".join(compo(ids, reglages).avertissements())
    assert fragment in messages


@pytest.mark.parametrize("joueurs", [10, 16, 24])
def test_roles_expert_reserves_aux_experts(joueurs: int) -> None:
    for experience in (Experience.DEBUTANT, Experience.CONFIRME):
        for graine in range(5):
            composition = generer(CATALOGUE, Reglages(joueurs, experience, 0), graine=graine)
            assert all(r.niveau != Niveau.EXPERT for r in composition.cartes)


def test_les_experts_recoivent_des_roles_expert() -> None:
    compositions = [
        generer(CATALOGUE, Reglages(j, Experience.EXPERT, 0), graine=g)
        for j in (12, 18, 24)
        for g in range(5)
    ]
    assert any(r.niveau == Niveau.EXPERT for c in compositions for r in c.cartes)


def test_contraintes_imposer_exclure_liberer() -> None:
    contraintes = Contraintes().imposer("sorciere").exclure("voyante").imposer("villageois")
    assert contraintes == Contraintes(frozenset({"sorciere"}), frozenset({"voyante"}))
    assert contraintes.exclure("sorciere").imposes == frozenset()
    assert contraintes.liberer("voyante").exclus == frozenset()


@pytest.mark.parametrize("graine", range(5))
def test_generer_respecte_les_contraintes(graine: int) -> None:
    contraintes = Contraintes(
        imposes=frozenset({"loup-blanc", "colosse"}), exclus=frozenset({"voyante", "sorciere"})
    )
    composition = generer(CATALOGUE, Reglages(14, Experience.CONFIRME, 0), graine, contraintes)
    assert {"loup-blanc", "colosse"} <= set(composition.ids)
    assert not {"voyante", "sorciere"} & set(composition.ids)
    assert len(composition.cartes) == 14
