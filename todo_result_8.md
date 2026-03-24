# Ergebnis ToDo 8.1

Am 2026-03-24 wurde ToDo `8.1` im aktuellen Workspace umgesetzt und verifiziert. Die Repo-Hygiene ist jetzt auf typische Generator- und Plattformartefakte ausgerichtet, ohne die ausdrücklich ausgenommene Demo-Datenbank `artifacts/sfcr.sqlite` aus dem Repository zu entfernen.

Getroffene Richtungsentscheidungen:
- Die Ignore-Logik wird zentral in [.gitignore](.gitignore#L1) gepflegt und nicht über verstreute Tool-Sonderfälle, damit Artefakte unabhängig vom Entstehungsweg konsistent ausgeschlossen werden.
- SQLite-Dateien werden standardmäßig ignoriert; die Demo-Datenbank [artifacts/sfcr.sqlite](artifacts/sfcr.sqlite#L1) bleibt als explizite Ausnahme bewusst versioniert.
- Bereits fehlplatzierte Laufartefakte sollen nicht nur künftig ignoriert werden, sondern auch aus dem Workspace-Bestand verschwinden; deshalb wurde das versionierte JSONL-Artefakt `ace_playbook.jsonl` gelöscht statt nur stillschweigend weiter mitzuschleppen.

Umgesetzte Änderungen:
- [.gitignore](.gitignore#L1) ignoriert jetzt zusätzlich typische Build-, Cache- und Plattformartefakte wie `.tmp/`, `build/`, `dist/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store` und `__MACOSX/`.
- [.gitignore](.gitignore#L13) ignoriert jetzt generierte `*.jsonl`-Dateien, sodass Laufprotokolle und Autobuild-Spuren nicht mehr versehentlich im Repo landen.
- [.gitignore](.gitignore#L18) ignoriert jetzt generische SQLite-Dateien inklusive Sidecars (`*.sqlite`, `*.sqlite-journal`, `*.sqlite-shm`, `*.sqlite-wal`) und lässt über [.gitignore](.gitignore#L22) die Demo-DB [artifacts/sfcr.sqlite](artifacts/sfcr.sqlite#L1) explizit zu.
- Das bisher versionierte Artefakt `ace_playbook.jsonl` wurde aus dem Workspace entfernt; künftige gleichartige Dateien fallen jetzt unter die neuen Ignore-Regeln.
- [tests/test_repo_hygiene.py](tests/test_repo_hygiene.py#L1) ergänzt eine Regression, die die Ignore-Regeln gegen echtes `git check-ignore` absichert und zusätzlich verlangt, dass `ace_playbook.jsonl` im Workspace gelöscht ist und nun ignoriert wird.

Regression-Absicherung:
- Die neue Repo-Hygiene-Regression schlägt fehl, sobald `.DS_Store`, `__MACOSX`, `*.jsonl` oder generische SQLite-Artefakte nicht mehr von Git ignoriert werden.
- Die Ausnahme-Regression schlägt fehl, sobald `artifacts/sfcr.sqlite` versehentlich unter die generischen SQLite-Ignore-Regeln fällt.
- Die JSONL-Regression schlägt fehl, sobald `ace_playbook.jsonl` wieder im Workspace auftaucht oder nicht mehr unter die `*.jsonl`-Ignore-Regel fällt.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 15:53:05 CET: Sichtprüfung gegen [diagnosis.md](diagnosis.md#L81) und [.gitignore](.gitignore#L1): Die dort bemängelten fehlenden Ignore-Regeln für `*.jsonl`/`*.sqlite` sowie typische ZIP-/macOS-Artefakte sind jetzt abgedeckt, die Demo-DB bleibt ausdrücklich erhalten.
- Lauf am 2026-03-24 15:53:05 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_repo_hygiene.py` war erfolgreich mit `3 passed in 0.04s`.
- Lauf am 2026-03-24 15:53:05 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_packaging.py tests/test_repo_hygiene.py` war erfolgreich mit `12 passed in 1.58s`.

Restrisiken / nicht-blockierende Hinweise:
- Bereits existierende lokale Artefaktdateien in einem bestehenden Working Tree verschwinden durch `.gitignore` nicht rückwirkend automatisch; sie werden nur künftig nicht mehr neu erfasst.
- Die Demo-Datenbank [artifacts/sfcr.sqlite](artifacts/sfcr.sqlite#L1) bleibt bewusst ein versionierter Sonderfall. Weitere SQLite-Dateien unter `artifacts/` wären weiterhin ignoriert und müssten bei echtem Bedarf explizit freigegeben werden.

Offene Rückfragen:
- Keine.
