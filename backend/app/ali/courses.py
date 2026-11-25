"""Die wählbaren Warm-up-Kurse. Reine Zeitrechnung, immer in Berliner Zeit.

Ein Schritt: (tag, art, nummer, fällig, minuten, davor, danach)
  art: warmup | native_warmup | reel | status
"""

from datetime import datetime, time, timedelta

from .. import settings

COURSES = {
    "pdf_v1": {
        "name": "Schnellstart",
        "summary": "7 Minuten Warm-up, am ersten Tag 2 Reels, danach 3 Reels pro Tag. Ab Tag 3 morgens und abends ein Konto-Check.",
    },
    "native_7": {
        "name": "Sanfter 7-Tage-Kurs",
        "summary": "Am ersten Tag nur 20 Minuten Warm-up. Ab dem zweiten Tag täglich Warm-up um 10 Uhr und ein Reel um 18 Uhr.",
    },
}


def _at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), settings.TIMEZONE)


def steps(course, t0, days=None):
    """t0: Zeitpunkt, zu dem du »Account erstellt« bestätigt hast (mit Zeitzone)."""
    days = days or settings.ALI_COURSE_DAYS
    t0 = t0.astimezone(settings.TIMEZONE)
    out = []
    if course == "pdf_v1":
        out.append((1, "warmup", 0, t0 + timedelta(minutes=3), 7, 0, 0))
        for day in range(1, days + 1):
            date = t0.date() + timedelta(days=day - 1)
            times = [t0 + timedelta(minutes=40), t0 + timedelta(minutes=160)] if day == 1 else [_at(date, 10), _at(date, 12, 30), _at(date, 15)]
            for number, due in enumerate(times, 1):
                out.append((day, "reel", number, due, 0, 2, 2))
            if day >= 3:
                for number, (hour, minute) in enumerate(((8, 30), (20, 30)), 1):
                    out.append((day, "status", number, _at(date, hour, minute), 0, 0, 0))
    elif course == "native_7":
        out.append((1, "native_warmup", 0, t0 + timedelta(minutes=3), 20, 0, 0))
        earliest = t0 + timedelta(hours=24)  # frühestens einen vollen Tag nach der Erstellung
        second = _at(earliest.date(), 10)
        if second < earliest:
            second = _at(earliest.date() + timedelta(days=1), 10)
        for day in range(2, days + 1):
            date = second.date() + timedelta(days=day - 2)
            out.append((day, "native_warmup", 0, _at(date, 10), 20, 0, 0))
            out.append((day, "reel", 1, _at(date, 18), 0, 2, 10))
    else:
        raise ValueError("Unbekannter Kurs")
    return out


def span(due, minutes, before, after):
    """Wie lange ein Schritt das Handy belegt (mit drei Minuten Puffer)."""
    return due - timedelta(minutes=before), due + timedelta(minutes=minutes + after + 3)
