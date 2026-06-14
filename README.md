<div align="center">

# 🛰️ SinFro · Job Radar

**Monitorea, clasifica y analiza vacantes de empleo con IA — directo desde tu escritorio.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![OpenCode](https://img.shields.io/badge/IA-OpenCode%20CLI-000000)](https://opencode.ai/)
[![Platform](https://img.shields.io/badge/OS-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](#)

</div>

**SinFro** (app: *Job Radar*) es una aplicación de **escritorio para Windows** que
**monitorea vacantes de empleo** mientras la ventana está abierta, las **clasifica y
analiza con IA** (vía OpenCode CLI) y te permite gestionarlas como una **bandeja de
correo**: no vistas en negrita, fondo coloreado según compatibilidad, análisis profundo
bajo demanda, y marcar como aplicada/descartada.

> Pensado para un perfil **Full Stack / Frontend** (React · Angular · TypeScript · UX/UI)
> con foco en trabajo **remoto** y pago en **USD** — pero todo es configurable.

---

## ✨ Características

- 🔎 **7 fuentes de vacantes** (RemoteOK, Remotive, We Work Remotely, Hacker News,
  LinkedIn, Indeed, Google for Jobs y OCC Mundial).
- 🧠 **Clasificación preliminar local** (sin costo de IA) + **análisis IA** bajo demanda.
- 📬 **Bandeja tipo correo** con heatmap de compatibilidad y estados (aplicada / vista / descartada).
- 📄 **Informe embellecido** con secciones, porcentajes coloreados y brechas ✅ ❌ ⚠️.
- ⏱️ **Scheduler** que corre solo mientras la app está abierta (nunca congela la UI).
- 🔐 **Privacidad local**: tus claves y datos viven en tu PC, nunca en el repo.

---

## 📑 Tabla de contenido

1. [¿Cómo funciona?](#-cómo-funciona)
2. [Requisitos e instalación](#-requisitos-e-instalación)
3. [IA: OpenCode y modelos](#-ia-opencode-y-modelos-lo-más-importante)
4. [APIs y fuentes externas](#-apis-y-fuentes-externas)
5. [Ejecutar](#-ejecutar-desarrollo)
6. [Generar el ejecutable](#-generar-el-ejecutable-pyinstaller)
7. [Arquitectura](#-arquitectura)
8. [Privacidad](#-privacidad)

---

## 🔄 ¿Cómo funciona?

| Paso | Qué ocurre |
|:----:|------------|
| **1. Monitoreo** | Un *scheduler* (QTimer) consulta las fuentes mientras la app está abierta. **Grupo A** (cada 20 min): RemoteOK, Remotive, We Work Remotely, Hacker News. **Grupo B** (6:00 y 18:00): JobSpy (LinkedIn + Indeed), SerpAPI (Google for Jobs) y OCC Mundial. |
| **2. Clasificación preliminar** | Cada vacante pasa un *pre-filtro* por keywords y una **clasificación semántica local** (0–100) según tus keywords, tecnologías, ubicación y modalidad. Sin costo de IA. Se deduplica por hash (título + empresa). |
| **3. Bandeja** | Las vacantes se listan tipo correo. El **fondo de la fila** y la **caja de %** muestran estado y compatibilidad de un vistazo. Preliminar = caja gris `¿NN%?`; analizada = caja sólida coloreada. |
| **4. Análisis IA** | Al abrir una vacante se genera un **análisis** (rápido o profundo, según Ajustes) con OpenCode, y se **cachea**. Popup con pestañas **Análisis** y **Vacante original**, y botón *Análisis Profundo* ↔ *Volver a Analizar*. |
| **5. Gestión** | *Aplicar* abre la vacante y te pregunta si aplicaste; *Descartar* la tiñe de rojo (no la borra). Todo se guarda localmente. |

> ⚙️ Toda llamada de red/IA corre en hilos (`QThreadPool`): **la UI nunca se congela**.
> Si una fuente falla, la app sigue y lo reporta en la barra de estado.

---

## ⬇️ Descargas (sin instalar nada)

¿No quieres compilar? Descarga el binario ya listo desde
**[Releases](https://github.com/MaxPanRa/sinfro/releases)**:

- **Windows** → `Sinfro-Windows.zip` → descomprime y ejecuta `Sinfro.exe`.
- **macOS** → `Sinfro-macOS.zip` → descomprime y ejecuta `Sinfro`.

No necesitas Python ni compilar. (Solo requieres **OpenCode CLI** para la parte de
IA.) Como la app no está firmada, la primera vez Windows (SmartScreen) o macOS
(Gatekeeper) pedirán confirmar: *"Más información → Ejecutar de todos modos"* /
clic derecho → *Abrir*.

> Los binarios se generan automáticamente con GitHub Actions en cada *release*.

---

## 🛠️ Requisitos e instalación (para desarrollar/compilar)

| Requisito | Detalle |
|-----------|---------|
| **Python ≥ 3.11** | Probado en 3.12.1 |
| **OpenCode CLI** | En el PATH (`opencode --version`). Instala desde [opencode.ai](https://opencode.ai) o `npm i -g opencode-ai` |
| **SO** | Windows 10/11 o **macOS** (también corre en Linux) |

<details open>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
</details>

<details>
<summary><b>🍎 macOS / 🐧 Linux (bash)</b></summary>

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```
> En macOS, si `python3` no está, instálalo con `brew install python` y Node (para
> OpenCode) con `brew install node`.
</details>

---

## 🤖 IA: OpenCode y modelos (lo más importante)

La app **no llama a ninguna API de IA directamente**: ejecuta el binario de
**OpenCode CLI** como subproceso (`opencode run --model <id> "<prompt>"`) y parsea su
salida. El proveedor por defecto es **OpenCode Go** (suscripción de pago de OpenCode).

### 🔑 Configurar OpenCode Go

1. Inicia sesión en [opencode.ai](https://opencode.ai) y **suscríbete a Go**.
2. Crea/copia tu **API key** de OpenCode Go.
3. En la app: **Ajustes → "API key de OpenCode Go"** y pégala. La app la **inyecta**
   como `OPENCODE_API_KEY` (alias `OPENCODE_ZEN_API_KEY`) al ejecutar `opencode run`.
   Si ya hiciste `opencode auth login`, esas credenciales también se respetan.

### 🧩 Modelos (configurables en Ajustes)

El formato real del CLI es `opencode-go/<id>` (Go) y `opencode/<id>-free` (gratuitos):

| Uso | Modelo por defecto | Cuándo corre |
|-----|--------------------|--------------|
| 🟢 Clasificación / análisis rápido | `opencode-go/deepseek-v4-flash` | barato, bajo demanda |
| 🔵 Análisis profundo | `opencode-go/kimi-k2.6` | capaz, bajo demanda + cacheado |
| ⚪ Respaldo **gratuito** | `opencode/deepseek-v4-flash-free` | si se agota el saldo Go |

> 💡 **El saldo de Go se mide en dólares, no en número de requests.** Por eso la
> clasificación preliminar es **local** y el análisis IA solo corre al abrir una
> vacante (y se cachea). Si ves *"saldo insuficiente"*, recarga tu billing de OpenCode
> o activa el **modelo gratuito de respaldo** en Ajustes.

```powershell
opencode models   # lista los modelos disponibles con tu key
```

---

## 🌐 APIs y fuentes externas

| Fuente | API / método | Key | Notas |
|--------|--------------|:---:|-------|
| RemoteOK | JSON público | — | `remoteok.com/api` |
| Remotive | JSON público | — | categoría software-dev |
| We Work Remotely | RSS | — | feed de programación remota |
| Hacker News | API Algolia | — | story *"Who is hiring"* + comentarios |
| LinkedIn / Indeed | **JobSpy** | — | modo invitado, pocas páginas |
| Google for Jobs | **SerpAPI** | ✅ | cuota gratuita **250 búsquedas/mes** |
| OCC Mundial | scraping HTML | — | parsea las tarjetas de resultados |

### 🔍 SerpAPI (opcional, Google for Jobs)

1. Crea una cuenta gratuita en [serpapi.com](https://serpapi.com) (**250 búsquedas/mes**).
2. Copia tu **API key** del dashboard.
3. Pégala en **Ajustes → "API key de SerpAPI"**.

En Ajustes verás las **búsquedas restantes** (`X/250`) y un botón
**"Buscar ahora (X/250)"** para lanzar una búsqueda al instante. La app lleva el
contador mensual en la base de datos y se detiene al agotar la cuota.

### 🛡️ Proxy (preparado, desactivado)

La capa de red soporta un **proxy** (p. ej. un VPS para enmascarar IP), integrado pero
**desactivado** por defecto. Se activa en **Ajustes → proxy** (host:puerto).

---

## ▶️ Ejecutar (desarrollo)

**🪟 Windows (PowerShell):**
```powershell
.\.venv\Scripts\python.exe run_job_radar.py
```

**🍎 macOS / 🐧 Linux (bash):**
```bash
./.venv/bin/python run_job_radar.py
# o, tras dar permisos, doble clic / ejecutar el lanzador:
chmod +x run_job_radar.command && ./run_job_radar.command
```

> En **Ajustes** hay un *flag de desarrollo* que baja el intervalo del Grupo A a
> 1 minuto para probar el monitoreo rápido.
>
> 📁 La base de datos y tus claves se guardan en `%APPDATA%\JobRadar\` (Windows) o
> `~/JobRadar/` (macOS / Linux), **fuera** del repositorio.

---

## 📦 Generar el ejecutable (PyInstaller)

**🪟 Windows (PowerShell):**
```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean job_radar.spec
```
Resultado: **`dist\Sinfro\Sinfro.exe`** (one-folder, sin consola).

**🍎 macOS (bash):**
```bash
./.venv/bin/python -m pip install pyinstaller
./.venv/bin/python -m PyInstaller --noconfirm --clean job_radar.spec
```
Resultado: **`dist/Sinfro/Sinfro`** (ejecútalo con `./dist/Sinfro/Sinfro`).

> **¿Por qué one-folder y no one-file?** Con PySide6, *one-file* re-extrae Qt a un
> temporal en cada arranque → inicios lentos y falsos positivos de antivirus.
> *One-folder* arranca rápido y es más estable. La base de datos vive en
> `%APPDATA%\JobRadar\` (Windows) o `~/JobRadar/` (macOS), **fuera** del ejecutable,
> así que actualizar el binario no borra tus datos.
>
> 🍎 *Nota macOS:* el ícono `.ico` aplica en Windows; para un ícono nativo en el
> `.app` de macOS habría que generar un `.icns` (pendiente, no afecta el funcionamiento).

---

## 🏗️ Arquitectura

```
job_radar/
├─ config.py            Constantes, modelos por defecto, estados de México
├─ db/database.py       SQLite thread-safe (jobs, evaluations, settings, quotas, runs…)
├─ sources/             Una clase por fuente (interfaz común JobSource)
│  ├─ remoteok · remotive · weworkremotely · hackernews     (Grupo A)
│  └─ jobspy_source · serpapi_source · occ                  (Grupo B)
├─ ai/                  Shell-out a OpenCode con parser tolerante
│  ├─ opencode_client.py   Subprocess + inyección de key + parser JSON laxo
│  └─ evaluator.py         Análisis rápido y profundo (plantillas)
├─ profile/cv_parser.py Extracción de CV (PDF/DOCX) + análisis IA
├─ scheduler/           QTimer Grupo A + ventanas Grupo B
├─ ui/                  PySide6: ventana, bandeja, popup, ajustes, tema
├─ service.py           Orquestación sin Qt (DB + fuentes + IA + clasificación)
└─ main.py              Punto de entrada
run_job_radar.py        Lanzador (dev y PyInstaller)
job_radar.spec          Spec de PyInstaller
```

> **Nota técnica (gotcha de OpenCode):** `opencode run` también lee de **stdin**; al
> lanzarlo como subprocess hereda un pipe abierto y **se cuelga** esperando EOF. La app
> lo evita con `stdin=DEVNULL`. El parser tolera ANSI, fences markdown y JSON laxo.

---

## 🔒 Privacidad

- Las API keys se guardan en SQLite local (`%APPDATA%\JobRadar\`) y **nunca** en logs
  ni en el repositorio.
- `.gitignore` excluye `*.db`, `.env`, `secrets.json`, `dist/`, `build/` y las notas
  internas de desarrollo.

---

<div align="center">

Hecho con ❤️ para cazar mejores vacantes · *SinFro · Job Radar*

</div>
