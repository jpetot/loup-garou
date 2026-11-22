import assert from "node:assert/strict";
import { test } from "node:test";

import { Catalogue, appeleLaNuit, catalogueParDefaut, creerRole, poids } from "../js/roles.js";

const minimal = (id, poidsMin = 1, poidsMax = 1) => ({
  id,
  nom: "Test",
  camp: "village",
  extension: "base",
  niveau: "classique",
  poidsMin,
  poidsMax,
  pouvoir: "Aucun",
});

test("le catalogue par défaut se charge", () => {
  const catalogue = catalogueParDefaut();
  assert.ok(catalogue.taille >= 30);
  const loup = catalogue.get("loup-garou");
  assert.equal(loup.camp, "loups");
  assert.ok(poids(loup) < 0);
  assert.equal(catalogue.get("abominable-sectaire"), null);
});

test("poidsMin supérieur au max refusé", () => {
  assert.throws(() => creerRole(minimal("x", 3, 1)), /poidsMin > poidsMax/);
});

test("identifiants en double refusés", () => {
  assert.throws(() => new Catalogue([creerRole(minimal("x")), creerRole(minimal("x"))]), /double/);
});

test("filtrer par camp, niveau et texte", () => {
  const catalogue = catalogueParDefaut();
  assert.ok(catalogue.filtrer({ camp: "loups" }).every((r) => r.camp === "loups"));
  assert.ok(catalogue.filtrer({ niveau: "classique" }).every((r) => r.niveau === "classique"));
  assert.deepEqual(
    catalogue.filtrer({ recherche: "POTION" }).map((r) => r.id),
    ["sorciere"],
  );
});

test("ordre de nuit trié et sans rôles passifs", () => {
  const ordre = catalogueParDefaut().ordreDeNuit();
  const valeurs = ordre.map((r) => r.ordreNuit);
  assert.deepEqual(valeurs, [...valeurs].sort((a, b) => a - b));
  assert.ok(!ordre.some((r) => r.id === "chasseur"));
});

test("nuits d'appel : première nuit, nuits paires, nuit max", () => {
  const c = catalogueParDefaut();
  assert.equal(appeleLaNuit(c.get("cupidon"), 2), false);
  assert.equal(appeleLaNuit(c.get("loup-blanc"), 1), false);
  assert.equal(appeleLaNuit(c.get("loup-blanc"), 2), true);
  assert.equal(appeleLaNuit(c.get("mere-des-loups"), 2), true);
  assert.equal(appeleLaNuit(c.get("mere-des-loups"), 3), false);
  assert.equal(appeleLaNuit(c.get("chasseur"), 1), false);
});
