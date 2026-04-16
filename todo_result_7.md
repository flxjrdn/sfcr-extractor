# Ergebnis ToDo 7.1

Am 2026-03-24 wurde ToDo `7.1` im aktuellen Workspace erneut geprüft und belastbar abgesichert. Die eigentlichen Produktionsänderungen für deterministische Pfadauflösung und seiteneffektfreie `Settings` waren bereits vorhanden; in diesem Lauf wurden die vom Review bemängelte Test- und Dokumentationslücke geschlossen.

Getroffene Richtungsentscheidungen:
- Die Pfadauflösung bleibt zentral in [sfcr/config.py](sfcr/config.py#L9), damit alle Aufrufer dieselbe Normalisierung für relative und absolute Pfade nutzen.
- Abgeleitete Output-Pfade wie `output_dir_ingest` bleiben berechnende Konfigurationswerte; Verzeichnisse werden ausschließlich an echten Schreibstellen angelegt.
- Die Reviewer-Lücke wird nicht nur textlich abgeschwächt, sondern mit einem expliziten CLI-Regressionstest für `ingest-dir` geschlossen.

Umgesetzte Änderungen:
- [sfcr/config.py](sfcr/config.py#L27) normalisiert `project_root`, `data_dir`, `pdfs_dir` und `output_dir` als `Path` und löst sie in [sfcr/config.py](sfcr/config.py#L44) konsistent relativ zu `project_root` auf. Damit hängt die Konfiguration nicht mehr vom aktuellen Arbeitsverzeichnis ab.
- [sfcr/config.py](sfcr/config.py#L56) berechnet `output_dir_ingest`, `output_dir_extract` und `output_dir_summaries` ohne Dateisystemzugriffe; `Settings()` bleibt seiteneffektfrei.
- [scripts/cli.py](scripts/cli.py#L91) erzeugt das effektive Ingest-Zielverzeichnis explizit mit `effective_out.mkdir(...)`, direkt bevor die `.ingest.json` geschrieben wird.
- [tests/test_cli.py](tests/test_cli.py#L157) ergänzt jetzt die bislang fehlende Regression für `ingest-dir`: Der Test startet über `get_settings()` mit einem nicht existierenden `output_dir_ingest`, prüft die Verzeichniserzeugung und verifiziert die geschriebenen Ingest-Daten.
- [tests/test_config.py](tests/test_config.py#L8) sichert weiterhin ab, dass relative Konfigurationspfade trotz fremdem `cwd` gegen `project_root` aufgelöst werden. [tests/test_config.py](tests/test_config.py#L30) prüft jetzt zusätzlich explizit, dass auch `data_dir` und `pdfs_dir` neben `output_dir` und den abgeleiteten Output-Pfaden bei `Settings(...)` nicht angelegt werden.

Regression-Absicherung:
- Die Config-Regression schlägt fehl, sobald `data_dir`, `pdfs_dir` oder `output_dir` wieder vom aktuellen Arbeitsverzeichnis statt von `project_root` abhängen.
- Die Seiteneffekt-Regression schlägt fehl, sobald `Settings()` oder ein Zugriff auf die abgeleiteten Output-Pfade wieder implizit Verzeichnisse erzeugt; sie umfasst jetzt auch `data_dir` und `pdfs_dir`.
- Die neue CLI-Regression schlägt fehl, sobald `ingest-dir` den konfigurierten Ingest-Ausgabeordner nicht mehr selbst anlegt oder trotz erfolgreicher CLI-Ausführung keine valide `.ingest.json` schreibt.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 15:25:43 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_config.py` war erfolgreich mit `2 passed, 2 warnings in 0.06s`.
- Lauf am 2026-03-24 15:25:43 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_cli.py` war erfolgreich mit `6 passed, 2 warnings in 0.37s`.
- Lauf am 2026-03-24 15:25:43 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `100 passed, 2 warnings in 1.91s`.

Restrisiken / nicht-blockierende Hinweise:
- Die bekannten Pydantic-Deprecation-Warnings zu `Field(..., env=...)` in [sfcr/config.py](sfcr/config.py#L24) und [sfcr/config.py](sfcr/config.py#L25) bestehen weiterhin. Sie betreffen nicht den Muss-Umfang von `7.1`.
- Der Vertrag bleibt bewusst: Konfigurationsobjekte erzeugen keine Output-Verzeichnisse vorab. Künftige neue Schreibpfade müssen deshalb wie [scripts/cli.py](scripts/cli.py#L91) ihr Zielverzeichnis explizit an der Schreibstelle anlegen.

Offene Rückfragen:
- Keine.



# Ergebnis ToDo 7.2

Am 2026-03-24 wurde ToDo `7.2` im aktuellen Workspace nachgezogen und erneut verifiziert. Die frühere Überzeichnung ist bereinigt: Die Härtung gilt jetzt nicht mehr nur für neu initialisierte oder explizit migrierte Datenbanken, sondern auch für die mitgelieferte Default-Datenbank [artifacts/sfcr.sqlite](artifacts/sfcr.sqlite) und die normalen Startpfade, die diese Datei verwenden.

Getroffene Richtungsentscheidungen:
- Die Aktivierung von `PRAGMA foreign_keys=ON` bleibt zentral in [sfcr/db.py](sfcr/db.py#L22), damit jede geöffnete SQLite-Verbindung denselben FK-Vertrag erzwingt.
- Die Schema-Reparatur bleibt in `init_db(...)`, aber die relevanten Default-Einstiegspunkte rufen diese Reparatur jetzt auch tatsächlich vor der Nutzung der Default-DB auf.
- Historisch inkonsistente Kindzeilen in bestehenden Datenbanken werden beim Reparaturpfad entfernt, damit der Zustand nach der Initialisierung nicht nur für `final_values`, sondern für den gesamten FK-Baum gegen `documents(doc_id)` konsistent ist.

Umgesetzte Änderungen:
- [sfcr/db.py](sfcr/db.py#L29) ergänzt `_table_exists(...)` als gemeinsame Grundlage für migrationsartige Reparaturen bestehender DB-Dateien.
- [sfcr/db.py](sfcr/db.py#L65) migriert ein Legacy-`final_values` weiterhin auf ein echtes `documents(doc_id)`-Foreign-Key-Schema mit `ON DELETE CASCADE`.
- [sfcr/db.py](sfcr/db.py#L102) ergänzt `_delete_orphan_rows(...)`; [sfcr/db.py](sfcr/db.py#L130) repariert damit beim `init_db(...)` nun auch historisch verwaiste Kindzeilen in `extractions`, `summaries` und `final_values`, sodass `PRAGMA foreign_key_check` danach leer ist.
- [scripts/cli.py](scripts/cli.py#L395) ruft vor `db-load` jetzt immer `db_init()` auf. Der normale Default-CLI-Pfad migriert die Standard-DB damit vor jedem Laden.
- [sfcr/ui_app.py](sfcr/ui_app.py#L222) ruft vor dem ersten Lesen der Default-DB jetzt `init_db(db_path)` auf. Der normale UI-Startpfad liest die Standard-DB damit nicht mehr im Legacy-Zustand.
- Die mitgelieferte Default-Datenbank [artifacts/sfcr.sqlite](artifacts/sfcr.sqlite) wurde im aktuellen Workspace explizit auf den gehärteten Stand migriert; `final_values` enthält dort jetzt selbst den FK auf `documents(doc_id)`.
- [tests/test_db.py](tests/test_db.py#L210) kopiert den tatsächlichen Repo-Snapshot von `artifacts/sfcr.sqlite`, führt `init_db(...)` darauf aus und verlangt danach sowohl den `final_values`-FK als auch einen leeren `PRAGMA foreign_key_check`.
- [tests/test_cli.py](tests/test_cli.py#L260) deckt den normalen `db-load`-Startpfad gegen einen kopierten Default-DB-Snapshot ab und verifiziert, dass der Pfad die DB vor dem Laden auf einen FK-konsistenten Zustand bringt.
- [tests/test_ui_app.py](tests/test_ui_app.py#L131) sichert zusätzlich ab, dass die UI vor `list_documents(...)` explizit `init_db(...)` auf dem Default-Pfad ausführt.

Regression-Absicherung:
- Die Verbindungs-Regression schlägt fehl, sobald `connect(...)` wieder ohne aktivierte SQLite-FKs zurückkehrt.
- Die Schema-Regression schlägt fehl, sobald `final_values` wieder ohne `documents(doc_id)`-Referenz oder ohne `ON DELETE CASCADE` ausgeliefert oder migriert wird.
- Die Repo-Snapshot-Regression schlägt fehl, sobald `init_db(...)` eine bestehende Default-DB nicht mehr vollständig in einen FK-konsistenten Zustand überführt.
- Die CLI-Regression schlägt fehl, sobald `db-load` die Default-DB wieder ohne vorherige Initialisierung/Migration benutzt.
- Die UI-Regression schlägt fehl, sobald die Anwendung die Default-DB wieder liest, bevor `init_db(...)` gelaufen ist.

Verifikation in der aktuellen Workspace-Umgebung:
- Nach `PYTHONPATH=. python -c 'from pathlib import Path; from sfcr.db import init_db; init_db(Path("artifacts/sfcr.sqlite"))'` zeigte `artifacts/sfcr.sqlite` in `.schema final_values` den Foreign Key auf `documents(doc_id)`, und `PRAGMA foreign_key_check` war leer.
- Lauf am 2026-03-24 15:44:44 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_db.py` war erfolgreich mit `9 passed, 2 warnings in 0.11s`.
- Lauf am 2026-03-24 15:44:44 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_cli.py` war erfolgreich mit `7 passed, 2 warnings in 0.39s`.
- Lauf am 2026-03-24 15:44:44 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_ui_app.py` war erfolgreich mit `4 passed, 2 warnings in 0.08s`.
- Lauf am 2026-03-24 15:44:44 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `109 passed, 2 warnings in 2.04s`.

Restrisiken / nicht-blockierende Hinweise:
- `final_values`-Altzeilen ohne referenziertes Dokument werden beim Migrationspfad weiterhin verworfen statt konserviert. Das ist für diese abgeleitete Tabelle vertretbar, weil sie rekonstruierbar ist.
- `connect(..., readonly=True)` legt weiterhin vor dem Öffnen das Elternverzeichnis an, weil [sfcr/db.py](sfcr/db.py#L118) das `mkdir(...)` noch vor der Readonly-Verzweigung ausführt. Das war vom Reviewer explizit als nicht-blockierend für `7.2` markiert und wurde in diesem Lauf nicht mitgezogen.
- Die bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py#L24) und [sfcr/config.py](sfcr/config.py#L25) bestehen weiterhin und waren nicht Teil dieses Auftrags.

Offene Rückfragen:
- Keine.
