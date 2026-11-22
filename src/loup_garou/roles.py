from enum import StrEnum
from functools import cache
from importlib import resources

import yaml
from pydantic import BaseModel, Field, model_validator


class Camp(StrEnum):
    VILLAGE = "village"
    LOUPS = "loups"
    SOLITAIRE = "solitaire"
    AMBIGU = "ambigu"


class Niveau(StrEnum):
    CLASSIQUE = "classique"
    AVANCE = "avance"
    EXPERT = "expert"


class Extension(StrEnum):
    BASE = "base"
    NOUVELLE_LUNE = "nouvelle_lune"
    PERSONNAGES = "personnages"
    INTERLUDE = "interlude"
    MAISON = "maison"


class Role(BaseModel):
    id: str
    nom: str
    camp: Camp
    extension: Extension
    niveau: Niveau
    unique: bool
    groupe: int = Field(default=1, ge=1)
    poids_min: float
    poids_max: float
    source: str = "estimation"
    est_loup: bool = False
    camp_solo: bool = False
    essentiel: bool = False
    pouvoir: str
    description: str = ""
    ordre_nuit: int | None = None
    premiere_nuit_seulement: bool = False
    cartes_supplementaires: int = Field(default=0, ge=0)
    conseils_mj: str = ""

    @model_validator(mode="after")
    def _poids_ordonnes(self) -> Role:
        if self.poids_min > self.poids_max:
            raise ValueError(f"{self.id}: poids_min > poids_max")
        return self

    @property
    def poids(self) -> float:
        return (self.poids_min + self.poids_max) / 2

    @property
    def compte_comme_loup(self) -> bool:
        return self.camp == Camp.LOUPS or self.est_loup

    @property
    def ajoute_un_camp_solo(self) -> bool:
        return self.camp == Camp.SOLITAIRE or self.camp_solo


class Catalogue:
    def __init__(self, roles: list[Role]) -> None:
        ids = [r.id for r in roles]
        doublons = {i for i in ids if ids.count(i) > 1}
        if doublons:
            raise ValueError(f"Identifiants de rôles en double : {sorted(doublons)}")
        self._roles = {r.id: r for r in roles}

    def __len__(self) -> int:
        return len(self._roles)

    def get(self, role_id: str) -> Role | None:
        return self._roles.get(role_id)

    def filtrer(
        self,
        recherche: str = "",
        camp: Camp | None = None,
        niveau: Niveau | None = None,
    ) -> list[Role]:
        terme = recherche.strip().casefold()
        resultat = [
            r
            for r in self._roles.values()
            if (camp is None or r.camp == camp)
            and (niveau is None or r.niveau == niveau)
            and (not terme or terme in f"{r.nom} {r.pouvoir} {r.description}".casefold())
        ]
        return sorted(resultat, key=lambda r: (list(Camp).index(r.camp), r.nom))

    def ordre_de_nuit(self) -> list[Role]:
        appeles = [r for r in self._roles.values() if r.ordre_nuit is not None]
        return sorted(appeles, key=lambda r: r.ordre_nuit or 0)


def charger_roles(texte_yaml: str) -> Catalogue:
    donnees = yaml.safe_load(texte_yaml)
    return Catalogue([Role.model_validate(d) for d in donnees])


@cache
def catalogue_par_defaut() -> Catalogue:
    texte = resources.files("loup_garou").joinpath("data/roles.yaml").read_text("utf-8")
    return charger_roles(texte)
