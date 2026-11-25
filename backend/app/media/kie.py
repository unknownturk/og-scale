"""Kie.ai: Dateien hosten, Bilder beauftragen, Stand abfragen.

Ein Auftrag kostet Geld und lässt sich nicht zurückholen. Deshalb gilt:
- Nur eine ausdrückliche Ablehnung (429) wird wiederholt.
- Geht die Antwort verloren oder kommt ein Serverfehler, ist unklar, ob Kie den
  Auftrag angenommen hat. Dann wird NICHT erneut gesendet, sondern
  SubmissionUncertain geworfen — der Aufrufer entscheidet.
"""

import json
import random
import time

import requests

from .. import settings
from .base import MediaError, SubmissionUncertain

_UPLOAD = "https://kieai.redpandaai.co/api/file-stream-upload"
_CREATE = "https://api.kie.ai/api/v1/jobs/createTask"
_STATUS = "https://api.kie.ai/api/v1/jobs/recordInfo"


def _auth():
    if not settings.KIE_API_KEY:
        raise MediaError("KIE_API_KEY ist nicht gesetzt")
    return {"Authorization": f"Bearer {settings.KIE_API_KEY}"}


class KieProvider:
    name = "kie"

    def configured(self):
        return bool(settings.KIE_API_KEY)

    def host_file(self, data: bytes, filename: str) -> str:
        """Datei bei Kie ablegen (dort etwa drei Tage abrufbar)."""
        try:
            resp = requests.post(
                _UPLOAD, headers=_auth(), files={"file": (filename, data)},
                data={"uploadPath": "og-scale"}, timeout=(15, 180),
            )
        except requests.RequestException as exc:
            raise MediaError("Hochladen zu Kie fehlgeschlagen (keine Verbindung)") from exc
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        url = (body.get("data") or {}).get("downloadUrl")
        if resp.status_code != 200 or not url:
            raise MediaError(f"Hochladen zu Kie fehlgeschlagen ({resp.status_code})")
        return url

    def _submit(self, payload) -> str:
        headers = {**_auth(), "Content-Type": "application/json"}
        for attempt in range(5):
            try:
                resp = requests.post(_CREATE, headers=headers, json=payload, timeout=60)
            except requests.RequestException as exc:
                raise SubmissionUncertain("Antwort von Kie ging verloren") from exc
            try:
                body = resp.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                body = {}
            data = body.get("data")
            task_id = (data.get("taskId") if isinstance(data, dict) else None) or body.get("taskId")
            if task_id:
                return task_id
            code = str(body.get("code") or "")
            if resp.status_code == 429 or code == "429":
                if attempt == 4:
                    raise MediaError("Kie ist überlastet. Versuch es in ein paar Minuten noch einmal.")
                time.sleep(2**attempt + random.uniform(0, 0.5))
                continue
            if resp.status_code >= 500 or code in ("500", "502", "503", "504"):
                raise SubmissionUncertain(f"Kie antwortete mit einem Serverfehler ({resp.status_code})")
            if resp.status_code != 200 or code not in ("200", ""):
                raise MediaError(f"Kie hat den Auftrag abgelehnt: {body.get('msg') or resp.status_code}")
            raise SubmissionUncertain("Kie hat keine Auftragsnummer geliefert")
        raise MediaError("Kie ist überlastet.")

    def submit_image(self, prompt, references, aspect_ratio="4:5", resolution="2K") -> str:
        return self._submit({
            "model": "nano-banana-pro",
            "input": {
                "prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": resolution,
                "output_format": "png", "image_input": list(references or []),
            },
        })

    def check(self, task_id) -> dict:
        """Einmal nachsehen. Ergebnis: {"state": "waiting"|"success"|"fail", "url", "error"}.
        Verbindungsprobleme gelten als „noch nicht fertig", nie als Fehlschlag."""
        try:
            resp = requests.get(_STATUS, params={"taskId": task_id}, headers=_auth(), timeout=30)
            body = resp.json()
        except (requests.RequestException, ValueError):
            return {"state": "waiting"}
        if resp.status_code != 200 or body.get("code") != 200:
            return {"state": "waiting"}
        data = body.get("data") or {}
        if data.get("state") == "success":
            try:
                urls = json.loads(data.get("resultJson") or "{}").get("resultUrls") or []
            except ValueError:
                urls = []
            if urls:
                return {"state": "success", "url": urls[0]}
            return {"state": "fail", "error": "Kie hat kein Ergebnis geliefert"}
        if data.get("state") == "fail":
            return {"state": "fail", "error": data.get("failMsg") or "Unbekannter Fehler bei Kie"}
        return {"state": "waiting"}
