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
| Content | noch nicht gebaut |
| AliRemote | noch nicht gebaut |

Der Airtable-Client ist nur gegen einen nachgestellten Server getestet, noch
nicht gegen eine echte Base.

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
