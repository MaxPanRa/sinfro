"""Cliente de OpenCode CLI vía subprocess.

Responsabilidades:
- Ejecutar ``opencode run --model <id> "<prompt>"`` con timeout.
- Inyectar la API key del usuario en el entorno del subprocess
  (``OPENCODE_API_KEY`` + alias ``OPENCODE_ZEN_API_KEY``). Si no hay key,
  respeta las credenciales ya guardadas por OpenCode (``auth.json``).
- Parser tolerante: quita ANSI, fences markdown y la línea header
  ``> build · <modelo>``; extrae el primer bloque ``{...}`` balanceado y repara
  JSON laxo (llaves sin comillas, comillas simples).
- Fallback automático al modelo gratuito si Go responde "saldo insuficiente".

NUNCA bloquea el hilo de UI: el caller debe invocarlo desde un worker.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

#: Regex para quitar secuencias de escape ANSI (colores del CLI).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
#: Líneas de metadata del CLI a descartar (header de build/modelo).
_META_LINE_RE = re.compile(r"^\s*>\s*(build|share|run)\b", re.IGNORECASE)
#: Señales de error de saldo o autenticación en la salida.
_BALANCE_RE = re.compile(r"insufficient balance|out of credits|quota", re.IGNORECASE)
_AUTH_RE = re.compile(r"unauthorized|invalid api key|not authenticated", re.IGNORECASE)


class OpenCodeError(RuntimeError):
    """Error al ejecutar o parsear una llamada a OpenCode."""

    def __init__(self, message: str, *, balance: bool = False, auth: bool = False) -> None:
        super().__init__(message)
        self.balance = balance  # True si es por saldo agotado
        self.auth = auth        # True si es por credenciales


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def clean_cli_output(text: str) -> str:
    """Quita ANSI y líneas de metadata; deja solo la respuesta del modelo."""
    text = strip_ansi(text)
    lines = [ln for ln in text.splitlines() if not _META_LINE_RE.match(ln)]
    return "\n".join(lines).strip()


def _strip_fences(text: str) -> str:
    """Quita fences markdown ```...``` conservando el contenido interior."""
    text = text.strip()
    if text.startswith("```"):
        # Quita la primera línea (``` o ```json) y el cierre.
        parts = text.split("```")
        # El contenido útil suele ser el segundo bloque.
        if len(parts) >= 2:
            inner = parts[1]
            # Quita un posible "json" inicial.
            inner = re.sub(r"^[a-zA-Z]+\n", "", inner.lstrip())
            return inner.strip()
    return text


def _first_json_block(text: str) -> str | None:
    """Extrae el primer objeto ``{...}`` balanceado (ignora llaves en strings)."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


def _repair_json(block: str) -> str:
    """Repara JSON laxo: comillas simples, llaves sin comillas, comas colgantes."""
    s = block
    # Comillas simples → dobles (sólo a nivel estructural simple).
    # Pon comillas a llaves sin comillas:  { ok: ...  ->  { "ok": ...
    s = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*):',
               r'\1"\2"\3:', s)
    # Comillas simples en valores/keys → dobles.
    s = s.replace("'", '"')
    # Quita comas colgantes antes de } o ].
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return s


def parse_json_loose(raw: str) -> dict:
    """Parsea la salida del CLI a dict de forma tolerante.

    Levanta :class:`ValueError` si no logra extraer un objeto JSON.
    """
    text = _strip_fences(clean_cli_output(raw))
    block = _first_json_block(text)
    if block is None:
        raise ValueError("No se encontró un bloque JSON en la salida")
    # Intento directo.
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        pass
    # Intento con reparación.
    repaired = _repair_json(block)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON irreparable: {exc}; bloque={block[:200]!r}") from exc


@dataclass
class OpenCodeClient:
    """Ejecuta prompts contra OpenCode con manejo de key, timeout y fallback."""

    api_key: str = ""
    fast_model: str = "opencode-go/deepseek-v4-flash"
    deep_model: str = "opencode-go/kimi-k2.6"
    free_model: str = "opencode/deepseek-v4-flash-free"
    use_free_fallback: bool = False

    def _env(self) -> dict[str, str]:
        """Entorno del subprocess con la API key inyectada si existe."""
        env = os.environ.copy()
        if self.api_key:
            env["OPENCODE_API_KEY"] = self.api_key
            env["OPENCODE_ZEN_API_KEY"] = self.api_key  # alias aceptado
        return env

    @staticmethod
    def _resolve_binary() -> str:
        """Ruta absoluta del ejecutable de OpenCode (resuelve .cmd en Windows)."""
        path = shutil.which("opencode")
        if not path:
            raise OpenCodeError(
                "No se encontró 'opencode' en el PATH. Instala OpenCode CLI."
            )
        return path

    @staticmethod
    def _subprocess_options() -> dict:
        """Opciones de subprocess para que OpenCode no abra ventanas en Windows."""
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return {
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": startupinfo,
        }

    def run(self, prompt: str, model: str, timeout: int) -> str:
        """Ejecuta una llamada y devuelve la salida cruda (stdout+stderr limpios).

        Aplica fallback al modelo gratuito si el principal falla por saldo y
        ``use_free_fallback`` está activo.
        """
        try:
            return self._run_once(prompt, model, timeout)
        except OpenCodeError as exc:
            if exc.balance and self.use_free_fallback and model != self.free_model:
                # Reintento con el modelo gratuito de respaldo.
                return self._run_once(prompt, self.free_model, timeout)
            raise

    def _run_once(self, prompt: str, model: str, timeout: int) -> str:
        binary = self._resolve_binary()
        cmd = [binary, "run", "--model", model, prompt]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self._env(),
                # CRÍTICO: cerrar stdin. `opencode run` también lee de stdin para
                # anexarlo al mensaje; si hereda un pipe abierto (caso típico al
                # lanzarse desde otro proceso), se cuelga esperando EOF. DEVNULL
                # le da EOF inmediato. No usamos shell=True (seguridad).
                stdin=subprocess.DEVNULL,
                **self._subprocess_options(),
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenCodeError(f"Timeout ({timeout}s) llamando a OpenCode") from exc
        except FileNotFoundError as exc:
            raise OpenCodeError("Ejecutable de OpenCode no encontrado") from exc

        combined = f"{proc.stdout or ''}\n{proc.stderr or ''}"
        # Detección de errores conocidos aunque el exit code sea 0.
        if _BALANCE_RE.search(combined):
            raise OpenCodeError("Saldo insuficiente en OpenCode Go", balance=True)
        if _AUTH_RE.search(combined):
            raise OpenCodeError("Credenciales inválidas o ausentes", auth=True)
        if proc.returncode != 0 and not proc.stdout:
            raise OpenCodeError(
                f"OpenCode salió con código {proc.returncode}: "
                f"{strip_ansi(proc.stderr)[:300]}"
            )
        return proc.stdout or combined

    # -- Conveniencias --------------------------------------------------------

    def run_fast(self, prompt: str, timeout: int = 60) -> str:
        return self.run(prompt, self.fast_model, timeout)

    def run_deep(self, prompt: str, timeout: int = 180) -> str:
        return self.run(prompt, self.deep_model, timeout)
