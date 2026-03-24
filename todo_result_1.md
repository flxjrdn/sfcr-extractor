# Ergebnis ToDo 1

Am 2026-03-24 wurde `todos.md` auf Basis von `diagnosis.md` um konkrete Folgeaufträge ergänzt.

Abgeleitete Auftragsblöcke:
- Sicherheit & UI
- Testbarkeit & Verträge
- Extraktion & Verifikation
- Seitenlogik & Summary-Konsistenz
- Packaging & CLI
- Konfiguration & Datenintegrität
- Repo-Hygiene

Neu eingetragene Folgeaufträge:
- `2.1` bis `8.1` in `todos.md`

Wesentliche Ableitungen aus der Diagnose:
- Die Sicherheitsprobleme wurden in getrennte Aufträge für UI-Härtung und sichere Dev-Konfiguration überführt.
- Die Testprobleme wurden in isolierbare Arbeitspakete für Testsammlung, grüne Test-Suite und den stabilen `verifier_notes`-Vertrag zerlegt.
- Die Robustheits- und Datenqualitätsprobleme wurden in eigene Aufträge für Status-Schema, Evidence-Seiten, Verifikationslogik und konsistente Seitenzuordnung überführt.
- Packaging-, CLI-, Konfigurations- und Datenintegritätsprobleme wurden als eigenständige Aufträge formuliert, damit sie unabhängig bearbeitet und verifiziert werden können.
- Die Ausnahme aus ToDo 1 wurde berücksichtigt: `sfcr.sqlite` bleibt ausdrücklich im Repository und ist nur als Sonderfall in der Repo-Hygiene dokumentiert.

Offene Rückfragen:
- Keine.

Blocker:
- Keine. `process_stop` wurde nicht angelegt.
