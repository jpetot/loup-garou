from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import JSON, Column
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine


def _maintenant() -> datetime:
    return datetime.now(UTC)


class Personne(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(index=True, unique=True)


class Partie(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cree_le: datetime = Field(default_factory=_maintenant)
    joueurs: int
    experience: str
    familiarite: int
    cartes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    statut: str = "preparation"
    numero: int = 1
    phase: str = "nuit"
    gagnant: str | None = None
    termine_le: datetime | None = None


class Participation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    partie_id: int = Field(foreign_key="partie.id", index=True)
    personne_id: int = Field(foreign_key="personne.id", index=True)
    place: int
    role_id: str
    vivant: bool = True
    marqueurs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    notes: str = ""


class Evenement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    partie_id: int = Field(foreign_key="partie.id", index=True)
    cree_le: datetime = Field(default_factory=_maintenant)
    numero: int
    phase: str
    texte: str


def creer_moteur(url: str) -> Engine:
    moteur = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(moteur)
    return moteur


def _session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.moteur) as session:
        yield session


SessionDep = Annotated[Session, Depends(_session)]
