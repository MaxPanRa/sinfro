"""Capa de fuentes de vacantes. Cada fuente implementa :class:`JobSource`."""

from .base import Job, JobSource, make_uid
from .remoteok import RemoteOKSource
from .remotive import RemotiveSource
from .weworkremotely import WeWorkRemotelySource
from .hackernews import HackerNewsSource
from .jobicy import JobicySource
from .jobspy_source import JobSpySource
from .serpapi_source import SerpApiSource
from .jooble_source import JoobleSource
from .adzuna import AdzunaSource
from .ats_source import ATSCompanySource
from .occ import OCCSource

#: Fuentes del Grupo A (alta frecuencia, sin key, agnósticas de profesión).
GROUP_A_SOURCES = [
    RemoteOKSource,
    RemotiveSource,
    WeWorkRemotelySource,
    HackerNewsSource,
    JobicySource,
]

#: Fuentes del Grupo B (ventanas horarias; riesgo de bloqueo/cuota o key).
GROUP_B_SOURCES = [JobSpySource, SerpApiSource, JoobleSource, AdzunaSource, OCCSource]

__all__ = [
    "Job", "JobSource", "make_uid",
    "RemoteOKSource", "RemotiveSource", "WeWorkRemotelySource",
    "HackerNewsSource", "JobicySource", "GROUP_A_SOURCES",
    "JobSpySource", "SerpApiSource", "JoobleSource", "AdzunaSource",
    "ATSCompanySource", "OCCSource", "GROUP_B_SOURCES",
]
