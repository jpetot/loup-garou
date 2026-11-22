import {
  Contraintes,
  EXPERIENCES,
  JOUEURS_MAX,
  JOUEURS_MIN,
  ROLES_DE_BASE,
  creerReglages,
  generer,
} from "./composition.js";
import { creerAleatoire } from "./aleatoire.js";
import * as jeu from "./partie.js";
import { CAMPS, NIVEAUX, catalogueParDefaut, poids } from "./roles.js";
import { ErreurImport, charger, exporter, importer, sauvegarder } from "./stockage.js";

const LIBELLES_CAMP = { village: "Village", loups: "Loups", solitaire: "Solitaire", ambigu: "Ambigu" };
const LIBELLES_NIVEAU = { classique: "Classique", avance: "Avancé", expert: "Expert" };
const LIBELLES_EXPERIENCE = { debutant: "Débutants", confirme: "Confirmés", expert: "Experts" };
const LIBELLES_FAMILIARITE = new Map([
  [-5, "Ne se sont jamais vus"],
  [-2, "Se connaissent peu"],
  [0, "La moitié se connaît"],
  [2, "Se connaissent bien"],
  [5, "Jouent souvent ensemble"],
]);
const LIBELLES_GAGNANT = {
  village: "Village",
  loups: "Loups-garous",
  solitaire: "Un solitaire",
  amoureux: "Les amoureux",
};
const SEUIL_EQUILIBRE = 1;
const DELAI_NOTES_MS = 600;

const catalogue = catalogueParDefaut();
const racine = document.getElementById("app");
let etat = charger();

const ui = {
  composer: {
    joueurs: 10,
    experience: "confirme",
    familiarite: 0,
    contraintes: new Contraintes(),
    composition: null,
    erreur: null,
  },
  roles: { q: "", camp: "", niveau: "" },
  preparation: new Map(),
  ouverts: new Set(),
  rappel: null,
  message: null,
};

const esc = (valeur) =>
  String(valeur ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

function signe(n) {
  const v = Math.round(n * 10) / 10 || 0;
  return `${v >= 0 ? "+" : "−"}${Math.abs(v)}`;
}

const options = (paires, choisi) =>
  paires
    .map(
      ([valeur, libelle]) =>
        `<option value="${esc(valeur)}" ${String(valeur) === String(choisi) ? "selected" : ""}>${esc(libelle)}</option>`,
    )
    .join("");

function sauver() {
  if (!sauvegarder(etat)) {
    ui.message = "Impossible d'enregistrer sur ce téléphone : le stockage est plein ou bloqué.";
  }
}

function avertissement(texte) {
  return `<p class="avertissement">⚠️ ${esc(texte)}</p>`;
}

function vueComposer() {
  const c = ui.composer;
  return `
    <h1>Composer une partie</h1>
    <form data-form="composer">
      <label>Nombre de joueurs
        <input type="number" name="joueurs" value="${c.joueurs}" min="${JOUEURS_MIN}" max="${JOUEURS_MAX}" required inputmode="numeric">
      </label>
      <label>Expérience du groupe
        <select name="experience">${options(EXPERIENCES.map((e) => [e, LIBELLES_EXPERIENCE[e]]), c.experience)}</select>
      </label>
      <label>Familiarité entre joueurs
        <select name="familiarite">${options([...LIBELLES_FAMILIARITE], c.familiarite)}</select>
      </label>
      <button type="submit">Générer</button>
    </form>
    ${c.erreur ? avertissement(c.erreur) : ""}
    <div id="resultat">${c.composition ? vueResultat(c.composition, c.contraintes) : ""}</div>`;
}

function jauge(ecart) {
  if (ecart > SEUIL_EQUILIBRE) return `<span class="jauge camp-village">Avantage village ${signe(ecart)}</span>`;
  if (ecart < -SEUIL_EQUILIBRE) return `<span class="jauge camp-loups">Avantage loups ${signe(ecart)}</span>`;
  return `<span class="jauge">Équilibré ${signe(ecart)}</span>`;
}

function vueResultat(composition, contraintes) {
  const { reglages } = composition;
  const ids = new Set(composition.ids);
  const nom = (id) => catalogue.get(id)?.nom ?? id;
  const lignes = composition
    .decompte()
    .map(({ role, nombre }) => {
      const boutons = ROLES_DE_BASE.has(role.id)
        ? ""
        : `${contraintes.imposes.has(role.id) ? "" : `<button data-action="imposer" data-role="${role.id}" class="secondary outline" title="Garder ce rôle" aria-label="Garder ${esc(role.nom)}">📌</button>`}
           <button data-action="exclure" data-role="${role.id}" class="secondary outline" title="Retirer ce rôle et recomposer" aria-label="Retirer ${esc(role.nom)}">−</button>`;
      return `
        <li class="camp-${role.camp}">
          <a href="#/roles/${role.id}">${contraintes.imposes.has(role.id) ? "📌 " : ""}${esc(role.nom)}${nombre > 1 ? ` ×${nombre}` : ""}</a>
          <span class="poids">${signe(poids(role) * nombre)}</span>
          <span class="quantite">${boutons}</span>
        </li>`;
    })
    .join("");
  const puces = [
    ...[...contraintes.imposes].sort().map(
      (id) => `<button data-action="liberer" data-role="${id}" class="puce puce-impose" title="Ne plus imposer">📌 ${esc(nom(id))} ✕</button>`,
    ),
    ...[...contraintes.exclus].sort().map(
      (id) => `<button data-action="liberer" data-role="${id}" class="puce puce-exclu" title="Autoriser à nouveau">🚫 ${esc(nom(id))} ✕</button>`,
    ),
  ].join("");
  const aAjouter = catalogue
    .filtrer()
    .filter((r) => !ROLES_DE_BASE.has(r.id) && !contraintes.imposes.has(r.id) && !ids.has(r.id));
  return `
    <article>
      <header class="bilan">
        <div>
          <strong>${composition.cartes.length} cartes</strong>
          <small>${LIBELLES_EXPERIENCE[reglages.experience]} · ${esc((LIBELLES_FAMILIARITE.get(reglages.familiarite) ?? reglages.familiarite).toString().toLowerCase())}</small>
        </div>
        ${jauge(composition.ecart)}
      </header>
      <p class="detail-score">
        Rôles ${signe(composition.poidsDesRoles)} · meute ${signe(composition.penaliteMeute)}
        · familiarité ${signe(reglages.familiarite)} = <strong>${signe(composition.score)}</strong>
        (cible ${signe(reglages.cible)})
      </p>
      ${composition.avertissements().map(avertissement).join("")}
      <ul class="compo">${lignes}</ul>
      ${puces ? `<div class="contraintes">${puces}</div>` : ""}
      <fieldset role="group">
        <select id="nouveau" aria-label="Rôle à imposer">
          ${options(aAjouter.map((r) => [r.id, `${r.nom} (${signe(poids(r))})`]))}
        </select>
        <button data-action="ajouter">Imposer</button>
      </fieldset>
      <div class="grid">
        <button data-action="relancer" class="secondary">🎲 Relancer</button>
        <button data-action="lancer">▶️ Lancer la partie</button>
      </div>
    </article>`;
}

function composer() {
  const c = ui.composer;
  try {
    const reglages = creerReglages(c.joueurs, c.experience, c.familiarite);
    c.composition = generer(catalogue, reglages, Math.floor(Math.random() * 2 ** 32), c.contraintes);
    c.erreur = null;
  } catch (erreur) {
    c.composition = null;
    c.erreur = erreur.message;
  }
}

function vueCartes() {
  const roles = catalogue.filtrer({
    recherche: ui.roles.q,
    camp: ui.roles.camp || null,
    niveau: ui.roles.niveau || null,
  });
  if (!roles.length) return "<p>Aucun rôle ne correspond.</p>";
  return `
    <p class="compteur">${roles.length} rôle${roles.length > 1 ? "s" : ""}</p>
    ${roles
      .map(
        (r) => `
      <a class="carte camp-${r.camp}" href="#/roles/${r.id}">
        <div class="carte-entete"><strong>${esc(r.nom)}</strong><span class="poids">${signe(poids(r))}</span></div>
        <small>${LIBELLES_CAMP[r.camp]} · ${LIBELLES_NIVEAU[r.niveau]}</small>
        <p>${esc(r.pouvoir)}</p>
      </a>`,
      )
      .join("")}`;
}

function vueRoles() {
  const f = ui.roles;
  return `
    <h1>Rôles</h1>
    <form data-form="roles">
      <input type="search" name="q" value="${esc(f.q)}" placeholder="Rechercher un rôle ou un pouvoir…" aria-label="Recherche">
      <div class="grid">
        <select name="camp" aria-label="Camp">${options([["", "Tous les camps"], ...CAMPS.map((c) => [c, LIBELLES_CAMP[c]])], f.camp)}</select>
        <select name="niveau" aria-label="Niveau">${options([["", "Tous les niveaux"], ...NIVEAUX.map((n) => [n, LIBELLES_NIVEAU[n]])], f.niveau)}</select>
      </div>
    </form>
    <div id="cartes">${vueCartes()}</div>`;
}

function vueRole(id) {
  const r = catalogue.get(id);
  if (!r) return "<h1>Rôle inconnu</h1><p><a href=\"#/roles\">← Tous les rôles</a></p>";
  const plage = r.poidsMin === r.poidsMax ? signe(r.poidsMin) : `de ${signe(r.poidsMin)} à ${signe(r.poidsMax)}`;
  let nuit = "";
  if (r.ordreNuit !== null) {
    const precisions = [
      r.premiereNuitSeulement && "première nuit seulement",
      r.nuitMax && !r.premiereNuitSeulement && `${r.nuitMax} premières nuits`,
      r.nuitsPaires && "nuits paires",
    ].filter(Boolean);
    nuit = `<h4>Nuit</h4><p>Appelé la nuit${precisions.length ? `, ${precisions.join(", ")}` : ""}.</p>`;
  }
  return `
    <p><a href="#/roles">← Tous les rôles</a></p>
    <article class="camp-${r.camp}">
      <header>
        <h2>${esc(r.nom)}</h2>
        <small>${LIBELLES_CAMP[r.camp]} · ${LIBELLES_NIVEAU[r.niveau]} · extension ${esc(r.extension.replace("_", " "))}</small>
      </header>
      <h4>Pouvoir</h4>
      <p>${esc(r.pouvoir)}</p>
      ${r.description ? `<p>${esc(r.description)}</p>` : ""}
      <h4>Équilibrage</h4>
      <p>${plage} unités villageois${r.groupe > 1 ? ` par carte, joué par ${r.groupe}` : ""}.
        <br><small>Source : ${esc(r.source)}${r.camp === "loups" || r.estLoup ? " · compte comme un loup (−2 par loup après le premier)" : ""}</small></p>
      ${nuit}
      ${r.conseilsMj ? `<footer><strong>Conseil MJ :</strong> ${esc(r.conseilsMj)}</footer>` : ""}
    </article>`;
}

function vueNuit() {
  return `
    <h1>Ordre d'appel de la nuit</h1>
    <ol class="nuit">
      ${catalogue
        .ordreDeNuit()
        .map(
          (r) => `
        <li class="camp-${r.camp}">
          <a href="#/roles/${r.id}"><strong>${esc(r.nom)}</strong></a>
          ${r.premiereNuitSeulement ? "<mark>1re nuit</mark>" : ""}
          ${r.conseilsMj ? `<br><small>${esc(r.conseilsMj)}</small>` : ""}
        </li>`,
        )
        .join("")}
    </ol>`;
}

function statutPartie(p) {
  if (p.statut === "preparation") return "en préparation";
  if (p.statut === "en_cours") return `en cours (${p.phase} ${p.numero})`;
  return `terminée, victoire : ${LIBELLES_GAGNANT[p.gagnant] ?? p.gagnant}`;
}

function vueParties() {
  const parties = [...etat.parties].sort((a, b) => b.id - a.id);
  return `
    <h1>Parties</h1>
    <p><a href="#/composer" role="button">Nouvelle partie</a></p>
    ${
      parties
        .map(
          (p) => `
      <a class="carte" href="#/parties/${p.id}">
        <div class="carte-entete"><strong>Partie n°${p.id}</strong><small>${new Date(p.creeLe).toLocaleDateString("fr-FR")}</small></div>
        <small>${p.joueurs} joueurs · ${esc(statutPartie(p))}</small>
      </a>`,
        )
        .join("") || "<p>Aucune partie pour l'instant. Composez-en une pour la lancer.</p>"
    }
    <section>
      <h2>Sauvegarde</h2>
      <p><small>Les parties sont enregistrées sur ce téléphone. Exportez-les de temps en temps pour ne rien perdre.</small></p>
      <div class="grid">
        <button data-action="exporter" class="secondary">⬇️ Exporter</button>
        <button data-action="importer" class="secondary">⬆️ Importer</button>
      </div>
      <input type="file" id="fichier-import" accept="application/json,.json" hidden>
    </section>`;
}

function etatPreparation(partie) {
  if (!ui.preparation.has(partie.id)) {
    ui.preparation.set(partie.id, {
      noms: Array(partie.joueurs).fill(""),
      roles: Array(partie.joueurs).fill(""),
      erreur: null,
    });
  }
  return ui.preparation.get(partie.id);
}

function vuePreparation(partie) {
  const prep = etatPreparation(partie);
  const distincts = catalogue.filtrer().filter((r) => partie.cartes.includes(r.id));
  const compte = (id) => partie.cartes.filter((x) => x === id).length;
  const resume = distincts.map((r) => `${r.nom}${compte(r.id) > 1 ? ` ×${compte(r.id)}` : ""}`).join(", ");
  const lignes = prep.noms
    .map(
      (nom, i) => `
      <li>
        <fieldset role="group">
          <input name="noms" value="${esc(nom)}" placeholder="Joueur ${i + 1}" list="noms-connus" autocomplete="off" aria-label="Nom du joueur ${i + 1}">
          <select name="roles" aria-label="Rôle du joueur ${i + 1}">
            ${options([["", "Rôle…"], ...distincts.map((r) => [r.id, r.nom])], prep.roles[i])}
          </select>
        </fieldset>
      </li>`,
    )
    .join("");
  return `
    <h1>Préparer la partie</h1>
    <p class="detail-score">Composition : ${esc(resume)}</p>
    ${prep.erreur ? avertissement(prep.erreur) : ""}
    <form data-form="preparation" data-partie="${partie.id}">
      <datalist id="noms-connus">${etat.personnes.map((n) => `<option value="${esc(n)}">`).join("")}</datalist>
      <ol class="places">${lignes}</ol>
      <p><small>Saisissez les joueurs dans l'ordre où ils sont assis : certains rôles dépendent des voisins.</small></p>
      <div class="grid">
        <button type="button" data-action="hasard" class="secondary">🎲 Distribuer au hasard</button>
        <button type="submit">▶️ Commencer</button>
      </div>
    </form>`;
}

function lirePreparation(formulaire) {
  const donnees = new FormData(formulaire);
  return { noms: donnees.getAll("noms").map(String), roles: donnees.getAll("roles").map(String) };
}

function vueTableau(partie) {
  const enCours = partie.statut === "en_cours";
  const liste = jeu.joueurs(partie, catalogue);
  const vivants = liste.filter((j) => j.vivant);
  const nbLoups = vivants.filter((j) => j.estLoup).length;
  const rappels = [...(ui.rappel ? [ui.rappel] : []), ...jeu.rappels(liste)];
  ui.rappel = null;
  const nuit = partie.phase === "nuit";

  const appels = jeu
    .appelsDeLaNuit(partie.numero, liste, catalogue)
    .map(
      (a) => `
      <li class="camp-${a.role.camp}${a.tousMorts ? " mort" : ""}">
        <label><input type="checkbox"> <strong>${esc(a.titre)}</strong> —
          ${a.joueurs.map((j) => `<span class="${j.vivant ? "" : "barre"}">${esc(j.nom)}</span>`).join(", ")}</label>
        ${
          a.tousMorts
            ? "<small>Mort : appelez quand même pour ne pas le révéler.</small>"
            : a.pouvoirPerdu
              ? "<small>Pouvoir perdu : appelez pour la forme.</small>"
              : a.role.conseilsMj
                ? `<small>${esc(a.role.conseilsMj)}</small>`
                : ""
        }
      </li>`,
    )
    .join("");

  const journee = [
    ...vivants.filter((j) => j.marqueurs.includes("muet")).map((j) => `<li>🤐 ${esc(j.nom)} ne peut pas parler aujourd'hui.</li>`),
    ...vivants.filter((j) => j.marqueurs.includes("marqué")).map((j) => `<li>🐦 ${esc(j.nom)} a deux voix contre lui au vote.</li>`),
    `<li>Vote : ${vivants.length} joueurs vivants.</li>`,
  ].join("");

  const bouton = (j, marqueur, libelle) =>
    `<button data-action="marqueur" data-joueur="${j.id}" data-marqueur="${esc(marqueur)}" class="marqueur ${j.marqueurs.includes(marqueur) ? "actif" : ""}">${libelle}</button>`;

  const fiches = liste
    .map(
      (j) => `
      <details class="joueur camp-${j.role.camp}${j.vivant ? "" : " mort"}" data-joueur="${j.id}" ${ui.ouverts.has(`${partie.id}:${j.id}`) ? "open" : ""}>
        <summary>
          <span class="${j.vivant ? "" : "barre"}"><strong>${esc(j.nom)}</strong> · ${esc(j.role.nom)}</span>
          <span class="marqueurs">${j.marqueurs.map((m) => jeu.MARQUEURS_COMMUNS[m] ?? "•").join("")}${j.vivant ? "" : " 💀"}</span>
        </summary>
        ${
          enCours
            ? `<div class="actions-joueur">
                <button data-action="vivant" data-joueur="${j.id}" class="${j.vivant ? "secondary" : ""} outline">${j.vivant ? "💀 Mort" : "↩️ Revient en jeu"}</button>
                ${Object.entries(jeu.MARQUEURS_COMMUNS).map(([m, emoji]) => bouton(j, m, `${emoji} ${m}`)).join("")}
                ${j.role.marqueurs.map((m) => bouton(j, m, `• ${esc(m)}`)).join("")}
              </div>`
            : j.marqueurs.length
              ? `<p><small>${esc(j.marqueurs.join(", "))}</small></p>`
              : ""
        }
        <textarea data-notes="${j.id}" placeholder="Notes du MJ" rows="2">${esc(j.notes)}</textarea>
      </details>`,
    )
    .join("");

  return `
    <header class="phase">
      <div>
        <h1>${nuit ? "🌙 Nuit" : "☀️ Jour"} ${partie.numero}</h1>
        <small>Partie n°${partie.id} · ${vivants.length} vivants dont ${nbLoups} loup${nbLoups > 1 ? "s" : ""}</small>
      </div>
      ${enCours ? `<button data-action="phase" class="contrast">${nuit ? "☀️ Passer au jour" : `🌙 Nuit ${partie.numero + 1}`}</button>` : ""}
    </header>
    ${enCours ? "" : `<p class="fin">🏁 Partie terminée — victoire : <strong>${esc(LIBELLES_GAGNANT[partie.gagnant] ?? partie.gagnant)}</strong></p>`}
    ${rappels.map(avertissement).join("")}
    ${
      nuit
        ? `<section><h2>Ordre d'appel</h2><ol class="appels">${appels || "<li>Personne n'est appelé cette nuit.</li>"}</ol></section>`
        : `<section><h2>Journée</h2><ul>${journee}</ul></section>`
    }
    <section><h2>Joueurs</h2>${fiches}</section>
    <section>
      <h2>Journal</h2>
      ${
        enCours
          ? `<form data-form="journal" role="group">
              <input name="texte" placeholder="Ajouter une note au journal…" autocomplete="off" aria-label="Note du journal">
              <button type="submit">Noter</button>
            </form>`
          : ""
      }
      <ul class="journal">
        ${jeu.journal(partie).map((e) => `<li><small>${esc(e.phase)} ${e.numero}</small> ${esc(e.texte)}</li>`).join("")}
      </ul>
    </section>
    ${
      enCours
        ? `<section>
            <h2>Fin de partie</h2>
            <form data-form="terminer" role="group">
              <select name="gagnant" aria-label="Camp gagnant">${options(Object.entries(LIBELLES_GAGNANT))}</select>
              <button type="submit" class="secondary">🏁 Terminer</button>
            </form>
          </section>`
        : ""
    }`;
}

function routeActuelle() {
  const [page = "composer", id, sous] = location.hash.replace(/^#\/?/, "").split("/");
  return { page: page || "composer", id, sous };
}

function vue() {
  const { page, id, sous } = routeActuelle();
  switch (page) {
    case "roles":
      return id ? vueRole(decodeURIComponent(id)) : vueRoles();
    case "nuit":
      return vueNuit();
    case "parties": {
      if (!id) return vueParties();
      const partie = jeu.trouverPartie(etat, Number(id));
      if (!partie) return "<h1>Partie inconnue</h1><p><a href=\"#/parties\">← Parties</a></p>";
      if (partie.statut === "preparation") {
        if (sous !== "preparation") history.replaceState(null, "", `#/parties/${partie.id}/preparation`);
        return vuePreparation(partie);
      }
      return vueTableau(partie);
    }
    default:
      return vueComposer();
  }
}

function rendre() {
  const message = ui.message ? avertissement(ui.message) : "";
  ui.message = null;
  racine.innerHTML = message + vue();
  const { page } = routeActuelle();
  for (const lien of document.querySelectorAll("nav a")) {
    lien.toggleAttribute("aria-current", lien.getAttribute("href") === `#/${page}`);
  }
}

function partieCourante() {
  const { page, id } = routeActuelle();
  return page === "parties" && id ? jeu.trouverPartie(etat, Number(id)) : null;
}

function agirSurPartie(action) {
  const partie = partieCourante();
  if (!partie) return;
  try {
    action(partie);
  } catch (erreur) {
    if (!(erreur instanceof jeu.ErreurPartie)) throw erreur;
    ui.message = erreur.message;
  }
  sauver();
  rendre();
}

function telecharger(nom, texte) {
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([texte], { type: "application/json" }));
  lien.download = nom;
  lien.click();
  setTimeout(() => URL.revokeObjectURL(lien.href), 1000);
}

const actions = {
  imposer: (b) => {
    ui.composer.contraintes = ui.composer.contraintes.imposer(b.dataset.role);
    composer();
  },
  exclure: (b) => {
    ui.composer.contraintes = ui.composer.contraintes.exclure(b.dataset.role);
    composer();
  },
  liberer: (b) => {
    ui.composer.contraintes = ui.composer.contraintes.liberer(b.dataset.role);
    composer();
  },
  ajouter: () => {
    const id = document.getElementById("nouveau")?.value;
    if (id) ui.composer.contraintes = ui.composer.contraintes.imposer(id);
    composer();
  },
  relancer: () => composer(),
  lancer: () => {
    const { composition } = ui.composer;
    if (!composition) return;
    const partie = jeu.creerPartie(etat, composition.reglages, composition.ids);
    sauver();
    location.hash = `#/parties/${partie.id}/preparation`;
  },
  hasard: (b) => {
    const formulaire = b.closest("form");
    const partie = jeu.trouverPartie(etat, Number(formulaire.dataset.partie));
    const prep = etatPreparation(partie);
    prep.noms = lirePreparation(formulaire).noms;
    prep.roles = jeu.attribuerAuHasard(partie.cartes, creerAleatoire());
    prep.erreur = null;
  },
  vivant: (b) =>
    agirSurPartie((p) => {
      ui.rappel = jeu.basculerVivant(p, Number(b.dataset.joueur), catalogue);
    }),
  marqueur: (b) =>
    agirSurPartie((p) => jeu.basculerMarqueur(p, Number(b.dataset.joueur), b.dataset.marqueur, catalogue)),
  phase: () => agirSurPartie((p) => jeu.changerDePhase(p)),
  exporter: () => {
    const date = new Date().toISOString().slice(0, 10);
    telecharger(`loup-garou-${date}.json`, exporter(etat));
  },
  importer: () => document.getElementById("fichier-import")?.click(),
};

racine.addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("[data-action]");
  if (!bouton || !racine.contains(bouton)) return;
  evenement.preventDefault();
  const action = actions[bouton.dataset.action];
  if (!action) return;
  action(bouton);
  if (!["vivant", "marqueur", "phase", "lancer", "exporter", "importer"].includes(bouton.dataset.action)) {
    rendre();
  }
});

racine.addEventListener("submit", (evenement) => {
  const formulaire = evenement.target;
  evenement.preventDefault();
  const donnees = new FormData(formulaire);
  switch (formulaire.dataset.form) {
    case "composer": {
      Object.assign(ui.composer, {
        joueurs: Number(donnees.get("joueurs")),
        experience: String(donnees.get("experience")),
        familiarite: Number(donnees.get("familiarite")),
      });
      composer();
      rendre();
      document.getElementById("resultat")?.scrollIntoView({ behavior: "smooth" });
      break;
    }
    case "preparation": {
      const partie = jeu.trouverPartie(etat, Number(formulaire.dataset.partie));
      const prep = etatPreparation(partie);
      Object.assign(prep, lirePreparation(formulaire));
      try {
        jeu.demarrer(etat, partie, prep.noms, prep.roles);
        ui.preparation.delete(partie.id);
        sauver();
        location.hash = `#/parties/${partie.id}`;
      } catch (erreur) {
        if (!(erreur instanceof jeu.ErreurPartie)) throw erreur;
        prep.erreur = erreur.message;
        rendre();
      }
      break;
    }
    case "journal":
      agirSurPartie((p) => jeu.ajouterAuJournal(p, String(donnees.get("texte"))));
      break;
    case "terminer":
      if (confirm("Terminer la partie ?")) {
        agirSurPartie((p) => jeu.terminer(p, String(donnees.get("gagnant"))));
      }
      break;
  }
});

racine.addEventListener("input", (evenement) => {
  const champ = evenement.target;
  if (champ.form?.dataset.form === "roles") {
    ui.roles[champ.name] = champ.value;
    document.getElementById("cartes").innerHTML = vueCartes();
  }
  if (champ.dataset.notes) {
    clearTimeout(champ.minuterie);
    champ.minuterie = setTimeout(() => {
      const partie = partieCourante();
      if (!partie) return;
      jeu.noter(partie, Number(champ.dataset.notes), champ.value);
      sauver();
    }, DELAI_NOTES_MS);
  }
});

racine.addEventListener(
  "toggle",
  (evenement) => {
    const fiche = evenement.target;
    const partie = partieCourante();
    if (!fiche.matches?.("details.joueur") || !partie) return;
    const cle = `${partie.id}:${fiche.dataset.joueur}`;
    if (fiche.open) ui.ouverts.add(cle);
    else ui.ouverts.delete(cle);
  },
  true,
);

racine.addEventListener("change", async (evenement) => {
  const champ = evenement.target;
  if (champ.id !== "fichier-import" || !champ.files?.length) return;
  try {
    const nouvelEtat = importer(await champ.files[0].text());
    const resume = `${nouvelEtat.parties.length} partie(s) et ${nouvelEtat.personnes.length} joueur(s)`;
    if (confirm(`Remplacer les données de ce téléphone par ${resume} ?`)) {
      etat = nouvelEtat;
      sauver();
    }
  } catch (erreur) {
    if (!(erreur instanceof ErreurImport)) throw erreur;
    ui.message = erreur.message;
  }
  rendre();
});

window.addEventListener("hashchange", () => {
  rendre();
  window.scrollTo(0, 0);
});

rendre();

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
navigator.storage?.persist?.().catch(() => {});
