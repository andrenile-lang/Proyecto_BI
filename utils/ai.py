"""Asistente de IA: LLM compatible con la API de OpenAI (OpenAI, Azure, Groq, GitHub Models, etc.)."""
from __future__ import annotations

import json
import os

import requests

SYSTEM_PROMPT = """Actúa como Director Comercial Senior y consultor de Business Intelligence especializado en
cadenas de restaurantes (pizza). Recibirás un JSON con los indicadores del dashboard YA FILTRADOS por el usuario.

REGLAS:
1. Usa EXCLUSIVAMENTE los datos del JSON. No inventes cifras, competidores, campañas ni causas no observables.
2. Cada afirmación debe citar la cifra que la respalda (ventas, margen, variación, descuento, tiempo de entrega, etc.).
3. Distingue entre correlación y causalidad: si propones una causa, márcala como HIPÓTESIS.
4. Si los datos son insuficientes para concluir algo, dilo explícitamente.
5. Responde en español, con formato Markdown y de forma ejecutiva.

ESTRUCTURA DE LA RESPUESTA (cuando se pidan recomendaciones):
## Hallazgos clave (5, con evidencia numérica)
## Riesgos (máx. 5)
## Oportunidades (máx. 5)
## Decisiones estratégicas (5): acción · evidencia · KPI de seguimiento · meta realista
## Ranking de sucursales y de productos (breve)
## Límites del análisis (qué debe validar un humano antes de decidir)
"""


def get_config(secrets=None, session_key: str | None = None) -> dict:
    def pick(name, default=None):
        val = None
        try:
            if secrets is not None and name in secrets:
                val = secrets[name]
        except Exception:
            val = None
        return val or os.environ.get(name) or default
    return {
        "api_key": session_key or pick("OPENAI_API_KEY"),
        "base_url": (pick("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/"),
        "model": pick("OPENAI_MODEL", "gpt-4o-mini"),
    }


def ask_llm(cfg: dict, user_msg: str, context: dict, history: list[dict] | None = None, timeout: int = 90) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": "DATOS DEL DASHBOARD (JSON):\n" + json.dumps(context, ensure_ascii=False, default=str)}]
    messages += (history or [])[-6:]
    messages.append({"role": "user", "content": user_msg})
    r = requests.post(
        f"{cfg['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={"model": cfg["model"], "messages": messages, "temperature": 0.2},
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Error {r.status_code} del proveedor de IA: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


DEFAULT_REQUEST = ("Genera: 5 hallazgos clave, 5 riesgos, 5 oportunidades, 5 decisiones estratégicas (acción, evidencia, "
                   "KPI y meta), un ranking de sucursales y un ranking de productos, y los límites del análisis.")
