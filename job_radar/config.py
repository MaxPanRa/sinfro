"""Configuración global y constantes de Job Radar.

Centraliza rutas, valores por defecto y catálogos (estados, modalidades, modelos).
No contiene secretos: las API keys viven en la tabla `settings` de SQLite.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Rutas de la aplicación --------------------------------------------------

#: Carpeta de datos del usuario (persistente entre ejecuciones y empaquetado).
APP_DIR: Path = Path(os.environ.get("APPDATA", Path.home())) / "JobRadar"
APP_DIR.mkdir(parents=True, exist_ok=True)

#: Ruta del archivo SQLite con toda la persistencia.
DB_PATH: Path = APP_DIR / "job_radar.db"

# --- Modelos de IA (defaults; configurables en Ajustes) ----------------------
# OJO: el formato real del CLI es `opencode-go/<id>` para la suscripción Go
# y `opencode/<id>-free` para los gratuitos.

#: Modelo barato para clasificación rápida (corre sobre cada vacante).
DEFAULT_FAST_MODEL = "opencode-go/deepseek-v4-flash"

#: Modelo capaz para la evaluación profunda (bajo demanda, cacheada).
DEFAULT_DEEP_MODEL = "opencode-go/kimi-k2.6"

#: Modelo gratuito de respaldo si se agota el saldo de Go.
DEFAULT_FREE_MODEL = "opencode/deepseek-v4-flash-free"

#: Timeout (segundos) para cada llamada a `opencode run`.
OPENCODE_TIMEOUT_FAST = 60
OPENCODE_TIMEOUT_DEEP = 180

# --- Scheduler ---------------------------------------------------------------

#: Intervalo del Grupo A en minutos (fuentes de alta frecuencia).
GROUP_A_INTERVAL_MIN = 20

#: Ventanas horarias del Grupo B (hora local). Se dispara una vez por ventana/día.
GROUP_B_WINDOWS = [(6, 0, 6, 5), (18, 0, 18, 5)]

#: Cuota gratuita mensual de SerpAPI (búsquedas).
SERPAPI_MONTHLY_QUOTA = 250

# --- Catálogos para la UI ----------------------------------------------------

#: Keywords precargadas como placeholders iniciales.
DEFAULT_KEYWORDS = [
    "angular", "react", "typescript", "frontend",
    "fullstack", "spring", "java", "ux/ui",
]

#: Modalidades de trabajo (multiselección).
MODALIDADES = ["Remoto", "Híbrido", "Presencial"]

#: Opciones de ubicación: especiales + 32 estados de México.
UBICACIONES_ESPECIALES = ["Toda la República", "Solo remoto internacional"]
ESTADOS_MEXICO = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
    "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila", "Colima",
    "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo",
    "Jalisco", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca",
    "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa",
    "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán",
    "Zacatecas",
]
UBICACIONES = UBICACIONES_ESPECIALES + ESTADOS_MEXICO

#: Niveles de inglés (MCER).
NIVELES_INGLES = ["A1", "A2", "B1", "B2", "C1", "C2"]

# --- Perfil base del usuario (se combina con el resumen del CV) ---------------

PERFIL_BASE = (
    "Desarrollador Full Stack con especialización en Frontend, más de 10 años "
    "de experiencia, React, Angular, TypeScript, UX/UI, liderazgo técnico y "
    "trabajo remoto."
)

# --- Settings: claves y valores por defecto ----------------------------------
# Estas claves se guardan en la tabla `settings` (clave→valor texto).

DEFAULT_SETTINGS: dict[str, str] = {
    "opencode_api_key": "",
    "fast_model": DEFAULT_FAST_MODEL,
    "deep_model": DEFAULT_DEEP_MODEL,
    "evaluation_mode": "rapida",  # "rapida" | "profunda"
    "use_free_fallback": "0",
    "free_model": DEFAULT_FREE_MODEL,
    "serpapi_key": "",
    "ubicacion": "Toda la República",
    "nivel_ingles": "B2",
    "salario_monto": "25",
    "salario_moneda": "USD",
    "salario_periodo": "hora",  # "hora" | "mes"
    "proxy_enabled": "0",
    "proxy_host": "",  # formato host:puerto
    "match_threshold": "70",
    "group_b_hour": "6",
    "dev_fast_scheduler": "0",  # flag de desarrollo: intervalo 1 min
}
