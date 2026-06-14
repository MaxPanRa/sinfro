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

#: Recursos empaquetados (ícono). Resuelve en dev y bajo PyInstaller (datas).
ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"
ICON_PATH: Path = ASSETS_DIR / "icon.ico"

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

#: Cuota mensual de Jooble configurada para este proyecto.
JOOBLE_MONTHLY_QUOTA = 500

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

#: Catálogo de skills para autocompletar (cualquier profesión). El usuario también
#: puede escribir las suyas. Cubre tech, soft, liderazgo, admin, legal, salud, etc.
SKILLS_CATALOG = sorted(set([
    # --- Lenguajes de programación ---
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "C", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl", "Dart",
    "Elixir", "Objective-C", "SQL", "Bash", "PowerShell", "Solidity", "Groovy",
    # --- Frontend ---
    "React", "Angular", "Vue.js", "Svelte", "Next.js", "Nuxt", "Redux", "HTML5",
    "CSS3", "Sass", "Tailwind CSS", "Bootstrap", "jQuery", "Webpack", "Vite",
    "Three.js", "D3.js", "Material UI", "Storybook", "Accessibility (a11y)",
    "Responsive Design", "Progressive Web Apps",
    # --- Backend / frameworks ---
    "Node.js", "Express", "NestJS", "Django", "Flask", "FastAPI", "Spring Boot",
    "Laravel", "Ruby on Rails", ".NET", "ASP.NET", "GraphQL", "REST APIs", "gRPC",
    "Microservices", "Kafka", "RabbitMQ", "Hibernate", "Entity Framework",
    "WebSockets", "OAuth", "JWT",
    # --- Datos / bases de datos ---
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Oracle", "SQL Server",
    "Cassandra", "DynamoDB", "Elasticsearch", "Firebase", "Supabase", "Snowflake",
    "BigQuery", "Pandas", "NumPy", "Apache Spark", "ETL", "Data Modeling",
    "Data Warehousing", "dbt",
    # --- Cloud / DevOps ---
    "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes", "Terraform", "Ansible",
    "Jenkins", "GitHub Actions", "GitLab CI", "CI/CD", "Linux", "Nginx",
    "Serverless", "AWS Lambda", "CloudFormation", "Prometheus", "Grafana", "Helm",
    "ArgoCD", "Datadog", "Site Reliability Engineering",
    # --- IA / Ciencia de datos ---
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "scikit-learn",
    "NLP", "Computer Vision", "LLMs", "Prompt Engineering", "Data Analysis",
    "Data Visualization", "Power BI", "Tableau", "Statistics", "MLOps",
    "Generative AI",
    # --- Testing / QA ---
    "Unit Testing", "Jest", "Cypress", "Selenium", "Playwright", "Pytest", "JUnit",
    "TDD", "QA Automation", "Postman", "Integration Testing", "Load Testing",
    # --- Mobile ---
    "React Native", "Flutter", "iOS Development", "Android Development", "SwiftUI",
    "Jetpack Compose", "Xamarin", "Ionic",
    # --- Metodologías / herramientas ---
    "Agile", "Scrum", "Kanban", "SAFe", "Git", "Jira", "Confluence",
    "Design Patterns", "Clean Architecture", "Domain-Driven Design",
    # --- Soft skills ---
    "Comunicación", "Trabajo en equipo", "Resolución de problemas",
    "Pensamiento crítico", "Adaptabilidad", "Gestión del tiempo", "Creatividad",
    "Inteligencia emocional", "Colaboración", "Escucha activa",
    "Resolución de conflictos", "Toma de decisiones", "Atención al detalle",
    "Ética profesional", "Empatía", "Resiliencia", "Negociación",
    "Hablar en público", "Presentaciones", "Storytelling", "Networking",
    "Automotivación", "Proactividad", "Flexibilidad", "Manejo del estrés",
    "Orientación a resultados", "Organización",
    # --- Liderazgo / management ---
    "Liderazgo", "Gestión de equipos", "Gestión de proyectos", "Mentoría",
    "Coaching", "Planeación estratégica", "Gestión de stakeholders", "Delegación",
    "Gestión del desempeño", "Gestión del cambio", "Presupuestos", "OKRs",
    "Roadmapping", "Reclutamiento", "Onboarding", "Liderazgo transversal",
    "Product Management", "People Management",
    # --- Negocios / administración ---
    "Microsoft Office", "Excel", "Word", "PowerPoint", "Outlook",
    "Google Workspace", "Captura de datos", "Contabilidad", "Análisis financiero",
    "Facturación", "Nómina", "Compras", "Gestión de inventario", "Agenda",
    "Administración de oficina", "Atención al cliente", "CRM", "Salesforce", "SAP",
    "Gestión documental",
    # --- Marketing / ventas ---
    "Marketing Digital", "SEO", "SEM", "Marketing de contenidos",
    "Redes sociales", "Email marketing", "Google Ads", "Meta Ads", "Copywriting",
    "Gestión de marca", "Investigación de mercado", "Generación de leads",
    "Ventas", "Ventas B2B", "Gestión de cuentas", "HubSpot", "Google Analytics",
    "Estrategia de marketing", "E-commerce", "Embudos de conversión",
    # --- Legal / abogacía ---
    "Derecho Corporativo", "Litigio", "Derecho Laboral", "Derecho Fiscal",
    "Derecho Civil", "Derecho Penal", "Derecho Mercantil", "Contratos",
    "Compliance", "Propiedad Intelectual", "Derecho Migratorio", "Mediación",
    "Arbitraje", "Due Diligence", "Redacción jurídica", "Investigación jurídica",
    "Derecho Administrativo", "Derecho Internacional", "Amparo", "Derecho Familiar",
    # --- Diseño / creativo ---
    "UX Design", "UI Design", "Diseño gráfico", "Adobe Photoshop",
    "Adobe Illustrator", "Adobe XD", "InDesign", "Premiere Pro", "After Effects",
    "Wireframing", "Prototyping", "Design Thinking", "Branding", "Tipografía",
    "Motion Graphics", "Figma",
    # --- Salud ---
    "Atención al paciente", "Enfermería", "Expediente clínico", "Toma de muestras",
    "RCP", "Farmacología", "Investigación clínica", "Codificación médica",
    "Telemedicina", "Primeros auxilios", "Valoración de pacientes",
    # --- Educación ---
    "Desarrollo curricular", "Planeación de clases", "Gestión del aula",
    "E-learning", "Diseño instruccional", "Tutoría", "Evaluación educativa",
    # --- Idiomas ---
    "Inglés", "Español", "Francés", "Alemán", "Portugués", "Italiano",
    "Chino Mandarín", "Japonés", "Bilingüe", "Traducción",
    # --- Operaciones / oficios ---
    "Logística", "Cadena de suministro", "Gestión de almacén", "Control de calidad",
    "Lean Manufacturing", "Six Sigma", "AutoCAD", "SolidWorks", "Soldadura",
    "Electricidad", "Plomería", "HVAC", "Mantenimiento industrial",
]))

# --- Perfil base del usuario (se combina con el resumen del CV) ---------------

# Vacío a propósito: el perfil real viene del resumen del CV de cada perfil.
# (Antes estaba fijo en "Desarrollador Full Stack…", lo que sesgaba la IA y
# castigaba perfiles no-tech como abogacía.)
PERFIL_BASE = ""

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
    "jooble_api_key": "",
    "adzuna_app_id": "",
    "adzuna_app_key": "",
    "ats_company": "",
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
    "settings_shared": "0",     # 0 = ajustes de búsqueda por perfil; 1 = compartidos
}
