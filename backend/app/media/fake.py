"""Platzhalter-Anbieter: erzeugt farbige Testbilder ohne Kosten.
Nur für lokales Ausprobieren und Tests (MEDIA_PROVIDER=fake)."""

import hashlib
import struct
import uuid
import zlib

from .. import settings


def _png(seed: str, width=400, height=500) -> bytes:
    h = hashlib.sha256(seed.encode()).digest()
    top, bottom = h[0:3], h[3:6]
    rows = bytearray()
    for y in range(height):
        t = y / (height - 1)
        r, g, b = (int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        rows += b"\x00" + bytes((r, g, b)) * width

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b"")


def _silent_clip(seed: str) -> bytes:
    """Zwei Sekunden einfarbiges Video ohne Ton (wie Kling es liefert)."""
    import subprocess
    import tempfile

    color = hashlib.sha256(seed.encode()).hexdigest()[:6]
    with tempfile.NamedTemporaryFile(suffix=".mp4") as out:
        subprocess.run([settings.FFMPEG_BIN, "-y", "-f", "lavfi", "-i", f"color=c=0x{color}:s=360x640:d=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out.name], check=True, capture_output=True)
        return out.read()


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.tasks = {}
        self.fail_next = []  # Fehlertexte, die die nächsten Aufträge liefern sollen

    def configured(self):
        return True

    def host_file(self, data: bytes, filename: str) -> str:
        settings.FILES_DIR.mkdir(parents=True, exist_ok=True)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        name = f"{uuid.uuid4().hex[:16]}.{ext if ext.isalnum() else 'bin'}"
        (settings.FILES_DIR / name).write_bytes(data)
        return f"{settings.PUBLIC_URL}/files/{name}"

    def submit_image(self, prompt, references, aspect_ratio="4:5", resolution="2K") -> str:
        task_id = "fake_" + uuid.uuid4().hex[:12]
        self.tasks[task_id] = {"prompt": prompt, "references": list(references or []),
                               "error": self.fail_next.pop(0) if self.fail_next else None}
        return task_id

    def submit_video(self, prompt, image_url, video_url, model="kling-3.0") -> str:
        task_id = "fakevid_" + uuid.uuid4().hex[:12]
        self.tasks[task_id] = {"prompt": prompt, "image": image_url, "video": video_url, "model": model, "kind": "video",
                               "error": self.fail_next.pop(0) if self.fail_next else None}
        return task_id

    def check(self, task_id) -> dict:
        task = self.tasks.get(task_id)
        if task is None:
            return {"state": "fail", "error": "Unbekannter Auftrag"}
        if task["error"]:
            return {"state": "fail", "error": task["error"]}
        if "url" not in task and task.get("kind") == "video":
            task["url"] = self.host_file(_silent_clip(task_id), "video.mp4")
        if "url" not in task:
            task["url"] = self.host_file(_png(task_id), "bild.png")
        return {"state": "success", "url": task["url"]}
