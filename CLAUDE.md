# CLAUDE.md

OG Scale: Nischen, Content, AliRemote. Ein Nutzer. Siehe @README.md.

## Regeln

- **Eigenständig.** Dieses Repo hat nichts mit `agency-hub-rebuild` zu tun. Dort
  nur lesen, nie schreiben. Abläufe werden neu und schlank gebaut; der Wortlaut
  der Prompts wird übernommen, damit die Ergebnisse gleich aussehen.
- **Nur die drei Bereiche.** Keine Rollen, kein Billing, kein Metricool, kein Grok.
- **Je eine Implementierung:** ein KI-Aufruf (`app/llm.py`), eine Auftrags-Laufzeit
  (`app/jobs.py`), ein Speicher-Zugang (`app/store/`), ein Zugang zu Bild/Video
  (`app/media/`), Einstellungen nur in
  `app/settings.py`. Zeit immer mit `settings.TIMEZONE` (Europe/Berlin).
- **KI-Ausgaben prüfen, bevor etwas gespeichert wird.** Alles oder nichts.
- **Kein Auftrag bleibt hängen:** jeder Handler ist entweder wiederaufnehmbar
  oder wird nach einem Neustart als fehlgeschlagen markiert.
- **Bezahlte Aufträge nie blind wiederholen.** Quittung vor dem Senden speichern;
  bei unklarer Antwort stehen lassen, bis der Nutzer »Erneut versuchen« drückt.
- **Fehler sind sichtbar.** Ein fehlgeschlagener Auftrag zeigt nie „fertig".
- Tabellen und Felder stehen nur in `app/store/schema.py`.
- Der Browser spricht nur über `frontend/app/api/proxy` mit dem Backend.
- Oberfläche auf Deutsch, Farben und Schriften nur über die Variablen in
  `frontend/app/globals.css`.
- Geheimnisse nur in `.env` / Umgebungsvariablen, nie im Repo.

## Vor „fertig"

`cd backend && python -m pytest` und `cd frontend && npx tsc --noEmit && npm run build`
ausführen und das Ergebnis zeigen. Oberflächen-Änderungen im Browser ansehen.
