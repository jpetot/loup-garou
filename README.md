# Loup-Garou — assistant du MJ

Application web installable (PWA) pour composer des parties équilibrées et animer le jeu.
Elle fonctionne hors connexion et enregistre les parties sur le téléphone du MJ.

## Utiliser sur un téléphone

1. Ouvrez l'adresse de l'application dans le navigateur (Safari sur iPhone, Chrome sur Android).
2. Ajoutez-la à l'écran d'accueil : « Partager → Sur l'écran d'accueil » sur iPhone,
   « ⋮ → Installer l'application » sur Android.
3. Elle s'ouvre ensuite comme une application, même en mode avion.

Les parties restent sur le téléphone. Dans **Parties**, le bouton **Exporter** crée un fichier
de sauvegarde, et **Importer** le recharge sur ce téléphone ou sur un autre.

## Développer

Aucune dépendance à installer : le site est fait de fichiers statiques (HTML, CSS, modules
JavaScript).

```bash
npm run serve
```

Ouvrez `http://localhost:8000`. Le service worker exige `localhost` ou HTTPS : n'ouvrez pas
`index.html` directement depuis le disque.

```bash
npm test
```

## Données

- `js/data/roles.js` : la base de rôles. Les poids sont en « unités villageois » :
  positif pour le village, négatif pour les loups et les solitaires.
- `js/composition.js` : le générateur de compositions et ses règles d'équilibrage.
- `js/partie.js` : le déroulement d'une partie (ordre d'appel, états des joueurs, journal).
- `js/stockage.js` : l'enregistrement sur le téléphone, l'export et l'import.

Après une modification des fichiers du site, changez `VERSION` dans `sw.js` pour que les
téléphones déjà installés récupèrent la nouvelle version.
