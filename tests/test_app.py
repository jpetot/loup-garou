import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loup_garou.app import creer_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(creer_app(f"sqlite:///{tmp_path / 'test.db'}"))


def roles_de(html: str) -> list[str]:
    return re.findall(r'name="roles" value="([^"]+)"', html)


REGLAGES = {"joueurs": "10", "experience": "confirme", "familiarite": "0"}


def test_accueil_redirige_vers_composer(client: TestClient) -> None:
    reponse = client.get("/", follow_redirects=False)
    assert reponse.status_code == 307
    assert reponse.headers["location"] == "/composer"


def test_generer_renvoie_une_composition(client: TestClient) -> None:
    reponse = client.post("/composer/generer", data=REGLAGES)
    assert reponse.status_code == 200
    assert reponse.text.count('name="roles"') == 10


def test_generer_refuse_un_nombre_de_joueurs_invalide(client: TestClient) -> None:
    reponse = client.post("/composer/generer", data=REGLAGES | {"joueurs": "3"})
    assert reponse.status_code == 422


def test_exclure_un_role_recompose_sans_lui(client: TestClient) -> None:
    reponse = client.post("/composer/generer", data=REGLAGES | {"action": "exclure:voyante"})
    assert "voyante" not in roles_de(reponse.text)
    assert 'name="exclus" value="voyante"' in reponse.text


def test_imposer_un_role_recompose_avec_lui(client: TestClient) -> None:
    donnees = REGLAGES | {"action": "ajouter", "nouveau": "colosse", "exclus": ["voyante"]}
    reponse = client.post("/composer/generer", data=donnees)
    roles = roles_de(reponse.text)
    assert "colosse" in roles
    assert "voyante" not in roles
    assert len(roles) == 10


def test_liberer_une_contrainte(client: TestClient) -> None:
    donnees = REGLAGES | {"action": "liberer:voyante", "exclus": ["voyante"]}
    reponse = client.post("/composer/generer", data=donnees)
    assert 'name="exclus"' not in reponse.text


def test_liste_complete_contient_la_page(client: TestClient) -> None:
    reponse = client.get("/roles")
    assert reponse.status_code == 200
    assert "<html" in reponse.text
    assert "Sorcière" in reponse.text


def test_requete_htmx_renvoie_seulement_les_cartes(client: TestClient) -> None:
    reponse = client.get("/roles", params={"camp": "loups"}, headers={"HX-Request": "true"})
    assert reponse.status_code == 200
    assert "<html" not in reponse.text
    assert "Loup-garou" in reponse.text
    assert "Sorcière" not in reponse.text


def test_detail_role(client: TestClient) -> None:
    reponse = client.get("/roles/sorciere")
    assert reponse.status_code == 200
    assert "potion" in reponse.text


def test_role_inconnu_renvoie_404(client: TestClient) -> None:
    assert client.get("/roles/inexistant").status_code == 404


def test_ordre_de_nuit(client: TestClient) -> None:
    reponse = client.get("/nuit")
    assert reponse.status_code == 200
    assert reponse.text.index("Cupidon") < reponse.text.index("Sorcière")
