# OG Scale

Ein schlanker Hub für genau drei Dinge: **Nischen**, **Content** (Motion-Reels,
Carousels, Fotos) und **AliRemote** (Instagram-Accounts auf ferngesteuerten
iPhones). Ein Nutzer, kein Rollen-System.

```
Next.js (frontend/)  ──Proxy──>  FastAPI (backend/)  ──>  Airtable (Models, Nischen, Content, Accounts)
                                       └──>  SQL (Aufträge, später der AliRemote-Plan)
```

## Stand

| Bereich | Stand |
|---|---|
| Anmeldung, Grundgerüst, Design | fertig |
| Models und Nischen | fertig |
| Viral: Quellen, Lesen, Bewertung, Import in Motion-Reels | fertig |
| Content: Referenzfotos, Carousels, Fotos, Motion-Reels | fertig |
| AliRemote: Accounts, Kurswahl, Plan, Tresor, Ausführung, Not-Stopp | fertig |
| Untertitel für Reels, Storys über AliRemote | nicht gebaut |

**Noch nie gegen die echten Dienste gelaufen.** Airtable, OpenRouter, Kie,
HikerAPI, Apify und AliRemote sind nur gegen nachgestellte Antworten getestet.
Mit `MEDIA_PROVIDER=fake` läuft alles kostenlos mit Platzhaltern und
nachgestellten Handys.

## Ausprobieren ohne Zugänge

`./demo.sh` (Mac/Linux) oder `demo.bat` (Windows) richtet alles ein und startet
den Testbetrieb unter http://localhost:3000 (Passwort `demo`). Braucht
Python 3.11+, Node 20+ und ffmpeg. `demo.bat` ist ungetestet.

## Einrichten für den echten Betrieb

Backend (`backend/.env` oder Umgebung des Servers):

| Variable | Wofür |
|---|---|
| `BACKEND_API_KEY` | gemeinsames Geheimnis mit dem Frontend (frei wählbar, lang) |
| `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID` | neue, leere Base; danach `python -m scripts.create_schema` |
| `DATABASE_URL` | Postgres für Aufträge und den AliRemote-Plan |
| `OPENROUTER_API_KEY` | Nischen |
| `KIE_API_KEY` | Bilder und Videos |
| `HIKERAPI_TOKEN` oder `APIFY_TOKEN` | Viral |
| `ALIREMOTE_TOKEN` | AliRemote |
| `PUBLIC_URL`, `CORS_ORIGINS` | Adresse des Backends, Adresse des Frontends |

Frontend (`frontend/.env.local`): `BACKEND_URL`, `BACKEND_API_KEY`, `APP_PASSWORD`, `AUTH_SECRET`.

Das Backend läuft als **ein** Prozess (`backend/Dockerfile`): Aufträge und der
AliRemote-Takt leben darin. Nicht mit mehreren Workern starten.

Erster echter AliRemote-Lauf: einen Test-Account planen, »Account erstellt«
bestätigen, Automatik einschalten und den ersten Warm-up am Handy beobachten.
Die Automations-Kennungen stehen in `app/settings.py` (`ALI_*_AUTOMATION`).

## Lokal starten

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # Werte eintragen
python -m scripts.create_schema   # legt die Airtable-Tabellen an (nur mit Airtable-Zugang)
uvicorn app.main:app --reload     # :8000
```

```bash
# Frontend
cd frontend
cp .env.local.example .env.local  # Werte eintragen
npm install
npm run dev                       # :3000
```

Ohne Airtable-Zugang läuft ein flüchtiger Demo-Speicher; mit `DEMO_SEED=1`
liegen Beispieldaten darin.

## Prüfen

```bash
cd backend && python -m pytest
cd frontend && npx tsc --noEmit && npm run build
```
