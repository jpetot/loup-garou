# Loup-Garou — assistant du MJ

Application web (FastAPI + HTMX) pour composer des parties équilibrées et animer le jeu.

## Lancer

```bash
uv run loup-garou
```

Ouvrez `http://localhost:8000`. Par défaut, l'app n'accepte que les connexions de cet ordinateur.

Pour l'ouvrir depuis un téléphone sur le même Wi-Fi :

```bash
HOST=0.0.0.0 RELOAD=0 uv run loup-garou
```

Puis ouvrez `http://<ip-de-l-ordi>:8000` (l'IP est donnée par `ipconfig getifaddr en0`).
Ne faites cela que sur un réseau de confiance (votre box) : toute personne connectée au
même réseau peut ouvrir l'app, qui n'a pas encore de mot de passe.

## Tests

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Données

La base de rôles est dans `src/loup_garou/data/roles.yaml`. Les poids sont en « unités villageois » :
positif pour le village, négatif pour les loups et les solitaires.
