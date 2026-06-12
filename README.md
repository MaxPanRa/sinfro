# Job Radar

Aplicación de escritorio (Windows) que **monitorea vacantes de empleo mientras la
ventana está abierta**, las **clasifica con IA** vía OpenCode CLI y te permite
gestionarlas como una **bandeja de correo**: no vistas en negrita, evaluación
profunda bajo demanda, marcar como aplicada/descartada, etc.

- **Stack:** Python 3.12 · PySide6 · SQLite · PyInstaller.
- **IA:** shell-out a OpenCode CLI (`opencode run`), proveedor **OpenCode Go**.
- **Persistencia local:** `%APPDATA%\JobRadar\job_radar.db`.

---

## 1. Requisitos

- **Python ≥ 3.11** (probado en 3.12.1).
- **OpenCode CLI** instalado y en el PATH (`opencode --version`).
  Instalación: https://opencode.ai (o `npm i -g opencode-ai`).
- Windows 10/11.

## 2. Instalación (desarrollo)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Configurar OpenCode Go (IA)

1. Inicia sesión en https://opencode.ai y **suscríbete a Go** si aún no lo estás.
2. Crea/copía tu **API key** de OpenCode Go.
3. Abre la app → menú **Ajustes** → pega la key en **"API key de OpenCode Go"**.
   La app la inyecta como `OPENCODE_API_KEY` al ejecutar `opencode run`.
   (Si ya tienes credenciales guardadas por `opencode auth login`, también se respetan.)
4. **Modelos** (configurables en Ajustes; el formato real es `opencode-go/<id>`):
   - Clasificación rápida (barata, corre sobre cada vacante): `opencode-go/deepseek-v4-flash`.
   - Evaluación profunda (capaz, bajo demanda + cacheada): `opencode-go/kimi-k2.6`.
   - Respaldo **gratuito** (si se agota el saldo): `opencode/deepseek-v4-flash-free`
     (actívalo con el toggle "usar modelo gratuito de respaldo").

> **Importante:** el saldo de Go se mide en **dólares**, no en número de requests.
> Por eso la clasificación usa un modelo barato y la evaluación profunda solo se
> genera bajo demanda y se cachea. Si ves "saldo insuficiente", recarga en tu
> panel de billing de OpenCode o usa el modelo gratuito de respaldo.

Ver modelos disponibles con tu key:

```powershell
opencode models
```

## 4. (Opcional) SerpAPI — Google for Jobs

1. Crea una cuenta gratuita en https://serpapi.com (incluye ~100 búsquedas/mes).
2. Copia tu **API key** desde el dashboard de SerpAPI.
3. Pégala en **Ajustes → "API key de SerpAPI"**.

La app lleva un contador mensual en la base de datos y deja de llamar al agotar la
cuota, avisándolo en la barra de estado.

## 5. Ejecutar (desarrollo)

```powershell
.\.venv\Scripts\python.exe run_job_radar.py
```

Pulsa **"Comenzar monitoreo"**. El **Grupo A** (RemoteOK, Remotive, We Work
Remotely, Hacker News) corre cada 20 min; el **Grupo B** (JobSpy LinkedIn/Indeed,
SerpAPI) corre en las ventanas 6:00 y 18:00. En Ajustes hay un **flag de
desarrollo** que reduce el intervalo del Grupo A a 1 minuto para pruebas.

---

## 6. Generar el ejecutable (PyInstaller)

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean job_radar.spec
```

El resultado queda en **`dist\JobRadar\JobRadar.exe`** (one-folder, sin consola).

**¿Por qué one-folder y no one-file?** Con PySide6, el modo *one-file* re-extrae
todo Qt a una carpeta temporal en **cada arranque**, lo que provoca inicios
lentos y, a veces, falsos positivos de antivirus. *One-folder* arranca rápido y
es más estable. Para distribuir, comprime la carpeta `dist\JobRadar\` completa.

La base de datos y la configuración viven en `%APPDATA%\JobRadar\`, **fuera** de la
carpeta del ejecutable, así que actualizar el binario no borra tus datos.

---

## 7. Arquitectura

```
job_radar/
  config.py            Constantes, modelos por defecto, estados de México
  db/database.py       SQLite thread-safe (jobs, evaluations, settings, quotas, runs…)
  sources/             Una clase por fuente (interfaz común JobSource)
    base.py            Job + JobSource + dedup por hash título+empresa
    remoteok / remotive / weworkremotely / hackernews   (Grupo A)
    jobspy_source / serpapi_source / occ                (Grupo B)
  ai/                  Shell-out a OpenCode con parser tolerante
    opencode_client.py Subprocess + inyección de key + parser JSON laxo
    classifier.py      Clasificación rápida (JSON)
    evaluator.py       Evaluación profunda (plantilla larga)
  profile/cv_parser.py Extracción de CV (PDF/DOCX) + análisis IA
  scheduler/           QTimer Grupo A + ventanas Grupo B
  ui/                  PySide6: ventana, columnas, bandeja, popup, ajustes, workers
  service.py           Orquestación sin Qt (DB + fuentes + IA)
  main.py              Punto de entrada
run_job_radar.py       Lanzador (dev y PyInstaller)
job_radar.spec         Spec de PyInstaller
```

Toda llamada de red/IA corre en **QThreadPool** (nunca en el hilo de UI). Si una
fuente falla, la app sigue y lo reporta en la barra de estado.

## 8. Notas de privacidad

- La API key se guarda en SQLite y **nunca** se escribe en logs.
- `dev-memory/` (notas internas de desarrollo) está en `.gitignore`.
- `*.db`, `.env` y `secrets.json` están ignorados por git.
