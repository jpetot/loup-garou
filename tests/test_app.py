from fastapi.testclient import TestClient

from loup_garou.app import app

client = TestClient(app)


REGLAGES = {"joueurs": "10", "experience": "confirme", "familiarite": "0"}


def test_accueil_redirige_vers_composer() -> None:
    reponse = client.get("/", follow_redirects=False)
    assert reponse.status_code == 307
    assert reponse.headers["location"] == "/composer"


def test_generer_renvoie_une_composition() -> None:
    reponse = client.post("/composer/generer", data=REGLAGES)
    assert reponse.status_code == 200
    assert reponse.text.count('name="roles"') == 10


def test_generer_refuse_un_nombre_de_joueurs_invalide() -> None:
    reponse = client.post("/composer/generer", data=REGLAGES | {"joueurs": "3"})
    assert reponse.status_code == 422


def test_modifier_ajoute_et_retire_des_roles() -> None:
    base = REGLAGES | {"roles": ["loup-garou", "villageois"]}
    ajout = client.post(
        "/composer/modifier", data=base | {"action": "ajouter", "nouveau": "deux-soeurs"}
    )
    assert ajout.text.count('value="deux-soeurs"') == 2 + 1
    retrait = client.post("/composer/modifier", data=base | {"action": "moins:villageois"})
    assert 'name="roles" value="villageois"' not in retrait.text


def test_modifier_refuse_un_second_role_unique() -> None:
    base = REGLAGES | {"roles": ["voyante"]}
    reponse = client.post("/composer/modifier", data=base | {"action": "plus:voyante"})
    assert reponse.text.count('name="roles" value="voyante"') == 1


def test_liste_complete_contient_la_page() -> None:
    reponse = client.get("/roles")
    assert reponse.status_code == 200
    assert "<html" in reponse.text
    assert "Sorcière" in reponse.text


def test_requete_htmx_renvoie_seulement_les_cartes() -> None:
    reponse = client.get("/roles", params={"camp": "loups"}, headers={"HX-Request": "true"})
    assert reponse.status_code == 200
    assert "<html" not in reponse.text
    assert "Loup-garou" in reponse.text
    assert "Sorcière" not in reponse.text


def test_detail_role() -> None:
    reponse = client.get("/roles/sorciere")
    assert reponse.status_code == 200
    assert "potion" in reponse.text


def test_role_inconnu_renvoie_404() -> None:
    assert client.get("/roles/inexistant").status_code == 404


def test_ordre_de_nuit() -> None:
    reponse = client.get("/nuit")
    assert reponse.status_code == 200
    assert reponse.text.index("Cupidon") < reponse.text.index("Sorcière")
