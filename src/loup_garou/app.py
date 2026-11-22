import os
import random
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from loup_garou import routes_partie
from loup_garou.composition import (
    JOUEURS_MAX,
    JOUEURS_MIN,
    ROLES_DE_BASE,
    Contraintes,
    Reglages,
    generer,
)
from loup_garou.db import creer_moteur
from loup_garou.roles import Camp, Niveau, catalogue_par_defaut
from loup_garou.web import (
    ICI,
    ExperienceForm,
    FamiliariteForm,
    Joueurs,
    ListeForm,
    templates,
)

URL_BASE_PAR_DEFAUT = "sqlite:///loup-garou.db"


def _vide_vers_none[T](valeur: str | None, type_: type[T]) -> T | None:
    return type_(valeur) if valeur else None


def appliquer_action(contraintes: Contraintes, action: str, nouveau: str | None) -> Contraintes:
    operation, _, role_id = action.partition(":")
    if operation == "ajouter":
        operation, role_id = "imposer", nouveau or ""
    if catalogue_par_defaut().get(role_id) is None:
        return contraintes
    match operation:
        case "imposer":
            return contraintes.imposer(role_id)
        case "exclure":
            return contraintes.exclure(role_id)
        case "liberer":
            return contraintes.liberer(role_id)
    return contraintes


def creer_app(url_base: str | None = None) -> FastAPI:
    app = FastAPI(title="Loup-Garou — assistant du MJ")
    app.state.moteur = creer_moteur(
        url_base or os.environ.get("LOUP_GAROU_DB", URL_BASE_PAR_DEFAUT)
    )
    app.mount("/static", StaticFiles(directory=ICI / "static"), name="static")
    app.include_router(routes_partie.routeur)

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
        imposes: ListeForm = None,
        exclus: ListeForm = None,
        action: Annotated[str, Form()] = "",
        nouveau: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        catalogue = catalogue_par_defaut()
        reglages = Reglages(joueurs, experience, familiarite)
        contraintes = appliquer_action(Contraintes.depuis(imposes, exclus), action, nouveau)
        composition = generer(catalogue, reglages, random.randrange(10**9), contraintes)
        contexte = {
            "reglages": reglages,
            "composition": composition,
            "contraintes": contraintes,
            "avertissements": composition.avertissements(),
            "roles_a_ajouter": [
                r
                for r in catalogue.filtrer()
                if r.id not in ROLES_DE_BASE | contraintes.imposes | set(composition.ids)
            ],
            "ROLES_DE_BASE": ROLES_DE_BASE,
            "nom_du_role": lambda i: r.nom if (r := catalogue.get(i)) else i,
        }
        return templates.TemplateResponse(request, "composer/_resultat.html", contexte)

    return app
