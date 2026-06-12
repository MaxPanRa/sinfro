"""Capa de IA: shell-out a OpenCode CLI, clasificación rápida y evaluación profunda."""

from .opencode_client import OpenCodeClient, OpenCodeError, parse_json_loose

__all__ = ["OpenCodeClient", "OpenCodeError", "parse_json_loose"]
