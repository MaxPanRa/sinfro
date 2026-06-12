"""Capa de fuentes de vacantes. Cada fuente implementa :class:`JobSource`."""

from .base import Job, JobSource, make_uid
from .remoteok import RemoteOKSource
from .remotive import RemotiveSource
from .weworkremotely import WeWorkRemotelySource
from .hackernews import HackerNewsSource

#: Fuentes del Grupo A (alta frecuencia, sin riesgo de bloqueo).
GROUP_A_SOURCES = [
    RemoteOKSource,
    RemotiveSource,
    WeWorkRemotelySource,
    HackerNewsSource,
]

__all__ = [
    "Job", "JobSource", "make_uid",
    "RemoteOKSource", "RemotiveSource", "WeWorkRemotelySource",
    "HackerNewsSource", "GROUP_A_SOURCES",
]
