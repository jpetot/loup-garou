const CLE = "loup-garou";
const VERSION = 1;

export class ErreurImport extends Error {}

export function etatVide() {
  return { version: VERSION, personnes: [], parties: [] };
}

function valider(etat) {
  if (
    !etat ||
    etat.version !== VERSION ||
    !Array.isArray(etat.personnes) ||
    !Array.isArray(etat.parties)
  ) {
    throw new ErreurImport("Ce fichier n'est pas une sauvegarde Loup-Garou valide.");
  }
  return etat;
}

export function charger(stockage = globalThis.localStorage) {
  try {
    const texte = stockage?.getItem(CLE);
    return texte ? valider(JSON.parse(texte)) : etatVide();
  } catch {
    return etatVide();
  }
}

export function sauvegarder(etat, stockage = globalThis.localStorage) {
  try {
    stockage.setItem(CLE, JSON.stringify(etat));
    return true;
  } catch {
    return false;
  }
}

export function exporter(etat) {
  return JSON.stringify(etat, null, 2);
}

export function importer(texte) {
  let donnees;
  try {
    donnees = JSON.parse(texte);
  } catch {
    throw new ErreurImport("Ce fichier n'est pas du JSON lisible.");
  }
  return valider(donnees);
}
