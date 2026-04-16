# Ergebnis ToDo 9.1

Am 2026-03-24 wurde ToDo `9.1` aus `todos.md` umgesetzt.

Gesamtfazit:
- Die in [diagnosis.md](diagnosis.md) benannten Themen aus den Blöcken `2.X` bis `8.X` sind im aktuellen Workspace im Sinne der ursprünglichen Diagnosepunkte geschlossen. Die unten aufgeführten nicht-blockierenden Restpunkte und Folgehinweise bleiben dabei ausdrücklich bestehen. Der aktuelle Gesamtlauf `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war am 2026-03-24 16:12:52 CET erfolgreich mit `112 passed, 2 warnings in 2.09s`.

Überblick über die umgesetzten Arbeiten aus ToDo `2.X` bis `8.X`:
- `2.1`: Die Streamlit-UI rendert datengetriebene Tabellen jetzt sicher über native Komponenten statt über ungefiltertes HTML; dynamische KPI-Inhalte werden escaped und durch UI-Tests abgesichert.
- `2.2`: Der Devcontainer- und lokale UI-Start laufen standardmäßig mit aktivem CORS-/XSRF-Schutz; der frühere unsichere Modus ist nur noch per explizitem localhost-Opt-in verfügbar und dokumentiert.
- `3.1`: `scripts/test_ollama.py` führt beim Import keine Netzwerkzugriffe mehr aus und blockiert die `pytest`-Sammlung nicht länger.
- `3.2`: Die damals fehlschlagende Test-Suite wurde repariert; optionale `fitz`-Imports und stabile Verifier-Notecodes sorgen dafür, dass die Suite wieder grün läuft.
- `3.3`: `verifier_notes` wurden von Freitext auf einen strukturierten, maschinenlesbaren Vertrag mit festen Codes umgestellt; DB-Import und Tests prüfen den Vertrag explizit.
- `4.1`: `ambiguous` ist jetzt als regulärer Status über Prompt, Schema, Parsing und Verifikation konsistent unterstützt.
- `4.2`: Evidence-Seiten werden nicht mehr pauschal aus `page_start` abgeleitet, sondern nur noch bei lokalisierbarer Fundstelle gespeichert.
- `4.3`: Text-/evidenzbasierte Unit- und Scale-Ermittlung hat Vorrang vor Modellangaben; Ratio-Widersprüche führen nicht mehr nur zu einer weichen Notiz, sondern blockieren `verified=True`.
- `5.1`: Extraktion und Summarization teilen sich nun dieselbe PDF-Seitenoffset-Logik, sodass Seitenangaben konsistent auf physische PDF-Seiten zeigen.
- `6.1`: Packaging und Installation wurden auf deklarative Paketmetadaten vereinheitlicht; das `dev`-Extra ist vorhanden, und das optionale `openai`-Extra ist sauber getrennt dokumentiert.
- `6.2`: Laufzeitressourcen wie `fields.yaml`, Katalogdaten, Overrides, Policy und UI-Komponente werden in Wheel und `sdist` mitgeliefert; Default-CLI-Pfade nutzen die paketierten Ressourcen.
- `6.3`: Die CLI setzt Importpfade robust vor Modulimports und propagiert fehlgeschlagene UI-Starts mit echtem Fehlercode.
- `7.1`: Konfigurationspfade werden deterministisch relativ zum Projekt aufgelöst; `Settings()` erzeugt keine Verzeichnisse mehr beim bloßen Instanziieren.
- `7.2`: SQLite-Foreign-Keys werden pro Verbindung aktiviert; bestehende Default-Datenbanken werden vor Nutzung in einen FK-konsistenten Zustand überführt.
- `8.1`: `.gitignore` deckt die beanstandeten Artefakte wie `.DS_Store`, `__MACOSX`, `*.jsonl` und generische SQLite-Dateien ab; `artifacts/sfcr.sqlite` bleibt bewusst versioniert.

Bewertung der in `diagnosis.md` genannten Themen:
- Diagnosepunkt `1` ist behoben durch ToDo `2.1`.
- Diagnosepunkt `2` ist behoben durch ToDo `2.2`.
- Diagnosepunkt `3` ist behoben durch ToDos `3.1` und `3.2`.
- Diagnosepunkt `4` ist behoben durch ToDo `4.1`.
- Diagnosepunkt `5` ist behoben durch ToDo `5.1`.
- Diagnosepunkt `6` ist behoben durch ToDo `4.2`.
- Diagnosepunkt `7` ist behoben durch ToDo `4.3`.
- Diagnosepunkt `8` ist behoben durch ToDo `3.3`.
- Diagnosepunkt `9` ist behoben durch ToDos `6.1` und `6.2`.
- Diagnosepunkt `10` ist behoben durch ToDo `6.3`.
- Diagnosepunkt `11` ist behoben durch ToDo `7.1`.
- Diagnosepunkt `12` ist behoben durch ToDo `7.2`.
- Diagnosepunkt `13` ist behoben durch ToDo `8.1`.

Verbliebene Lücken / Anmerkungen:
- Die ursprünglichen Diagnosepunkte sind geschlossen, aber im aktuellen Workspace bestehen weiterhin zwei nicht-blockierende Pydantic-Deprecation-Warnings in [sfcr/config.py](sfcr/config.py).
- Für ToDo `2.1` fehlt weiterhin eine explizite End-to-End-Regression des UI-`main()`-Pfads; die vorhandenen Tests decken Hilfsfunktionen und den direkten Rendering-Wrapper ab, nicht den vollständigen Seitenaufbau.
- Die sichere Umstellung aus ToDo `2.1` von HTML-Tabellen auf `st.dataframe(...)` kann weiterhin bekannte, aber nicht sicherheitskritische UI-Abweichungen gegenüber der früheren HTML-Darstellung mit sich bringen.
- ToDo `4.1` schließt den Prompt-/Schema-Widerspruch, aber `ambiguous` hat downstream weiterhin keine eigene fachliche Semantik: der Zustand wird wie andere Nicht-`ok`-Fälle behandelt, also ohne kanonische Zahl und ohne separate Folgeauswertung.
- Die Evidenzlokalisierung aus ToDo `4.2` bleibt heuristisch: bei paraphrasiertem oder mehrfach vorkommendem `source_text` wird konservativ keine Seite oder die erste passende Seite im Span verwendet.
- `source_text` bleibt auch nach ToDo `4.3` das stärkste Evidenzsignal. Wenn dieser Ausschnitt halluzinierte Unit-/Scale-Tokens enthält, kann er lokalisierte Seitensignale weiterhin übersteuern.
- Die Ratio-Ableitung aus ToDo `4.3` ist weiterhin gezielt auf `sii_ratio_pct` zugeschnitten.
- Die Seitenlogik aus ToDo `5.1` ist für die produktiv genutzte arabische Offset-Behandlung vereinheitlicht; eine explizite Nutzung von `offset_roman` bleibt weiterhin ein separates Folge-Thema.
- Seit ToDo `5.1` schreiben Summary-Ausgaben physische PDF-Seiten statt logischer Ingestion-Seiten. Das behebt den Diagnosefehler, ist aber eine bewusst verbleibende Koordinatenänderung für Downstream-Verbraucher.
- Für ToDo `6.2` fehlen weiterhin gezielte Laufzeit-Regressionen dafür, dass paketierte Fallbacks für Katalog-/Override-Ressourcen auch dann tatsächlich greifen, wenn entsprechende Workspace-Dateien fehlen.
- Das paketierte [sfcr/data/catalog.csv] enthält weiterhin repo-lokale PDF-Pfade; das ist für die Mitlieferung tolerierbar, macht den Katalog aber nicht vollständig selbsttragend.
- Das optionale `openai`-Extra ist weiterhin nicht versionsbegrenzt; das ist ein nicht-blockierendes Reproduzierbarkeitsrisiko.
- Die AST-basierte Packaging-Regression aus ToDo `6.1` deckt weiterhin nur Runtime-Code unter `sfcr/` ab. Eine gleichwertige AST-Abdeckung für Python-Pfade außerhalb von `sfcr/` bleibt als offene Reviewer-Anmerkung bestehen.
- `verifier_notes` sind zwar strukturiert, werden aus Kompatibilitätsgründen in `extractions.issues` aber weiterhin als JSON-String in einer `TEXT`-Spalte gespeichert.
- Der Vertrag aus ToDo `7.1` bleibt bewusst dezentral: künftige neue Schreibpfade müssen ihr Zielverzeichnis weiterhin explizit an der jeweiligen Schreibstelle per `mkdir(...)` anlegen.
- Im Reparaturpfad aus ToDo `7.2` werden verwaiste historische `final_values`-Altzeilen weiterhin verworfen statt konserviert; das ist für die abgeleitete Tabelle vertretbar, bleibt aber eine bewusste Bereinigungsentscheidung.
- `connect(..., readonly=True)` legt weiterhin vor dem Öffnen das Elternverzeichnis an, weil der `mkdir(...)`-Pfad noch vor der Readonly-Verzweigung liegt.
- Repo-Hygiene bleibt ein laufender Prozess: `.gitignore` verhindert neues Einchecken typischer Artefakte, bereinigt aber bestehende lokale Altartefakte in vorhandenen Working Trees nicht rückwirkend automatisch.
- Ignorierte Generatorartefakte wie `ace_playbook.jsonl` müssen deshalb bei erneutem Auftauchen weiterhin aktiv aus dem Working Tree entfernt werden.

Liste evtl noch erforderlicher Arbeiten durch den Nutzer:
- Für produktive Nutzung mit `PROVIDER=openai` muss weiterhin das optionale Extra installiert werden, also z. B. `make install-openai`, und `OPENAI_API_KEY` muss gesetzt sein.
- Bereits vorhandene oder erneut auftauchende ignorierte Artefakte wie `ace_playbook.jsonl`, `.DS_Store`, `__MACOSX` oder zusätzliche `*.sqlite`-/`*.jsonl`-Dateien müssen bei Bedarf weiterhin manuell aus dem Working Tree entfernt werden; `.gitignore` verhindert ihr erneutes Einchecken, bereinigt bestehende Altartefakte aber nicht rückwirkend.
- Falls für die UI-Härtung aus ToDo `2.1` zusätzlich Vertrauen in den vollständigen Seitenaufbau benötigt wird, sollte der Nutzer/Maintainer noch eine End-to-End-Regression über den `main()`-Pfad ergänzen und die Darstellung der `st.dataframe(...)`-Variante fachlich abnehmen.
- Falls Downstream-Skripte, Reports oder Auswertungen bisher `start_page`/`end_page` bzw. Evidenzseiten als logische Ingestion-Seiten interpretiert haben, müssen sie nach ToDo `5.1` auf physische PDF-Seiten umgestellt oder entsprechend übersetzt werden.
- Falls `ambiguous` downstream fachlich anders behandelt werden soll als generische Nicht-`ok`-Fälle, muss dafür noch eine eigene Semantik in Reports, Auswertungen oder Folgeprozessen definiert werden.
- Wenn künftig zusätzliche Prozent- oder Verhältnisfelder mit eigener Sollformel geprüft werden sollen, muss die feldspezifische Ratio-Logik erweitert werden.
- Wenn paketierte Katalog-/Override-Fallbacks auch bei fehlenden Workspace-Dateien explizit verlässlich abgesichert werden sollen, sollte noch ein gezielter Laufzeit-Test für diesen Installationspfad ergänzt werden.
- Wenn der Katalog außerhalb des Repository-Kontexts als vollständig portable Paketressource dienen soll, müssen die darin enthaltenen PDF-Pfade vom Nutzer bzw. Maintainer auf ein distributionsunabhängiges Konzept umgestellt werden.
- Wenn auch Python-Pfade außerhalb von `sfcr/` packaging-seitig gegen undeclarierte Drittanbieter-Imports abgesichert werden sollen, muss die AST-basierte Importanalyse aus `tests/test_packaging.py` entsprechend erweitert werden.
- Wenn weitere Schreibpfade hinzukommen, muss an diesen Stellen die Verzeichniserzeugung explizit mitgedacht werden; `Settings()` übernimmt das bewusst nicht mehr zentral.
- Wenn historische Altartefakte oder verworfene Legacy-Zeilen rückwirkend aufbewahrt bzw. separat migriert werden sollen, braucht es eine zusätzliche Bereinigungs- oder Archivierungsentscheidung außerhalb des bisherigen Muss-Umfangs.
- Wenn die Pydantic-Deprecation-Warnings vor einer späteren Pydantic-v3-Migration verschwinden sollen, ist ein separates Cleanup in [sfcr/config.py](sfcr/config.py) erforderlich.

Dokumentationsstand:
- [diagnosis.md] wurde in diesem Lauf um eine Statuszusammenfassung ergänzt, die den Ausgangsbefund klar vom aktuellen Stand trennt.
- Weitere Änderungen in [README.md] waren in diesem Lauf nicht erforderlich, weil die relevanten Sicherheits-, Installations- und UI-Hinweise bereits in den vorherigen ToDo-Blöcken nachgezogen wurden.

Offene Rückfragen:
- Keine.
