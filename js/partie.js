import { ID_LOUP } from "./composition.js";
import { appeleLaNuit, compteCommeLoup } from "./roles.js";

export const MARQUEURS_COMMUNS = {
  amoureux: "❤️",
  protégé: "🛡️",
  charmé: "🎵",
  muet: "🤐",
  marqué: "🐦",
  "devenu loup": "🐺",
  neutralisé: "🚫",
  modèle: "👤",
};
const MARQUEURS_DE_LA_NUIT = new Set(["protégé", "muet", "marqué"]);
const TAILLE_DU_JOURNAL = 50;

export const GAGNANTS = ["village", "loups", "solitaire", "amoureux"];

export class ErreurPartie extends Error {}

const maintenant = () => new Date().toISOString();

export function creerPartie(etat, reglages, cartes) {
  if (cartes.length !== reglages.joueurs) {
    throw new ErreurPartie(`${cartes.length} cartes pour ${reglages.joueurs} joueurs`);
  }
  const partie = {
    id: Math.max(0, ...etat.parties.map((p) => p.id)) + 1,
    creeLe: maintenant(),
    joueurs: reglages.joueurs,
    experience: reglages.experience,
    familiarite: reglages.familiarite,
    cartes: [...cartes],
    statut: "preparation",
    numero: 1,
    phase: "nuit",
    gagnant: null,
    termineLe: null,
    participants: [],
    journal: [],
  };
  etat.parties.push(partie);
  return partie;
}

export function trouverPartie(etat, id) {
  return etat.parties.find((p) => p.id === id) ?? null;
}

export function attribuerAuHasard(cartes, rng) {
  return rng.melanger(cartes);
}

function compter(liste) {
  const compte = new Map();
  for (const x of liste) compte.set(x, (compte.get(x) ?? 0) + 1);
  return compte;
}

function memesCartes(a, b) {
  const ca = compter(a);
  const cb = compter(b);
  return ca.size === cb.size && [...ca].every(([k, n]) => cb.get(k) === n);
}

export function demarrer(etat, partie, noms, roles) {
  const propres = noms.map((n) => (n ?? "").trim());
  if (propres.length !== partie.joueurs || propres.some((n) => !n)) {
    throw new ErreurPartie(`Il faut le nom des ${partie.joueurs} joueurs.`);
  }
  const minuscules = propres.map((n) => n.toLocaleLowerCase("fr"));
  const doublons = [...new Set(propres.filter((_, i) => minuscules.indexOf(minuscules[i]) !== i))];
  if (doublons.length) throw new ErreurPartie(`Noms en double : ${doublons.sort().join(", ")}.`);
  if (!memesCartes(roles, partie.cartes)) {
    throw new ErreurPartie("Les rôles attribués ne correspondent pas à la composition.");
  }
  partie.participants = propres.map((nom, i) => ({
    id: i + 1,
    nom,
    place: i + 1,
    roleId: roles[i],
    vivant: true,
    marqueurs: [],
    notes: "",
  }));
  for (const nom of propres) {
    if (!etat.personnes.some((p) => p.toLocaleLowerCase("fr") === nom.toLocaleLowerCase("fr"))) {
      etat.personnes.push(nom);
    }
  }
  etat.personnes.sort((a, b) => a.localeCompare(b, "fr"));
  partie.statut = "en_cours";
  journaliser(partie, "La partie commence.");
}

export function joueurs(partie, catalogue) {
  return partie.participants.map((p) => {
    const role = catalogue.get(p.roleId);
    if (!role) throw new ErreurPartie(`Rôle inconnu : ${p.roleId}`);
    return { ...p, role, estLoup: compteCommeLoup(role) || p.marqueurs.includes("devenu loup") };
  });
}

export function appelsDeLaNuit(numero, liste, catalogue) {
  const appels = [];
  const loup = catalogue.get(ID_LOUP);
  const loups = liste.filter((j) => j.estLoup);
  if (loup && loups.length && appeleLaNuit(loup, numero)) {
    appels.push({ titre: "Loups-garous", role: loup, joueurs: loups });
  }
  const parRole = new Map();
  for (const j of liste) parRole.set(j.role.id, [...(parRole.get(j.role.id) ?? []), j]);
  for (const [id, porteurs] of parRole) {
    const { role } = porteurs[0];
    if (id !== ID_LOUP && appeleLaNuit(role, numero)) {
      appels.push({ titre: role.nom, role, joueurs: porteurs });
    }
  }
  return appels
    .sort((a, b) => a.role.ordreNuit - b.role.ordreNuit)
    .map((a) => ({
      ...a,
      tousMorts: !a.joueurs.some((j) => j.vivant),
      pouvoirPerdu: a.joueurs.every((j) => j.marqueurs.includes("neutralisé")),
    }));
}

export function rappels(liste) {
  const amoureux = liste.filter((j) => j.marqueurs.includes("amoureux"));
  const morts = amoureux.filter((j) => !j.vivant);
  const vivants = amoureux.filter((j) => j.vivant);
  if (!morts.length || !vivants.length) return [];
  return [`${morts[0].nom} est mort : ${vivants.map((j) => j.nom).join(", ")} meurt de chagrin.`];
}

function journaliser(partie, texte) {
  partie.journal.push({ numero: partie.numero, phase: partie.phase, texte, creeLe: maintenant() });
}

export function journal(partie) {
  return partie.journal.slice(-TAILLE_DU_JOURNAL).reverse();
}

function verifierEnCours(partie) {
  if (partie.statut !== "en_cours") throw new ErreurPartie("La partie n'est pas en cours.");
}

function participant(partie, joueurId) {
  const p = partie.participants.find((x) => x.id === joueurId);
  if (!p) throw new ErreurPartie(`Joueur inconnu : ${joueurId}`);
  return p;
}

export function basculerVivant(partie, joueurId, catalogue) {
  verifierEnCours(partie);
  const p = participant(partie, joueurId);
  const role = catalogue.get(p.roleId);
  p.vivant = !p.vivant;
  if (p.vivant) {
    journaliser(partie, `${p.nom} (${role.nom}) revient en jeu.`);
    return null;
  }
  journaliser(partie, `${p.nom} (${role.nom}) meurt.`);
  return role.aLaMort ? `${p.nom} : ${role.aLaMort}` : null;
}

export function basculerMarqueur(partie, joueurId, marqueur, catalogue) {
  verifierEnCours(partie);
  const p = participant(partie, joueurId);
  const role = catalogue.get(p.roleId);
  if (!(marqueur in MARQUEURS_COMMUNS) && !role.marqueurs.includes(marqueur)) {
    throw new ErreurPartie(`Marqueur inconnu : ${marqueur}`);
  }
  if (p.marqueurs.includes(marqueur)) {
    p.marqueurs = p.marqueurs.filter((m) => m !== marqueur);
    journaliser(partie, `${p.nom} : ${marqueur} retiré.`);
  } else {
    p.marqueurs = [...p.marqueurs, marqueur];
    journaliser(partie, `${p.nom} : ${marqueur}.`);
  }
}

export function noter(partie, joueurId, texte) {
  participant(partie, joueurId).notes = texte;
}

export function ajouterAuJournal(partie, texte) {
  if (texte.trim()) journaliser(partie, texte.trim());
}

export function changerDePhase(partie) {
  verifierEnCours(partie);
  if (partie.phase === "nuit") {
    partie.phase = "jour";
  } else {
    partie.phase = "nuit";
    partie.numero += 1;
    for (const p of partie.participants) {
      p.marqueurs = p.marqueurs.filter((m) => !MARQUEURS_DE_LA_NUIT.has(m));
    }
  }
  journaliser(partie, `Début : ${partie.phase} ${partie.numero}.`);
}

export function terminer(partie, gagnant) {
  verifierEnCours(partie);
  if (!GAGNANTS.includes(gagnant)) throw new ErreurPartie(`Gagnant inconnu : ${gagnant}`);
  partie.statut = "terminee";
  partie.gagnant = gagnant;
  partie.termineLe = maintenant();
  journaliser(partie, `Fin de la partie : victoire ${gagnant}.`);
}
