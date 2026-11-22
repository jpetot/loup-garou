import assert from "node:assert/strict";
import { test } from "node:test";

import { creerAleatoire } from "../js/aleatoire.js";
import { creerReglages } from "../js/composition.js";
import * as jeu from "../js/partie.js";
import { catalogueParDefaut } from "../js/roles.js";
import { charger, etatVide, exporter, importer, sauvegarder } from "../js/stockage.js";

const CATALOGUE = catalogueParDefaut();
const CARTES = ["loup-garou", "loup-garou", "voyante", "sorciere", "cupidon", "chasseur", "villageois"];
const NOMS = ["Alice", "Bruno", "Chloé", "David", "Emma", "Fanny", "Gaël"];

function partieDemarree() {
  const etat = etatVide();
  const partie = jeu.creerPartie(etat, creerReglages(7, "confirme", 0), CARTES);
  jeu.demarrer(etat, partie, NOMS, CARTES);
  const id = (nom) => partie.participants.find((p) => p.nom === nom).id;
  return { etat, partie, id };
}

const titres = (partie, numero) =>
  jeu.appelsDeLaNuit(numero, jeu.joueurs(partie, CATALOGUE), CATALOGUE).map((a) => a.titre);

test("démarrer enregistre les joueurs et les noms connus", () => {
  const { etat, partie } = partieDemarree();
  assert.equal(partie.statut, "en_cours");
  assert.equal(partie.participants[0].roleId, "loup-garou");
  assert.deepEqual(etat.personnes, [...NOMS].sort((a, b) => a.localeCompare(b, "fr")));
});

for (const [noms, roles, message] of [
  [[...NOMS.slice(0, -1), ""], CARTES, /nom des 7/],
  [[...NOMS.slice(0, -1), "alice"], CARTES, /double/],
  [NOMS, [...CARTES.slice(0, -1), "voyante"], /ne correspondent pas/],
]) {
  test(`démarrer refuse : ${message}`, () => {
    const etat = etatVide();
    const partie = jeu.creerPartie(etat, creerReglages(7, "confirme", 0), CARTES);
    assert.throws(() => jeu.demarrer(etat, partie, noms, roles), message);
  });
}

test("attribuer au hasard garde les cartes", () => {
  const roles = jeu.attribuerAuHasard(CARTES, creerAleatoire(1));
  assert.deepEqual([...roles].sort(), [...CARTES].sort());
});

test("appels de la première puis de la deuxième nuit", () => {
  const { partie } = partieDemarree();
  assert.deepEqual(titres(partie, 1), ["Cupidon", "Voyante", "Loups-garous", "Sorcière"]);
  assert.ok(!titres(partie, 2).includes("Cupidon"));
  const loups = jeu.appelsDeLaNuit(1, jeu.joueurs(partie, CATALOGUE), CATALOGUE)[2];
  assert.deepEqual(loups.joueurs.map((j) => j.nom), ["Alice", "Bruno"]);
});

test("un joueur devenu loup est appelé avec la meute", () => {
  const { partie, id } = partieDemarree();
  jeu.basculerMarqueur(partie, id("Gaël"), "devenu loup", CATALOGUE);
  const loups = jeu
    .appelsDeLaNuit(2, jeu.joueurs(partie, CATALOGUE), CATALOGUE)
    .find((a) => a.titre === "Loups-garous");
  assert.ok(loups.joueurs.some((j) => j.nom === "Gaël"));
});

test("le loup-garou blanc est appelé les nuits paires", () => {
  const etat = etatVide();
  const cartes = ["loup-garou", "loup-garou", "loup-blanc", "voyante", "villageois"];
  const partie = jeu.creerPartie(etat, creerReglages(5, "expert", 0), cartes);
  jeu.demarrer(etat, partie, NOMS.slice(0, 5), cartes);
  assert.ok(!titres(partie, 1).includes("Loup-garou blanc"));
  assert.ok(titres(partie, 2).includes("Loup-garou blanc"));
});

test("la mort du chasseur donne un rappel", () => {
  const { partie, id } = partieDemarree();
  const rappel = jeu.basculerVivant(partie, id("Fanny"), CATALOGUE);
  assert.match(rappel, /tire/);
  assert.equal(partie.participants[5].vivant, false);
});

test("la mort d'un amoureux rappelle le chagrin", () => {
  const { partie, id } = partieDemarree();
  jeu.basculerMarqueur(partie, id("Chloé"), "amoureux", CATALOGUE);
  jeu.basculerMarqueur(partie, id("Gaël"), "amoureux", CATALOGUE);
  jeu.basculerVivant(partie, id("Chloé"), CATALOGUE);
  assert.deepEqual(jeu.rappels(jeu.joueurs(partie, CATALOGUE)), [
    "Chloé est mort : Gaël meurt de chagrin.",
  ]);
});

test("un marqueur d'un autre rôle est refusé", () => {
  const { partie, id } = partieDemarree();
  assert.throws(
    () => jeu.basculerMarqueur(partie, id("Alice"), "potion de vie utilisée", CATALOGUE),
    jeu.ErreurPartie,
  );
  jeu.basculerMarqueur(partie, id("David"), "potion de vie utilisée", CATALOGUE);
});

test("une nouvelle nuit efface les marqueurs de la nuit", () => {
  const { partie, id } = partieDemarree();
  jeu.basculerMarqueur(partie, id("Emma"), "protégé", CATALOGUE);
  jeu.basculerMarqueur(partie, id("Emma"), "amoureux", CATALOGUE);
  jeu.changerDePhase(partie);
  assert.deepEqual([partie.phase, partie.numero], ["jour", 1]);
  assert.ok(partie.participants[4].marqueurs.includes("protégé"));
  jeu.changerDePhase(partie);
  assert.deepEqual([partie.phase, partie.numero], ["nuit", 2]);
  assert.deepEqual(partie.participants[4].marqueurs, ["amoureux"]);
});

test("terminer bloque les actions", () => {
  const { partie, id } = partieDemarree();
  jeu.terminer(partie, "village");
  assert.equal(partie.gagnant, "village");
  assert.throws(() => jeu.basculerVivant(partie, id("Alice"), CATALOGUE), jeu.ErreurPartie);
  assert.match(jeu.journal(partie)[0].texte, /^Fin de la partie/);
});

test("stockage : sauvegarder, charger, exporter, importer", () => {
  const memoire = new Map();
  const stockage = { getItem: (k) => memoire.get(k) ?? null, setItem: (k, v) => memoire.set(k, v) };
  const { etat } = partieDemarree();
  assert.equal(sauvegarder(etat, stockage), true);
  assert.deepEqual(charger(stockage), etat);
  assert.deepEqual(importer(exporter(etat)), etat);
  assert.throws(() => importer("pas du json"), /JSON/);
  assert.throws(() => importer('{"version": 99}'), /valide/);
  assert.deepEqual(charger({ getItem: () => "{cassé" }), etatVide());
  assert.equal(sauvegarder(etat, { setItem: () => { throw new Error("plein"); } }), false);
});
