import random
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from loup_garou.composition import (
    FAMILIARITE_MAX,
    FAMILIARITE_MIN,
    JOUEURS_MAX,
    JOUEURS_MIN,
    Composition,
    Experience,
    Reglages,
    composition_depuis_ids,
    generer,
)
from loup_garou.roles import Camp, Niveau, catalogue_par_defaut

ICI = Path(__file__).parent
templates = Jinja2Templates(directory=ICI / "templates")

LIBELLES_CAMP = {
    Camp.VILLAGE: "Village",
    Camp.LOUPS: "Loups",
    Camp.SOLITAIRE: "Solitaire",
    Camp.AMBIGU: "Ambigu",
}
LIBELLES_NIVEAU = {
    Niveau.CLASSIQUE: "Classique",
    Niveau.AVANCE: "Avancé",
    Niveau.EXPERT: "Expert",
}
LIBELLES_EXPERIENCE = {
    Experience.DEBUTANT: "Débutants",
    Experience.CONFIRME: "Confirmés",
    Experience.EXPERT: "Experts",
}
LIBELLES_FAMILIARITE = {
    -5: "Ne se sont jamais vus",
    -2: "Se connaissent peu",
    0: "La moitié se connaît",
    2: "Se connaissent bien",
    5: "Jouent souvent ensemble",
}
SEUIL_EQUILIBRE = 1.0
templates.env.globals |= {
    "LIBELLES_CAMP": LIBELLES_CAMP,
    "LIBELLES_NIVEAU": LIBELLES_NIVEAU,
    "LIBELLES_EXPERIENCE": LIBELLES_EXPERIENCE,
    "LIBELLES_FAMILIARITE": LIBELLES_FAMILIARITE,
    "SEUIL_EQUILIBRE": SEUIL_EQUILIBRE,
}

Joueurs = Annotated[int, Form(ge=JOUEURS_MIN, le=JOUEURS_MAX)]
ExperienceForm = Annotated[Experience, Form()]
FamiliariteForm = Annotated[int, Form(ge=FAMILIARITE_MIN, le=FAMILIARITE_MAX)]


def _vide_vers_none[T](valeur: str | None, type_: type[T]) -> T | None:
    return type_(valeur) if valeur else None


def _rendre_resultat(
    request: Request, reglages: Reglages, composition: Composition
) -> HTMLResponse:
    contexte = {
        "reglages": reglages,
        "composition": composition,
        "avertissements": composition.avertissements(),
        "tous_les_roles": catalogue_par_defaut().filtrer(),
    }
    return templates.TemplateResponse(request, "composer/_resultat.html", contexte)


def _appliquer_action(ids: list[str], action: str, nouveau: str | None) -> list[str]:
    catalogue = catalogue_par_defaut()
    operation, _, role_id = action.partition(":")
    if operation == "ajouter":
        operation, role_id = "plus", nouveau or ""
    role = catalogue.get(role_id)
    if role is None:
        return ids
    resultat = list(ids)
    if operation == "plus" and not (role.unique and role_id in resultat):
        resultat.extend([role_id] * role.groupe)
    elif operation == "moins":
        for _ in range(role.groupe):
            if role_id in resultat:
                resultat.remove(role_id)
    return resultat


def creer_app() -> FastAPI:
    app = FastAPI(title="Loup-Garou — assistant du MJ")
    app.mount("/static", StaticFiles(directory=ICI / "static"), name="static")

    @app.get("/")
    def accueil() -> RedirectResponse:
        return RedirectResponse("/composer")

    @app.get("/roles", response_class=HTMLResponse)
    def liste_roles(
        request: Request,
        q: str = "",
        camp: Annotated[str | None, Query()] = None,
        niveau: Annotated[str | None, Query()] = None,
    ) -> HTMLResponse:
        roles = catalogue_par_defaut().filtrer(
            recherche=q,
            camp=_vide_vers_none(camp, Camp),
            niveau=_vide_vers_none(niveau, Niveau),
        )
        contexte = {"roles": roles, "q": q, "camp": camp or "", "niveau": niveau or ""}
        gabarit = "roles/_cartes.html" if request.headers.get("HX-Request") else "roles/liste.html"
        return templates.TemplateResponse(request, gabarit, contexte)

    @app.get("/roles/{role_id}", response_class=HTMLResponse)
    def detail_role(request: Request, role_id: str) -> HTMLResponse:
        role = catalogue_par_defaut().get(role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="Rôle inconnu")
        return templates.TemplateResponse(request, "roles/detail.html", {"role": role})

    @app.get("/nuit", response_class=HTMLResponse)
    def ordre_nuit(request: Request) -> HTMLResponse:
        roles = catalogue_par_defaut().ordre_de_nuit()
        return templates.TemplateResponse(request, "nuit.html", {"roles": roles})

    @app.get("/composer", response_class=HTMLResponse)
    def page_composer(request: Request) -> HTMLResponse:
        contexte = {"joueurs_min": JOUEURS_MIN, "joueurs_max": JOUEURS_MAX}
        return templates.TemplateResponse(request, "composer/page.html", contexte)

    @app.post("/composer/generer", response_class=HTMLResponse)
    def generer_composition(
        request: Request,
        joueurs: Joueurs,
        experience: ExperienceForm,
        familiarite: FamiliariteForm,
    ) -> HTMLResponse:
        reglages = Reglages(joueurs, experience, familiarite)
        composition = generer(catalogue_par_defaut(), reglages, graine=random.randrange(10**9))
        return _rendre_resultat(request, reglages, composition)

    @app.post("/composer/modifier", response_class=HTMLResponse)
    def modifier_composition(
        request: Request,
        joueurs: Joueurs,
        experience: ExperienceForm,
        familiarite: FamiliariteForm,
        action: Annotated[str, Form()],
        roles: Annotated[list[str] | None, Form()] = None,
        nouveau: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        reglages = Reglages(joueurs, experience, familiarite)
        ids = _appliquer_action(roles or [], action, nouveau)
        composition = composition_depuis_ids(catalogue_par_defaut(), ids, reglages)
        return _rendre_resultat(request, reglages, composition)

    return app


app = creer_app()
