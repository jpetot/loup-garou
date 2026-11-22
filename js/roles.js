import { ROLES } from "./data/roles.js";

export const CAMPS = ["village", "loups", "solitaire", "ambigu"];
export const NIVEAUX = ["classique", "avance", "expert"];
export const EXTENSIONS = ["base", "nouvelle_lune", "personnages", "interlude", "maison"];

const DEFAUTS = {
  unique: false,
  groupe: 1,
  essentiel: false,
  estLoup: false,
  campSolo: false,
  source: "estimation",
  description: "",
  ordreNuit: null,
  premiereNuitSeulement: false,
  nuitMax: null,
  nuitsPaires: false,
  cartesSupplementaires: 0,
  marqueurs: [],
  aLaMort: "",
  conseilsMj: "",
};

export function creerRole(donnees) {
  const role = { ...DEFAUTS, ...donnees };
  if (!CAMPS.includes(role.camp)) throw new Error(`${role.id} : camp inconnu ${role.camp}`);
  if (!NIVEAUX.includes(role.niveau)) throw new Error(`${role.id} : niveau inconnu ${role.niveau}`);
  if (!EXTENSIONS.includes(role.extension)) {
    throw new Error(`${role.id} : extension inconnue ${role.extension}`);
  }
  if (role.poidsMin > role.poidsMax) throw new Error(`${role.id} : poidsMin > poidsMax`);
  if (role.groupe < 1) throw new Error(`${role.id} : groupe < 1`);
  return Object.freeze({ ...role, marqueurs: Object.freeze([...role.marqueurs]) });
}

export const poids = (role) => (role.poidsMin + role.poidsMax) / 2;
export const compteCommeLoup = (role) => role.camp === "loups" || role.estLoup;
export const ajouteUnCampSolo = (role) => role.camp === "solitaire" || role.campSolo;

export function appeleLaNuit(role, numero) {
  if (role.ordreNuit === null) return false;
  if (role.premiereNuitSeulement && numero > 1) return false;
  if (role.nuitMax !== null && numero > role.nuitMax) return false;
  return !(role.nuitsPaires && numero % 2);
}

const comparerNoms = (a, b) => a.nom.localeCompare(b.nom, "fr");

export class Catalogue {
  #roles;

  constructor(roles) {
    const ids = roles.map((r) => r.id);
    const doublons = [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
    if (doublons.length) throw new Error(`Identifiants de rôles en double : ${doublons.sort()}`);
    this.#roles = new Map(roles.map((r) => [r.id, r]));
  }

  get taille() {
    return this.#roles.size;
  }

  get(id) {
    return this.#roles.get(id) ?? null;
  }

  filtrer({ recherche = "", camp = null, niveau = null } = {}) {
    const terme = recherche.trim().toLocaleLowerCase("fr");
    return [...this.#roles.values()]
      .filter(
        (r) =>
          (!camp || r.camp === camp) &&
          (!niveau || r.niveau === niveau) &&
          (!terme ||
            `${r.nom} ${r.pouvoir} ${r.description}`.toLocaleLowerCase("fr").includes(terme)),
      )
      .sort((a, b) => CAMPS.indexOf(a.camp) - CAMPS.indexOf(b.camp) || comparerNoms(a, b));
  }

  ordreDeNuit() {
    return [...this.#roles.values()]
      .filter((r) => r.ordreNuit !== null)
      .sort((a, b) => a.ordreNuit - b.ordreNuit);
  }
}

let parDefaut = null;

export function catalogueParDefaut() {
  parDefaut ??= new Catalogue(ROLES.map(creerRole));
  return parDefaut;
}
