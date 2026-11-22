from pathlib import Path
from typing import Annotated

from fastapi import Form
from fastapi.templating import Jinja2Templates

from loup_garou.composition import (
    FAMILIARITE_MAX,
    FAMILIARITE_MIN,
    JOUEURS_MAX,
    JOUEURS_MIN,
    Experience,
)
from loup_garou.partie import MARQUEURS_COMMUNS, Gagnant
from loup_garou.roles import Camp, Niveau

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
LIBELLES_GAGNANT = {
    Gagnant.VILLAGE: "Village",
    Gagnant.LOUPS: "Loups-garous",
    Gagnant.SOLITAIRE: "Un solitaire",
    Gagnant.AMOUREUX: "Les amoureux",
}
SEUIL_EQUILIBRE = 1.0
templates.env.globals |= {
    "LIBELLES_CAMP": LIBELLES_CAMP,
    "LIBELLES_NIVEAU": LIBELLES_NIVEAU,
    "LIBELLES_EXPERIENCE": LIBELLES_EXPERIENCE,
    "LIBELLES_FAMILIARITE": LIBELLES_FAMILIARITE,
    "LIBELLES_GAGNANT": LIBELLES_GAGNANT,
    "MARQUEURS_COMMUNS": MARQUEURS_COMMUNS,
    "SEUIL_EQUILIBRE": SEUIL_EQUILIBRE,
}

Joueurs = Annotated[int, Form(ge=JOUEURS_MIN, le=JOUEURS_MAX)]
ExperienceForm = Annotated[Experience, Form()]
FamiliariteForm = Annotated[int, Form(ge=FAMILIARITE_MIN, le=FAMILIARITE_MAX)]
ListeForm = Annotated[list[str] | None, Form()]
