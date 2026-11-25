"""Der eine Weg zur Text-KI (OpenRouter): Timeout, Wiederholung, JSON geprüft.

Jeder Aufruf gibt geprüftes JSON zurück oder wirft LLMError — nie halbe Daten.
"""

import json
import re
import time

import requests

from . import settings

_URL = "https://openrouter.ai/api/v1/chat/completions"
_SYSTEM = "You are a specialized JSON-only generator. No markdown."


class LLMError(RuntimeError):
    pass


def configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)


def parse_json(text: str):
    """JSON aus einer Modellantwort lesen; repariert Code-Zäune, Zeilenumbrüche
    in Strings und Kommas vor schließenden Klammern."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(
        r'("\s*:\s*")(.+?)("\s*[,}\]])',
        lambda m: (
            m.group(1) + m.group(2).replace("\n", "\\n").replace("\r", "") + m.group(3)
        ),
        text,
        flags=re.DOTALL,
    )
    fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as exc:
        raise LLMError("Die KI hat kein lesbares JSON geliefert") from exc


def _post(payload, timeout):
    return requests.post(
        _URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )


def complete_json(
    prompt: str, *, timeout: int = 120, max_tokens: int = 12000, attempts: int = 2
):
    """Prompt senden, geprüftes JSON zurückgeben."""
    if not configured():
        raise LLMError("OPENROUTER_API_KEY ist nicht gesetzt")
    payload = {
        "model": settings.CREATIVE_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.6,
        "max_tokens": max_tokens,
    }
    last = None
    for attempt in range(attempts):
        try:
            resp = _post(payload, timeout)
            if resp.status_code in (401, 403):
                raise LLMError("OpenRouter lehnt den Schlüssel ab")
            if resp.status_code == 429 or resp.status_code >= 500:
                last = LLMError(f"OpenRouter antwortet mit {resp.status_code}")
            elif resp.status_code >= 400:
                raise LLMError(
                    f"OpenRouter-Fehler {resp.status_code}: {resp.text[:200]}"
                )
            else:
                choices = (resp.json() or {}).get("choices") or []
                if not choices:
                    last = LLMError("Die KI hat nichts geantwortet")
                elif choices[0].get("finish_reason") == "length":
                    last = LLMError("Die Antwort der KI wurde abgeschnitten")
                else:
                    content = (choices[0].get("message") or {}).get("content")
                    if not content:
                        last = LLMError("Die KI hat eine leere Antwort geliefert")
                    else:
                        try:
                            return parse_json(content)
                        except LLMError as exc:
                            last = exc
        except requests.Timeout:
            last = LLMError("Die KI hat nicht rechtzeitig geantwortet")
        except requests.RequestException as exc:
            last = LLMError(f"KI nicht erreichbar: {exc.__class__.__name__}")
        if attempt + 1 < attempts:
            time.sleep(1.5)
    raise last or LLMError("Unbekannter KI-Fehler")
