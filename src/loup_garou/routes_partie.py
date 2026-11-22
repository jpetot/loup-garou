import random
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import col, select

from loup_garou import partie as jeu
from loup_garou.composition import Reglages
from loup_garou.db import Partie, SessionDep
from loup_garou.roles import catalogue_par_defaut
from loup_garou.web import ExperienceForm, FamiliariteForm, Joueurs, ListeForm, templates

routeur = APIRouter(prefix="/parties")


def _partie(session: SessionDep, partie_id: int) -> Partie:
    partie = session.get(Partie, partie_id)
    if partie is None:
        raise HTTPException(status_code=404, detail="Partie inconnue")
    return partie


def _joueur(liste: list[jeu.Joueur], joueur_id: int) -> jeu.Joueur:
    for joueur in liste:
        if joueur.id == joueur_id:
            return joueur
    raise HTTPException(status_code=404, detail="Joueur inconnu")


def _rediriger(request: Request, url: str) -> Response:
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


def _rendre_tableau(
    request: Request,
    session: SessionDep,
    partie: Partie,
    rappel: str | None = None,
    complet: bool = False,
) -> HTMLResponse:
    catalogue = catalogue_par_defaut()
    liste = jeu.joueurs(session, partie, catalogue)
    rappels = ([rappel] if rappel else []) + jeu.rappels(liste)
    vivants = [j for j in liste if j.vivant]
    contexte = {
        "partie": partie,
        "joueurs": liste,
        "appels": jeu.appels_de_la_nuit(partie.numero, liste, catalogue),
        "rappels": rappels,
        "journal": jeu.journal(session, partie),
        "nb_vivants": len(vivants),
        "nb_loups_vivants": sum(j.est_loup for j in vivants),
        "muets": [j for j in vivants if "muet" in j.marqueurs],
        "marques": [j for j in vivants if "marqué" in j.marqueurs],
    }
    gabarit = "parties/tableau.html" if complet else "parties/_tableau.html"
    return templates.TemplateResponse(request, gabarit, contexte)


@routeur.get("", response_class=HTMLResponse)
def liste_parties(request: Request, session: SessionDep) -> HTMLResponse:
    parties = session.exec(select(Partie).order_by(col(Partie.id).desc())).all()
    return templates.TemplateResponse(request, "parties/liste.html", {"parties": parties})


@routeur.post("")
def creer_partie(
    request: Request,
    session: SessionDep,
    joueurs: Joueurs,
    experience: ExperienceForm,
    familiarite: FamiliariteForm,
    roles: ListeForm = None,
) -> Response:
    try:
        partie = jeu.creer_partie(session, Reglages(joueurs, experience, familiarite), roles or [])
    except jeu.ErreurPartie as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    return _rediriger(request, f"/parties/{partie.id}/preparation")


def _rendre_preparation(
    request: Request,
    session: SessionDep,
    partie: Partie,
    noms: list[str],
    roles: list[str],
    erreur: str | None = None,
) -> HTMLResponse:
    catalogue = catalogue_par_defaut()
    distincts = sorted(
        set(partie.cartes), key=lambda i: catalogue.filtrer().index(catalogue.get(i))
    )
    contexte = {
        "partie": partie,
        "places": list(zip(noms, roles, strict=True)),
        "roles_disponibles": [catalogue.get(i) for i in distincts],
        "compte": {i: partie.cartes.count(i) for i in distincts},
        "noms_connus": jeu.noms_connus(session),
        "erreur": erreur,
    }
    statut = 422 if erreur else 200
    return templates.TemplateResponse(
        request, "parties/preparation.html", contexte, status_code=statut
    )


@routeur.get("/{partie_id}/preparation", response_class=HTMLResponse)
def page_preparation(request: Request, session: SessionDep, partie_id: int) -> Response:
    partie = _partie(session, partie_id)
    if partie.statut != jeu.Statut.PREPARATION:
        return RedirectResponse(f"/parties/{partie_id}", status_code=303)
    vides = [""] * partie.joueurs
    return _rendre_preparation(request, session, partie, vides, vides)


@routeur.post("/{partie_id}/preparation", response_class=HTMLResponse)
def valider_preparation(
    request: Request,
    session: SessionDep,
    partie_id: int,
    noms: ListeForm = None,
    roles: ListeForm = None,
    action: Annotated[str, Form()] = "valider",
) -> Response:
    partie = _partie(session, partie_id)
    noms = (noms or []) + [""] * (partie.joueurs - len(noms or []))
    roles = (roles or []) + [""] * (partie.joueurs - len(roles or []))
    if action == "hasard":
        tirage = jeu.attribuer_au_hasard(partie.cartes, random.Random())
        return _rendre_preparation(request, session, partie, noms, tirage)
    try:
        jeu.demarrer(session, partie, noms, roles)
    except jeu.ErreurPartie as erreur:
        session.rollback()
        return _rendre_preparation(request, session, partie, noms, roles, str(erreur))
    return RedirectResponse(f"/parties/{partie_id}", status_code=303)


@routeur.get("/{partie_id}", response_class=HTMLResponse)
def page_tableau(request: Request, session: SessionDep, partie_id: int) -> Response:
    partie = _partie(session, partie_id)
    if partie.statut == jeu.Statut.PREPARATION:
        return RedirectResponse(f"/parties/{partie_id}/preparation", status_code=303)
    return _rendre_tableau(request, session, partie, complet=True)


def _action[T](fonction: Callable[[], T]) -> T:
    try:
        return fonction()
    except jeu.ErreurPartie as erreur:
        raise HTTPException(status_code=409, detail=str(erreur)) from erreur


@routeur.post("/{partie_id}/joueurs/{joueur_id}/vivant", response_class=HTMLResponse)
def basculer_vivant(
    request: Request, session: SessionDep, partie_id: int, joueur_id: int
) -> HTMLResponse:
    partie = _partie(session, partie_id)
    joueur = _joueur(jeu.joueurs(session, partie, catalogue_par_defaut()), joueur_id)
    rappel = _action(lambda: jeu.basculer_vivant(session, partie, joueur))
    return _rendre_tableau(request, session, partie, rappel)


@routeur.post("/{partie_id}/joueurs/{joueur_id}/marqueur", response_class=HTMLResponse)
def basculer_marqueur(
    request: Request,
    session: SessionDep,
    partie_id: int,
    joueur_id: int,
    marqueur: Annotated[str, Form()],
) -> HTMLResponse:
    partie = _partie(session, partie_id)
    joueur = _joueur(jeu.joueurs(session, partie, catalogue_par_defaut()), joueur_id)
    _action(lambda: jeu.basculer_marqueur(session, partie, joueur, marqueur))
    return _rendre_tableau(request, session, partie)


@routeur.post("/{partie_id}/joueurs/{joueur_id}/notes")
def noter(
    session: SessionDep, partie_id: int, joueur_id: int, notes: Annotated[str, Form()] = ""
) -> Response:
    partie = _partie(session, partie_id)
    joueur = _joueur(jeu.joueurs(session, partie, catalogue_par_defaut()), joueur_id)
    jeu.noter(session, joueur, notes)
    return Response(status_code=204)


@routeur.post("/{partie_id}/phase", response_class=HTMLResponse)
def changer_de_phase(request: Request, session: SessionDep, partie_id: int) -> HTMLResponse:
    partie = _partie(session, partie_id)
    liste = jeu.joueurs(session, partie, catalogue_par_defaut())
    _action(lambda: jeu.changer_de_phase(session, partie, liste))
    return _rendre_tableau(request, session, partie)


@routeur.post("/{partie_id}/journal", response_class=HTMLResponse)
def ajouter_au_journal(
    request: Request, session: SessionDep, partie_id: int, texte: Annotated[str, Form()] = ""
) -> HTMLResponse:
    partie = _partie(session, partie_id)
    jeu.ajouter_au_journal(session, partie, texte)
    return _rendre_tableau(request, session, partie)


@routeur.post("/{partie_id}/terminer", response_class=HTMLResponse)
def terminer(
    request: Request,
    session: SessionDep,
    partie_id: int,
    gagnant: Annotated[jeu.Gagnant, Form()],
) -> HTMLResponse:
    partie = _partie(session, partie_id)
    _action(lambda: jeu.terminer(session, partie, gagnant))
    return _rendre_tableau(request, session, partie)
