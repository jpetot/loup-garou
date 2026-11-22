import { creerAleatoire } from "./aleatoire.js";
import { CAMPS, ajouteUnCampSolo, compteCommeLoup, poids } from "./roles.js";

export const JOUEURS_MIN = 5;
export const JOUEURS_MAX = 30;
export const FAMILIARITE_MIN = -5;
export const FAMILIARITE_MAX = 5;
export const ID_VILLAGEOIS = "villageois";
export const ID_LOUP = "loup-garou";
const ID_CUPIDON = "cupidon";
const ID_ANGE = "ange";
const ID_LOUP_BLANC = "loup-blanc";
export const ROLES_DE_BASE = new Set([ID_VILLAGEOIS, ID_LOUP]);

const PENALITE_PAR_LOUP_SUPPLEMENTAIRE = -2;
const PART_VILLAGE_MIN = 2 / 3;
const LOUPS_MIN_AVEC_CUPIDON = 3;
const AUTRES_LOUPS_MIN_AVEC_LOUP_BLANC = 2;
const PALIERS_CAMPS_SOLO = [
  [16, 2],
  [12, 1],
];
const COMBINAISONS_INTERDITES = [[ID_CUPIDON, ID_ANGE]];

export const EXPERIENCES = ["debutant", "confirme", "expert"];
const PART_ROLES_SPECIAUX = { debutant: 0.35, confirme: 0.55, expert: 0.75 };
const MARGE_PART_ROLES_SPECIAUX = 0.25;
const CIBLE_PAR_EXPERIENCE = { debutant: 2, confirme: 0, expert: -2 };
const POIDS_TIRAGE = { classique: 3, avance: 1, expert: 1 };
const NIVEAUX_PERMIS = {
  debutant: new Set(["classique"]),
  confirme: new Set(["classique", "avance"]),
  expert: new Set(["classique", "avance", "expert"]),
};
const ESSAIS = 600;

export function creerReglages(joueurs, experience, familiarite) {
  if (!Number.isInteger(joueurs) || joueurs < JOUEURS_MIN || joueurs > JOUEURS_MAX) {
    throw new RangeError(`Le nombre de joueurs doit être entre ${JOUEURS_MIN} et ${JOUEURS_MAX}`);
  }
  if (!EXPERIENCES.includes(experience)) throw new RangeError(`Expérience inconnue : ${experience}`);
  if (
    !Number.isInteger(familiarite) ||
    familiarite < FAMILIARITE_MIN ||
    familiarite > FAMILIARITE_MAX
  ) {
    throw new RangeError(
      `La familiarité doit être entre ${FAMILIARITE_MIN} et ${FAMILIARITE_MAX}`,
    );
  }
  return Object.freeze({ joueurs, experience, familiarite, cible: CIBLE_PAR_EXPERIENCE[experience] });
}

export function campsSoloAutorises(joueurs) {
  return PALIERS_CAMPS_SOLO.find(([seuil]) => joueurs >= seuil)?.[1] ?? 0;
}

export function penaliteMeute(nombreDeLoups) {
  return nombreDeLoups > 1 ? PENALITE_PAR_LOUP_SUPPLEMENTAIRE * (nombreDeLoups - 1) : 0;
}

export function plageDeLoups(joueurs) {
  return [Math.max(1, Math.round(joueurs / 5)), Math.max(1, Math.floor(joueurs / 3))];
}

export class Composition {
  constructor(cartes, reglages) {
    this.cartes = Object.freeze([...cartes]);
    this.reglages = reglages;
  }

  get ids() {
    return this.cartes.map((r) => r.id);
  }

  get nombreDeLoups() {
    return this.cartes.filter(compteCommeLoup).length;
  }

  get poidsDesRoles() {
    return this.cartes.reduce((total, r) => total + poids(r), 0);
  }

  get penaliteMeute() {
    return penaliteMeute(this.nombreDeLoups);
  }

  get score() {
    return this.poidsDesRoles + this.penaliteMeute + this.reglages.familiarite;
  }

  get ecart() {
    return this.score - this.reglages.cible;
  }

  decompte() {
    const parId = new Map();
    for (const role of this.cartes) {
      const ligne = parId.get(role.id) ?? { role, nombre: 0 };
      ligne.nombre += 1;
      parId.set(role.id, ligne);
    }
    return [...parId.values()].sort(
      (a, b) =>
        CAMPS.indexOf(a.role.camp) - CAMPS.indexOf(b.role.camp) ||
        a.role.nom.localeCompare(b.role.nom, "fr"),
    );
  }

  avertissements() {
    const { joueurs } = this.reglages;
    const ids = new Set(this.ids);
    const nCartes = this.cartes.length;
    const nLoups = this.nombreDeLoups;
    const messages = [];
    if (nCartes !== joueurs) messages.push(`${nCartes} cartes pour ${joueurs} joueurs.`);
    for (const { role, nombre } of this.decompte()) {
      if (role.unique && nombre > 1) messages.push(`${role.nom} est un rôle unique (${nombre} cartes).`);
      if (role.groupe > 1 && nombre % role.groupe) messages.push(`${role.nom} se joue par ${role.groupe}.`);
    }
    if (nLoups === 0) messages.push("Aucun loup-garou.");
    const nVillage = this.cartes.filter((r) => r.camp === "village").length;
    if (nCartes && nVillage < PART_VILLAGE_MIN * nCartes) {
      messages.push("Moins de 2/3 des rôles sont dans le camp du village.");
    }
    const nSimples = this.ids.filter((id) => id === ID_VILLAGEOIS).length;
    if (nSimples < nLoups) {
      messages.push(`Moins de simples villageois (${nSimples}) que de loups (${nLoups}).`);
    }
    const nSolos = this.cartes.filter(ajouteUnCampSolo).length;
    if (nSolos > campsSoloAutorises(joueurs)) {
      messages.push(
        `${nSolos} camp(s) solo pour ${joueurs} joueurs : 1 dès 12 joueurs, 2 dès 16 (Cupidon compte pour un).`,
      );
    }
    if (ids.has(ID_CUPIDON) && nLoups < LOUPS_MIN_AVEC_CUPIDON) {
      messages.push(`Cupidon demande au moins ${LOUPS_MIN_AVEC_CUPIDON} loups.`);
    }
    if (ids.has(ID_LOUP_BLANC) && nLoups - 1 < AUTRES_LOUPS_MIN_AVEC_LOUP_BLANC) {
      messages.push(
        `Le loup-garou blanc demande au moins ${AUTRES_LOUPS_MIN_AVEC_LOUP_BLANC} autres loups.`,
      );
    }
    const noms = new Map(this.cartes.map((r) => [r.id, r.nom]));
    for (const [a, b] of COMBINAISONS_INTERDITES) {
      if (ids.has(a) && ids.has(b)) messages.push(`Combinaison déconseillée : ${noms.get(a)} et ${noms.get(b)}.`);
    }
    return messages;
  }
}

export function compositionDepuisIds(catalogue, ids, reglages) {
  return new Composition(ids.map((id) => catalogue.get(id)).filter(Boolean), reglages);
}

export class Contraintes {
  constructor(imposes = [], exclus = []) {
    this.imposes = new Set([...imposes].filter((id) => !ROLES_DE_BASE.has(id)));
    this.exclus = new Set([...exclus].filter((id) => !ROLES_DE_BASE.has(id)));
    Object.freeze(this);
  }

  imposer(id) {
    if (ROLES_DE_BASE.has(id)) return this;
    return new Contraintes([...this.imposes, id], [...this.exclus].filter((x) => x !== id));
  }

  exclure(id) {
    if (ROLES_DE_BASE.has(id)) return this;
    return new Contraintes([...this.imposes].filter((x) => x !== id), [...this.exclus, id]);
  }

  liberer(id) {
    return new Contraintes(
      [...this.imposes].filter((x) => x !== id),
      [...this.exclus].filter((x) => x !== id),
    );
  }

  get vide() {
    return !this.imposes.size && !this.exclus.size;
  }
}

function ordrePondere(roles, rng) {
  return roles
    .map((r) => ({ r, cle: rng.random() ** (1 / POIDS_TIRAGE[r.niveau]) }))
    .sort((a, b) => b.cle - a.cle)
    .map(({ r }) => r);
}

function tirer(pioche, rng) {
  const { joueurs, experience } = pioche.reglages;
  const cartesImposees = pioche.imposes.flatMap((r) => Array(r.groupe).fill(r));
  const loupsImposes = cartesImposees.filter((r) => r.camp === "loups");
  const autresImposes = cartesImposees.filter((r) => r.camp !== "loups");

  const nLoups = Math.max(rng.entier(...plageDeLoups(joueurs)), loupsImposes.length);
  const cartes = [...loupsImposes, ...Array(nLoups - loupsImposes.length).fill(pioche.loup)];
  if (!loupsImposes.length && pioche.loupsSpeciaux.length && rng.random() < 0.4) {
    cartes[0] = rng.choisir(pioche.loupsSpeciaux);
  }
  cartes.push(...autresImposes);

  const places = joueurs - nLoups;
  const part = PART_ROLES_SPECIAUX[experience] + rng.uniform(-0.1, MARGE_PART_ROLES_SPECIAUX);
  let pris = autresImposes.length;
  const objectif = Math.max(pris, Math.min(Math.round(places * part), places - nLoups));
  for (const role of ordrePondere(pioche.speciaux, rng)) {
    if (pris + role.groupe <= objectif) {
      cartes.push(...Array(role.groupe).fill(role));
      pris += role.groupe;
    }
  }
  cartes.push(...Array(Math.max(0, joueurs - cartes.length)).fill(pioche.villageois));
  return cartes;
}

export function generer(catalogue, reglages, graine, contraintes = new Contraintes(), essais = ESSAIS) {
  const villageois = catalogue.get(ID_VILLAGEOIS);
  const loup = catalogue.get(ID_LOUP);
  if (!villageois || !loup) {
    throw new Error("Le catalogue doit contenir le simple villageois et le loup-garou");
  }

  const imposes = [...contraintes.imposes].sort().map((id) => catalogue.get(id)).filter(Boolean);
  const idsImposes = new Set(imposes.map((r) => r.id));
  const permis = catalogue
    .filtrer()
    .filter(
      (r) =>
        r.cartesSupplementaires === 0 &&
        NIVEAUX_PERMIS[reglages.experience].has(r.niveau) &&
        !ROLES_DE_BASE.has(r.id) &&
        !contraintes.exclus.has(r.id) &&
        !idsImposes.has(r.id),
    );
  const pioche = {
    reglages,
    villageois,
    loup,
    imposes: [...imposes, ...permis.filter((r) => r.essentiel)],
    loupsSpeciaux: permis.filter((r) => r.camp === "loups"),
    speciaux: permis.filter((r) => r.camp !== "loups" && !r.essentiel),
  };

  const rng = creerAleatoire(graine);
  let meilleure = null;
  let meilleureCle = null;
  for (let i = 0; i < essais; i++) {
    const candidate = new Composition(tirer(pioche, rng), reglages);
    const cle = [candidate.avertissements().length, Math.abs(candidate.ecart)];
    if (!meilleureCle || cle[0] < meilleureCle[0] || (cle[0] === meilleureCle[0] && cle[1] < meilleureCle[1])) {
      meilleure = candidate;
      meilleureCle = cle;
    }
  }
  return meilleure;
}
