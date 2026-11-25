"""Video-Handwerk mit ffmpeg: Vorlage holen, prüfen, umrechnen, Ton zurücklegen."""

import ipaddress
import socket
import subprocess
import uuid
from contextlib import contextmanager
from urllib.parse import urlparse

import requests

from .. import settings


class VideoError(RuntimeError):
    pass


@contextmanager
def workdir():
    """Arbeitsordner, der am Ende immer aufgeräumt wird."""
    import shutil

    path = settings.WORK_DIR / uuid.uuid4().hex[:12]
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def check_url(url):
    """Nur öffentliche http(s)-Adressen. Schützt davor, dass eine eingefügte
    Adresse den Server interne Dienste abrufen lässt."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise VideoError("Das ist keine gültige Web-Adresse")
    if settings.ALLOW_PRIVATE_URLS:
        return
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise VideoError("Die Adresse ist nicht erreichbar")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise VideoError("Diese Adresse ist nicht erlaubt")


def _is_page(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host.endswith(h) for h in ("instagram.com", "tiktok.com", "youtube.com", "youtu.be"))


def download(url, folder):
    """Video laden. Direkte Datei-Links per HTTP, Seiten (Instagram, TikTok) per yt-dlp."""
    check_url(url)
    target = folder / "quelle.mp4"
    if _is_page(url):
        try:
            import yt_dlp

            options = {"format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                       "outtmpl": str(folder / "quelle.%(ext)s"), "quiet": True, "no_warnings": True,
                       "max_filesize": settings.MAX_SOURCE_BYTES}
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.prepare_filename(ydl.extract_info(url, download=True))
        except Exception as exc:
            raise VideoError("Das Video ließ sich von dieser Seite nicht laden. Lade die Videodatei direkt hoch.") from exc
    try:
        with requests.get(url, stream=True, timeout=120, headers={"User-Agent": "Mozilla/5.0"}) as resp:
            if resp.status_code != 200:
                raise VideoError(f"Die Vorlage ist nicht abrufbar ({resp.status_code})")
            size = 0
            with open(target, "wb") as out:
                for chunk in resp.iter_content(1 << 16):
                    size += len(chunk)
                    if size > settings.MAX_SOURCE_BYTES:
                        raise VideoError("Die Vorlage ist größer als 200 MB")
                    out.write(chunk)
    except requests.RequestException as exc:
        raise VideoError("Die Vorlage ist nicht abrufbar") from exc
    return str(target)


def _run(args, what):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=600)
    except FileNotFoundError as exc:
        raise VideoError("ffmpeg ist auf dem Server nicht installiert") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise VideoError(f"{what} ist fehlgeschlagen. Ist die Datei wirklich ein Video?") from exc


def duration(path):
    out = _run([settings.FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path)], "Die Längenprüfung")
    try:
        seconds = float(out.stdout.decode().strip())
    except ValueError:
        raise VideoError("Die Länge der Vorlage ließ sich nicht bestimmen")
    if seconds <= 0:
        raise VideoError("Die Vorlage ist leer")
    return seconds


def first_frame(path, folder):
    target = folder / "frame.jpg"
    _run([settings.FFMPEG_BIN, "-y", "-i", str(path), "-frames:v", "1", "-q:v", "2", str(target)], "Das Auslesen des ersten Bildes")
    return target


def normalize(path, folder, *, audio, trim=None):
    """H.264, gerade Kantenlängen, schnell startend — das Format, das Kling annimmt.
    audio=True behält den Ton (zum späteren Zurücklegen), False entfernt ihn."""
    target = folder / ("mit-ton.mp4" if audio else "ohne-ton.mp4")
    args = [settings.FFMPEG_BIN, "-y", "-i", str(path), "-c:v", "libx264", "-preset", "veryfast",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    args += ["-c:a", "aac", "-b:a", "128k"] if audio else ["-an"]
    if trim:
        args += ["-t", str(trim)]
    _run(args + ["-movflags", "+faststart", str(target)], "Das Umrechnen der Vorlage")
    return target


def mux_audio(video_path, audio_source, folder):
    """Ton der Vorlage auf das (stumme) Ergebnis legen. None, wenn die Vorlage keinen Ton hat."""
    target = folder / "fertig.mp4"
    try:
        subprocess.run([settings.FFMPEG_BIN, "-y", "-i", str(video_path), "-i", str(audio_source),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                        "-shortest", "-movflags", "+faststart", str(target)], check=True, capture_output=True, timeout=600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return target


def fetch(url, target):
    """Eine schon gespeicherte Datei (Anbieter, Airtable) laden."""
    try:
        resp = requests.get(url, timeout=180)
    except requests.RequestException as exc:
        raise VideoError("Eine gespeicherte Datei ist gerade nicht abrufbar") from exc
    if resp.status_code != 200:
        raise VideoError("Eine gespeicherte Datei ist gerade nicht abrufbar")
    target.write_bytes(resp.content)
    return target
