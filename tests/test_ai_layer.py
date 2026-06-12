"""Prueba de la capa IA: parser (unit) + clasificación y evaluación reales.

Como la suscripción Go está sin saldo, usa el modelo GRATIS para las llamadas
reales. Ejecutar:  python -m tests.test_ai_layer
"""

from __future__ import annotations

import sys

from job_radar.ai import parse_json_loose
from job_radar.ai.classifier import classify_job
from job_radar.ai.evaluator import evaluate_job
from job_radar.ai.opencode_client import OpenCodeClient
from job_radar.sources import RemotiveSource

FREE = "opencode/deepseek-v4-flash-free"


def test_parser_unit() -> None:
    """El parser debe tolerar ANSI, header, fences y JSON laxo."""
    casos = [
        '\x1b[0m\n> build · deepseek-v4-flash-free\n\x1b[0m\n{ok: true, n: 7}',
        '```json\n{"match_score": 80, "modalidad": "Remoto"}\n```',
        "Aquí tienes:\n{'match_score': 65, 'seniority': 'Senior',}",
        '> build · model\n{ "acepta_cdmx": true, "resumen_una_linea": "hola" }',
    ]
    for c in casos:
        data = parse_json_loose(c)
        assert isinstance(data, dict) and data, c
    print("[OK] parser tolerante: 4/4 casos parseados")


def test_classify_real() -> None:
    client = OpenCodeClient(fast_model=FREE, free_model=FREE, use_free_fallback=True)
    jobs = RemotiveSource().fetch()[:2]
    for job in jobs:
        data = classify_job(client, job.to_dict(), timeout=90)
        assert 0 <= data["match_score"] <= 100
        assert set(data) >= {
            "match_score", "modalidad", "acepta_cdmx", "seniority", "resumen_una_linea"
        }
        print(f"[OK] clasif {job.title[:40]!r}: score={data['match_score']} "
              f"mod={data['modalidad']} sr={data['seniority']}")


def test_evaluate_real() -> None:
    client = OpenCodeClient(deep_model=FREE, free_model=FREE, use_free_fallback=True)
    job = RemotiveSource().fetch()[0]
    md = evaluate_job(
        client, job.to_dict(),
        profile_summary="10+ años React/Angular/TypeScript, líder técnico.",
        technologies=[{"name": "React", "level": 9, "origin": "manual"},
                      {"name": "Angular", "level": 8, "origin": "manual"}],
        nivel_ingles="B2",
        salario_objetivo="25 USD/hora",
        timeout=180,
    )
    assert "# Evaluación de Vacante" in md, md[:300]
    assert "## Veredicto" in md
    print(f"[OK] evaluación generada ({len(md)} chars). Primeras líneas:")
    print("\n".join(md.splitlines()[:6]))


def main() -> int:
    test_parser_unit()
    test_classify_real()
    test_evaluate_real()
    print("\nTodas las pruebas de IA pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
