import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  Contraintes,
  EXPERIENCES,
  campsSoloAutorises,
  compositionDepuisIds,
  creerReglages,
  generer,
  penaliteMeute,
} from "../js/composition.js";
import { catalogueParDefaut } from "../js/roles.js";

const CATALOGUE = catalogueParDefaut();
const CONFIRMES = creerReglages(10, "confirme", 0);
const compo = (ids, reglages = CONFIRMES) => compositionDepuisIds(CATALOGUE, ids, reglages);

describe("compositions générées", () => {
  for (const joueurs of [5, 8, 12, 16, 22, 30]) {
    for (const experience of EXPERIENCES) {
      for (const familiarite of [-5, 0, 5]) {
        test(`${joueurs} ${experience} ${familiarite} respecte les règles`, () => {
          const reglages = creerReglages(joueurs, experience, familiarite);
          const c = generer(CATALOGUE, reglages, 42);
          assert.equal(c.cartes.length, joueurs);
          assert.deepEqual(c.avertissements(), []);
          assert.ok(c.cartes.every((r) => r.cartesSupplementaires === 0));
          assert.ok(c.ids.includes("voyante"));
        });
      }
    }
  }

  for (const joueurs of [10, 12, 15, 20]) {
    for (const experience of EXPERIENCES) {
      test(`${joueurs} ${experience} équilibrée`, () => {
        const c = generer(CATALOGUE, creerReglages(joueurs, experience, 0), 1);
        assert.ok(Math.abs(c.ecart) <= 1, `écart ${c.ecart}`);
      });
    }
  }
});

test("niveaux de rôles selon l'expérience", () => {
  for (const joueurs of [8, 12, 20, 24]) {
    for (let graine = 0; graine < 5; graine++) {
      const debutants = generer(CATALOGUE, creerReglages(joueurs, "debutant", 0), graine);
      assert.ok(debutants.cartes.every((r) => r.niveau === "classique"));
      const confirmes = generer(CATALOGUE, creerReglages(joueurs, "confirme", 0), graine);
      assert.ok(confirmes.cartes.every((r) => r.niveau !== "expert"));
    }
  }
  const experts = [12, 18, 24].flatMap((j) =>
    [0, 1, 2, 3, 4].map((g) => generer(CATALOGUE, creerReglages(j, "expert", 0), g)),
  );
  assert.ok(experts.some((c) => c.cartes.some((r) => r.niveau === "expert")));
});

test("même graine, même composition", () => {
  assert.deepEqual(generer(CATALOGUE, CONFIRMES, 7).ids, generer(CATALOGUE, CONFIRMES, 7).ids);
});

test("pénalité de meute du mémo", () => {
  assert.deepEqual([1, 2, 3].map(penaliteMeute), [0, -2, -4]);
  assert.equal(compo(Array(3).fill("loup-garou")).poidsDesRoles + penaliteMeute(3), -22);
});

test("le score ajoute la meute et la familiarité", () => {
  const c = compo(["loup-garou", "loup-garou", "voyante", "villageois"], creerReglages(10, "confirme", 3));
  assert.equal(c.score, -12 + 9 + 1 - 2 + 3);
});

test("cible selon l'expérience", () => {
  const cibles = EXPERIENCES.map((e) => creerReglages(10, e, 0).cible);
  assert.deepEqual(cibles, [2, 0, -2]);
});

test("camps solo autorisés", () => {
  assert.deepEqual([11, 12, 15, 16, 30].map(campsSoloAutorises), [0, 1, 1, 2, 2]);
});

test("réglages hors limites refusés", () => {
  assert.throws(() => creerReglages(4, "confirme", 0), RangeError);
  assert.throws(() => creerReglages(10, "confirme", 6), RangeError);
  assert.throws(() => creerReglages(10, "inconnu", 0), RangeError);
});

describe("avertissements", () => {
  const cas = [
    [["voyante", "loup-garou"], 5, "2 cartes pour 5 joueurs"],
    [["voyante", "voyante"], 5, "rôle unique"],
    [["deux-soeurs", "loup-garou", "villageois"], 5, "par 2"],
    [Array(5).fill("villageois"), 5, "Aucun loup-garou"],
    [[...Array(2).fill("loup-garou"), ...Array(3).fill("villageois")], 5, "2/3"],
    [["loup-garou", "loup-garou", "voyante", "sorciere", "chasseur", "villageois"], 6, "simples"],
    [["cupidon", "loup-garou", "loup-garou", ...Array(9).fill("villageois")], 12, "Cupidon demande"],
    [["loup-blanc", "loup-garou", ...Array(10).fill("villageois")], 12, "loup-garou blanc demande"],
    [["joueur-de-flute", ...Array(3).fill("loup-garou"), ...Array(7).fill("villageois")], 11, "camp(s) solo"],
    [["cupidon", "ange", ...Array(3).fill("loup-garou"), ...Array(11).fill("villageois")], 16, "déconseillée"],
  ];
  for (const [ids, joueurs, fragment] of cas) {
    test(fragment, () => {
      const messages = compo(ids, creerReglages(joueurs, "confirme", 0)).avertissements().join(" ");
      assert.ok(messages.includes(fragment), messages);
    });
  }
});

test("contraintes : imposer, exclure, libérer", () => {
  const c = new Contraintes().imposer("sorciere").exclure("voyante").imposer("villageois");
  assert.deepEqual([...c.imposes], ["sorciere"]);
  assert.deepEqual([...c.exclus], ["voyante"]);
  assert.equal(c.exclure("sorciere").imposes.size, 0);
  assert.equal(c.liberer("voyante").exclus.size, 0);
});

test("générer respecte les contraintes", () => {
  const contraintes = new Contraintes(["loup-blanc", "colosse"], ["voyante", "sorciere"]);
  for (let graine = 0; graine < 5; graine++) {
    const c = generer(CATALOGUE, creerReglages(14, "confirme", 0), graine, contraintes);
    assert.ok(c.ids.includes("loup-blanc") && c.ids.includes("colosse"));
    assert.ok(!c.ids.includes("voyante") && !c.ids.includes("sorciere"));
    assert.equal(c.cartes.length, 14);
  }
});
