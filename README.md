# SinFro · Job Radar

**SinFro** (app: *Job Radar*) es una aplicación de **escritorio para Windows** que
**monitorea vacantes de empleo** mientras la ventana está abierta, las **clasifica
y analiza con IA** (vía OpenCode CLI) y te permite gestionarlas como una **bandeja
de correo**: no vistas en negrita, fondo coloreado según compatibilidad, evaluación
profunda bajo demanda, marcar como aplicada/descartada, y más.

Pensado para un perfil **Full Stack / Frontend** (React, Angular, TypeScript, UX/UI)
con foco en trabajo **remoto** y pago en **USD**, pero todo es configurable.

- **Stack:** Python 3.12 · PySide6 · SQLite · PyInstaller.
- **IA:** *shell-out* a **OpenCode CLI** (`opencode run`), proveedor **OpenCode Go**.
- **Persistencia local:** `%APPDATA%\JobRadar\job_radar.db` (incluye API keys, fuera del repo).

> ⚠️ Es una herramienta personal de búsqueda de empleo. **Nunca** se suben claves al
> repositorio: viven en la base de datos local del usuario.

---

## 1. ¿Cómo funciona?

1. **Monitoreo.** Al pulsar *Comenzar monitoreo*, un *scheduler* (QTimer) consulta
   fuentes de vacantes mientras la app esté abierta:
   - **Grupo A** (cada 20 min, sin riesgo de bloqueo): RemoteOK, Remotive,
     We Work Remotely (RSS) y Hacker News "Who is hiring".
   - **Grupo B** (a las 6:00 y 18:00): JobSpy (LinkedIn + Indeed), Google for Jobs
     (SerpAPI) y OCC Mundial (scraping del HTML de resultados).
2. **Pre-filtro + clasificación preliminar (sin costo de IA).** Cada vacante nueva
   pasa por un *pre-filtro* por palabras clave y una **clasificación semántica local**
   que calcula una compatibilidad preliminar (0–100) según tus keywords, tecnologías,
   ubicación y modalidad. Se guarda en SQLite y se deduplica por hash (título+empresa).
3. **Bandeja.** Las vacantes aparecen en una bandeja tipo correo. El **fondo de cada
   fila** y la **caja de %** indican su estado y compatibilidad de un vistazo
   (ver leyenda en la app). Preliminar = caja gris `¿NN%?`; analizada = caja sólida.
4. **Análisis con IA bajo demanda.** Al abrir una vacante, se genera un **análisis**
   con OpenCode (rápido o profundo, según Ajustes) que se **cachea**. El popup tiene
   dos pestañas: **Análisis** (informe embellecido con secciones, %, brechas ✅/❌/⚠️)
   y **Vacante original**. Botón dinámico: *Análisis Profundo* ↔ *Volver a Analizar*.
5. **Gestión.** *Aplicar* abre la vacante en el navegador y te pregunta si aplicaste;
   *Descartar* la tiñe de rojo (no la borra); los estados se guardan localmente.

Toda llamada de red/IA corre en hilos (`QThreadPool`): **la UI nunca se congela**.
Si una fuente falla, la app sigue y lo reporta en la barra de estado.

---

## 2. Requisitos

- **Python ≥ 3.11** (probado en 3.12.1).
- **OpenCode CLI** instalado y en el PATH → comprueba con `opencode --version`.
  Instalación: <https://opencode.ai> (o `npm i -g opencode-ai`).
- **Windows 10/11**.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 3. IA: OpenCode y modelos (lo más importante)

La app **no llama a ninguna API de IA directamente**: ejecuta el binario de
**OpenCode CLI** como subproceso (`opencode run --model <id> "<prompt>"`) y parsea su
salida. El proveedor por defecto es **OpenCode Go** (suscripción de pago de OpenCode).

### Configurar OpenCode Go

1. Inicia sesión en <https://opencode.ai> y **suscríbete a Go** si aún no lo estás.
2. Crea/copía tu **API key** de OpenCode Go.
3. En la app: menú **Ajustes → "API key de OpenCode Go"** y pégala.
   La app la **inyecta** como variable de entorno `OPENCODE_API_KEY` (alias
   `OPENCODE_ZEN_API_KEY`) al ejecutar `opencode run`. Si ya hiciste
   `opencode auth login`, esas credenciales también se respetan.

### Modelos (configurables en Ajustes)

El formato real del CLI es `opencode-go/<id>` para la suscripción Go y
`opencode/<id>-free` para los gratuitos. Defaults:

| Uso | Modelo | Cuándo corre |
|-----|--------|--------------|
| Clasificación / análisis rápido | `opencode-go/deepseek-v4-flash` | barato, bajo demanda |
| Análisis profundo | `opencode-go/kimi-k2.6` | capaz, bajo demanda + cacheado |
| Respaldo **gratuito** | `opencode/deepseek-v4-flash-free` | si se agota el saldo Go |

> 💡 **El saldo de Go se mide en dólares, no en número de requests.** Por eso la
> app evita llamadas innecesarias (clasificación preliminar es local, el análisis IA
> solo corre al abrir una vacante y se cachea). Si ves *"saldo insuficiente"*, recarga
> en tu panel de billing de OpenCode o activa el **toggle de modelo gratuito** en Ajustes.

Lista de modelos disponibles con tu key:

```powershell
opencode models
```

---

## 4. APIs y fuentes externas

| Fuente | API / método | Key requerida | Notas |
|--------|--------------|---------------|-------|
| RemoteOK | JSON público | No | `https://remoteok.com/api` |
| Remotive | JSON público | No | categoría software-dev |
| We Work Remotely | RSS | No | feed de programación remota |
| Hacker News | API Algolia | No | story "Who is hiring" + comentarios |
| LinkedIn / Indeed | **JobSpy** | No | modo invitado, pocas páginas |
| Google for Jobs | **SerpAPI** | **Sí** | cuota gratuita 250 búsquedas/mes |
| OCC Mundial | scraping HTML | No | parsea las tarjetas de resultados |

### SerpAPI (opcional, Google for Jobs)

1. Crea una cuenta gratuita en <https://serpapi.com> (incluye **250 búsquedas/mes**).
2. Copia tu **API key** del dashboard.
3. Pégala en **Ajustes → "API key de SerpAPI"**.

En Ajustes verás las **búsquedas restantes del mes** (`X/250`) y un botón
**"Buscar ahora (X/250)"** para lanzar una búsqueda de Google for Jobs al instante.
La app lleva el contador mensual en la base de datos y deja de llamar al agotar la cuota.

### Proxy (preparado, desactivado)

La capa de red soporta un **proxy** (p. ej. un VPS para enmascarar IP) ya integrado
pero **desactivado** por defecto. Se activa en **Ajustes → proxy** (host:puerto).

---

## 5. Ejecutar (desarrollo)

```powershell
.\.venv\Scripts\python.exe run_job_radar.py
```

En **Ajustes** hay un *flag de desarrollo* que reduce el intervalo del Grupo A a
1 minuto para probar el monitoreo rápidamente.

---

## 6. Generar el ejecutable (PyInstaller)

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean job_radar.spec
```

El resultado queda en **`dist\JobRadar\JobRadar.exe`** (one-folder, sin consola).

**¿Por qué one-folder y no one-file?** Con PySide6, *one-file* re-extrae Qt a un
temporal en cada arranque → inicios lentos y falsos positivos de antivirus.
*One-folder* arranca rápido y es más estable. Para distribuir, comprime
`dist\JobRadar\` completa. La base de datos vive en `%APPDATA%\JobRadar\`, **fuera**
del ejecutable, así que actualizar el binario no borra tus datos.

---

## 7. Arquitectura

```
job_radar/
  config.py            Constantes, modelos por defecto, estados de México
  db/database.py       SQLite thread-safe (jobs, evaluations, settings, quotas, runs…)
  sources/             Una clase por fuente (interfaz común JobSource)
    remoteok / remotive / weworkremotely / hackernews   (Grupo A)
    jobspy_source / serpapi_source / occ                (Grupo B)
  ai/                  Shell-out a OpenCode con parser tolerante
    opencode_client.py Subprocess + inyección de key + parser JSON laxo
    evaluator.py       Análisis rápido y profundo (plantillas)
  profile/cv_parser.py Extracción de CV (PDF/DOCX) + análisis IA
  scheduler/           QTimer Grupo A + ventanas Grupo B
  ui/                  PySide6: ventana, columnas, bandeja, popup, ajustes, tema
  service.py           Orquestación sin Qt (DB + fuentes + IA + clasificación)
  main.py              Punto de entrada
run_job_radar.py       Lanzador (dev y PyInstaller)
job_radar.spec         Spec de PyInstaller
```

### Nota técnica (gotcha de OpenCode)

`opencode run` también lee de **stdin**. Al lanzarlo como subprocess hereda un pipe
abierto y **se cuelga** esperando EOF. La app lo evita con `stdin=DEVNULL`. El parser
es tolerante a códigos ANSI, fences markdown y JSON con llaves sin comillas.

---

## 8. Privacidad

- Las API keys se guardan en SQLite local (`%APPDATA%\JobRadar\`) y **nunca** en logs
  ni en el repositorio.
- `.gitignore` excluye `*.db`, `.env`, `secrets.json`, `dist/`, `build/` y notas
  internas de desarrollo.

## 9. Estado del proyecto

Funcional de punta a punta: monitoreo, clasificación preliminar local, análisis IA
(rápido/profundo) con OpenCode, bandeja con estados, fuentes A y B, y empaquetado.
SerpAPI requiere tu key; OpenCode Go requiere saldo (o usa el modelo gratuito).
#   s i n f r o  
 