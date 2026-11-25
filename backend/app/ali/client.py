"""Der eine Zugang zu AliRemote.

Zwei Fehlerarten, wie bei Kie:
- AliError: AliRemote hat sicher abgelehnt (oder ist nicht eingerichtet).
- AliUncertain: Antwort verloren oder Serverfehler. Ein Start kann trotzdem
  angekommen sein — der Aufrufer wiederholt ihn nicht von selbst.
Jeder schreibende Aufruf trägt einen Idempotency-Key.
"""

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import requests

from .. import settings

_API = "https://api.aliremote.com/api/v1/"
_DEFINITE = {400, 401, 403, 404, 409, 413, 422, 429}
TERMINAL = {"succeeded", "completed", "failed", "cancelled", "canceled", "error", "stopped"}


class AliError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class AliUncertain(RuntimeError):
    pass


def phone(value):
    value = str(value or "").removeprefix("aliremote:")
    if not value or "/" in value or "?" in value:
        raise AliError("Dem Account ist kein gültiges Handy zugeordnet")
    return value


class AliClient:
    name = "aliremote"

    def configured(self):
        return bool(settings.ALIREMOTE_TOKEN)

    def _request(self, method, path, body=None, key=None, timeout=25):
        if not self.configured():
            raise AliError("AliRemote ist nicht verbunden (ALIREMOTE_TOKEN fehlt)")
        headers = {"Authorization": f"Bearer {settings.ALIREMOTE_TOKEN}"}
        if key:
            headers["Idempotency-Key"] = key
        try:
            resp = requests.request(method, _API + path, json=body, headers=headers, timeout=timeout, allow_redirects=False)
        except requests.RequestException as exc:
            raise AliUncertain("Keine Antwort von AliRemote") from exc
        if resp.status_code in _DEFINITE:
            raise AliError(f"AliRemote hat abgelehnt ({resp.status_code})", resp.status_code)
        if resp.status_code >= 300:
            raise AliUncertain(f"AliRemote antwortete mit {resp.status_code}")
        try:
            return resp.json()
        except ValueError as exc:
            raise AliUncertain("Unlesbare Antwort von AliRemote") from exc

    # --- Lesen --------------------------------------------------------------
    def devices(self):
        out, cursor = [], None
        for _ in range(20):
            page = self._request("GET", "devices" + (f"?{urlencode({'cursor': cursor})}" if cursor else ""))
            for d in page.get("devices") or []:
                out.append({"id": d["public_id"], "name": d.get("name") or d["public_id"], "online": d.get("status") == "online"})
            cursor = page.get("next_cursor")
            if not cursor:
                break
        return out

    def phone_free(self, device_id):
        return self._request("GET", f"devices/{quote(phone(device_id), safe='')}/control-session").get("held_by") == "free"

    def native_accounts(self):
        rows = self._request("GET", "instagram/accounts").get("accounts") or []
        return [{"id": str(r.get("id")), "username": str(r.get("username") or "").lstrip("@").lower()} for r in rows if r.get("id")]

    # --- Tresor -------------------------------------------------------------
    def ensure_folder(self, names):
        rows = self._request("GET", "media/folders").get("folders") or []
        parent = None
        for name in names:
            name = name[:100]
            match = [r for r in rows if r.get("parent_id") == parent and r.get("name") == name]
            if not match:
                row = self._request("POST", "media/folders", {"name": name, "parent_id": parent}, key=f"ogs-folder:{parent}:{name}")
                if not row.get("id"):
                    raise AliUncertain("AliRemote hat den Ordner nicht bestätigt")
                rows.append(row)
                match = [row]
            parent = match[0]["id"]
        return parent

    def import_media(self, url, filename, folder_id, key):
        row = self._request("POST", "media/import", {"url": url, "filename": filename, "folder_id": folder_id}, key=key, timeout=90)
        if not row.get("id"):
            raise AliUncertain("AliRemote hat keine Datei-Kennung geliefert")
        return row["id"]

    def media(self, media_id):
        """{"ready": bool, "posted": bool, "expired": bool} oder None, wenn es die Datei nicht mehr gibt."""
        try:
            row = self._request("GET", f"media/{quote(media_id, safe='')}")
        except AliError as exc:
            if exc.status == 404:
                return None
            raise
        expires = row.get("expires_at")
        expired = bool(expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) <= datetime.now(timezone.utc))
        return {"ready": row.get("status") == "ready", "posted": bool(row.get("posted")), "expired": expired}

    # --- Läufe --------------------------------------------------------------
    def start_run(self, automation_id, device_id, inputs, key):
        data = self._request("POST", f"automations/{quote(automation_id, safe='')}/runs", {"phone": phone(device_id), "inputs": inputs}, key=key)
        if not isinstance(data.get("run_id"), str) or not data["run_id"]:
            raise AliUncertain("AliRemote hat keine Lauf-Nummer geliefert")
        return data["run_id"]

    def run(self, run_id):
        data = self._request("GET", f"automation-runs/{quote(run_id, safe='')}")
        return data.get("run", data)

    def cancel_run(self, run_id, key):
        self._request("POST", f"automation-runs/{quote(run_id, safe='')}/cancel", {}, key=key)

    # --- Native Warm-ups (Sanfter Kurs) --------------------------------------
    def start_warmup(self, device_id, native_id, minutes, key):
        device = phone(device_id)
        busy = [w for w in self._request("GET", "warmups").get("warmups") or []
                if (w.get("device") or {}).get("id") == device and (w.get("status") not in ("done", "stopped") or w.get("running") or w.get("starting"))]
        if busy:
            raise AliError("Auf diesem Handy läuft schon ein AliRemote-Warm-up")
        body = {"devices": [device], "platform": "instagram", "days": 1, "sessions_per_day": 1, "hours_from": 0, "hours_to": 24,
                "run_now": False, "accounts": {device: native_id},
                "routine": {"blocks": [{"kind": "reels", "minutes": minutes}], "reel_seconds": 10, "post_seconds": 6, "likes": 0,
                            "comment_reads": 0, "comments": 0, "follows": 0, "rewatch_chance": 0, "creator_visits": 0,
                            "creator_videos": 0, "max_following": 0}}
        data = self._request("POST", "warmups", body, key=key)
        programs = data.get("warmups") or []
        if data.get("started") != 1 or len(programs) != 1 or not programs[0].get("id"):
            raise AliUncertain("AliRemote hat das Warm-up nicht eindeutig bestätigt")
        return str(programs[0]["id"])

    def warmup(self, warmup_id):
        return self._request("GET", f"warmups/{quote(warmup_id, safe='')}").get("warmup") or {}


class FakeAli:
    """Nachgestelltes AliRemote für Tests und zum Ausprobieren: drei Handys,
    Läufe enden sofort mit einer passenden Quittung."""

    name = "fake"

    def __init__(self):
        self.phones = [{"id": "2343", "name": "iPhone 2343", "online": True}, {"id": "3996", "name": "iPhone 3996", "online": True},
                       {"id": "4410", "name": "iPhone 4410", "online": False}]
        self.runs, self.vault, self.warmups, self.calls = {}, {}, {}, []
        self.busy = set()
        self.fail = {}  # art -> Fehler, den der nächste Aufruf wirft
        self.output = {}  # Überschreibungen für die nächste Quittung

    def _maybe_fail(self, kind):
        if kind in self.fail:
            raise self.fail.pop(kind)

    def configured(self):
        return True

    def devices(self):
        return list(self.phones)

    def phone_free(self, device_id):
        return phone(device_id) not in self.busy

    def native_accounts(self):
        return []

    def ensure_folder(self, names):
        return "folder:" + "/".join(names)

    def import_media(self, url, filename, folder_id, key):
        self._maybe_fail("import")
        self.calls.append(("import", key))
        media_id = self.vault.setdefault(key, {"id": "vault_" + uuid.uuid4().hex[:10], "ready": True, "posted": False, "expired": False})["id"]
        return media_id

    def media(self, media_id):
        return next((dict(v) for v in self.vault.values() if v["id"] == media_id), None)

    def start_run(self, automation_id, device_id, inputs, key):
        self._maybe_fail("start")
        self.calls.append(("start", key))
        if key in self.runs:  # Idempotency-Key: derselbe Lauf, kein zweiter
            return self.runs[key]["id"]
        out = {"slot_id": inputs["slot_id"], "account": inputs["account"], "phone": phone(device_id)}
        if "video" in inputs:
            out.update(video=inputs["video"], posted=True, verified=True, after_scroll="done", posts_before=3, posts_after=4,
                       caption=inputs.get("caption", ""))
        elif "minutes" in inputs:
            out.update(session_done=True, minutes=inputs["minutes"])
        else:
            out.update(account_status="fine")
        out.update(self.output)
        self.output = {}
        run = {"id": "run_" + uuid.uuid4().hex[:10], "status": "succeeded", "output": out, "steps": [{"device": phone(device_id)}]}
        self.runs[key] = run
        return run["id"]

    def run(self, run_id):
        return next(dict(r) for r in self.runs.values() if r["id"] == run_id)

    def cancel_run(self, run_id, key):
        next(r for r in self.runs.values() if r["id"] == run_id)["status"] = "cancelled"

    def start_warmup(self, device_id, native_id, minutes, key):
        self._maybe_fail("start")
        now = datetime.now(timezone.utc)
        wid = "wu_" + uuid.uuid4().hex[:8]
        self.warmups[wid] = {"id": wid, "status": "done", "sessions_done": 1,
                             "sessions": [{"id": "s1", "outcome": "done", "started_at": (now - timedelta(minutes=minutes)).isoformat(), "finished_at": now.isoformat()}]}
        return wid

    def warmup(self, warmup_id):
        return self.warmups[warmup_id]


_client = None


def get_client():
    global _client
    if _client is None:
        _client = FakeAli() if settings.MEDIA_PROVIDER == "fake" else AliClient()
    return _client


def set_client(client):
    global _client
    _client = client
