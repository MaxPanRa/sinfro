"""Capa de fuentes de vacantes. Cada fuente implementa :class:`JobSource`."""

from .base import Job, JobSource, make_uid
from .remoteok import RemoteOKSource
from .remotive import RemotiveSource
from .weworkremotely import WeWorkRemotelySource
from .hackernews import HackerNewsSource
from .jobspy_source import JobSpySource
from .serpapi_source import SerpApiSource
from .jooble_source import JoobleSource
from .ats_source import ATSCompanySource
from .occ import OCCSource

#: Fuentes del Grupo A (alta frecuencia, sin riesgo de bloqueo).
GROUP_A_SOURCES = [
    RemoteOKSource,
    RemotiveSource,
    WeWorkRemotelySource,
    HackerNewsSource,
]

#: Fuentes del Grupo B (ventanas horarias; riesgo de bloqueo/cuota).
#: SerpAPI y JobSpy se instancian con parámetros en tiempo de ejecución.
GROUP_B_SOURCES = [JobSpySource, SerpApiSource, JoobleSource, OCCSource]

__all__ = [
    "Job", "JobSource", "make_uid",
    "RemoteOKSource", "RemotiveSource", "WeWorkRemotelySource",
    "HackerNewsSource", "GROUP_A_SOURCES",
    "JobSpySource", "SerpApiSource", "JoobleSource", "ATSCompanySource",
    "OCCSource", "GROUP_B_SOURCES",
]
