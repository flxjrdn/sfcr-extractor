# Ergebnis ToDo 6.1

Am 2026-03-24 wurde der im Workspace bereits vorhandene Stand zu ToDo `6.1` erneut geprüft und als umgesetzt dokumentiert. In diesem Lauf waren keine weiteren Codeänderungen nötig, weil Packaging, Installationspfade und Regressionen den Auftrag bereits abdecken.

Getroffene Richtungsentscheidungen:
- Die Paketmetadaten in [pyproject.toml](pyproject.toml#L1) bleiben die führende Quelle für Installations- und Laufzeitabhängigkeiten; `requirements.txt` dupliziert keinen zweiten Paketkatalog.
- Der OpenAI-Provider bleibt optional und wird weiterhin über das Extra `openai` bereitgestellt, weil der Code das SDK nur bei Bedarf lädt.
- Das Basis-Setup und das OpenAI-Setup werden jetzt explizit getrennt dokumentiert, damit `make install` nicht mehr stillschweigend als hinreichend für OpenAI-basierte Aufrufe erscheint.
- Die Regression-Absicherung für Packaging prüft jetzt echte Drittanbieter-Imports im Paketcode statt nur eine feste Allowlist bekannter Paketnamen.

Umgesetzte Änderungen:
- [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json#L20) installiert im Devcontainer jetzt nur noch deklarativ über `requirements.txt`; die separate Sonderbehandlung `pip3 install --user streamlit` wurde entfernt, sodass `streamlit` ausschließlich über die Paketmetadaten aus [pyproject.toml](pyproject.toml#L1) in die Runtime gelangt.
- [Makefile](Makefile#L34) unterscheidet jetzt zwischen `make install` für `.[dev]` und `make install-openai` für `.[dev,openai]`; die Pip-Aufrufe sind zudem gequotet, damit Shell-Glob-Interpretation der Extras nicht dazwischenfunkt.
- [README.md](README.md#L85) trennt Basis-Installation und optionales OpenAI-Setup sauber, markiert `OPENAI_API_KEY` als nur für `PROVIDER=openai` erforderlich und zeigt getrennte Pipeline-Beispiele für Basis- und OpenAI-Betrieb.
- [tests/test_packaging.py](tests/test_packaging.py#L1) nutzt jetzt AST-Importanalyse über den Runtime-Code unter `sfcr/`, gleicht Pflicht-Imports gegen `project.dependencies` ab, verlangt passende Extras für optionale Imports wie `openai` und sichert zusätzlich Makefile- sowie Devcontainer-Installationspfade gegen manuelle Runtime-Sonderinstallationen ab.

Regression-Absicherung:
- Neue Drittanbieter-Imports im Paketcode schlagen jetzt fehl, wenn sie weder in `project.dependencies` noch in einem explizit zugeordneten optionalen Extra deklariert sind.
- Die Prüfung auf `requirements.txt == -e .[dev]` erzwingt weiterhin eine einzige deklarative Quelle statt zweier driftender Dependency-Listen.
- Die zusätzliche Makefile-Prüfung stellt sicher, dass die dokumentierten Installationspfade den tatsächlichen Extras `dev` bzw. `dev,openai` entsprechen.
- Die Devcontainer-Prüfung verhindert, dass Runtime-Pakete wie `streamlit` wieder außerhalb von `requirements.txt` bzw. `pyproject.toml` separat per `pip install` nachinstalliert werden.
- Die Python-`3.10`-Fallback-Absicherung über `tomli` bleibt bestehen, damit der Packaging-Test auch mit dem Mindest-Python TOML sicher lesen kann.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 14:25:46 CET: erneute Sichtprüfung gegen `todos.md`, [pyproject.toml](pyproject.toml#L1), [requirements.txt](requirements.txt#L1), [Makefile](Makefile#L1), [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json#L1), [README.md](README.md#L1) und [tests/test_packaging.py](tests/test_packaging.py#L1): die dokumentierten Maßnahmen für `6.1` sind im aktuellen Workspace konsistent vorhanden.
- Lauf am 2026-03-24 14:25:46 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_packaging.py` war erfolgreich mit `6 passed in 0.05s`.
- Lauf am 2026-03-24 14:25:46 CET: `python -m pip install --dry-run -e '.[dev]'` war erfolgreich; die Basis-Installation löst die deklarierten Runtime-Abhängigkeiten inklusive `streamlit` aus den Paketmetadaten auf.
- Lauf am 2026-03-24 14:25:46 CET: `python -m pip install --dry-run -e '.[dev,openai]'` war erfolgreich; auch das optionale Extra `openai` ist installierbar und konsistent an die Paketmetadaten angebunden.
- Lauf am 2026-03-24 14:25:46 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `89 passed, 2 warnings in 0.21s`.
- Läufe am 2026-03-24 zwischen 14:19:50 CET und 14:20:04 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_packaging.py` war erfolgreich mit `6 passed in 0.05s`.
- Läufe am 2026-03-24 zwischen 14:19:50 CET und 14:20:04 CET: `python -m pip install --dry-run -e '.[dev]'` war erfolgreich; die editable Basis-Installation löst `streamlit` jetzt weiterhin korrekt aus den Paketmetadaten auf, ohne dass der Devcontainer dafür einen separaten Installationspfad benötigt.
- Lauf am 2026-03-24 14:21:06 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `89 passed, 2 warnings in 0.21s`.

Restrisiken / nicht-blockierende Hinweise:
- Das optionale `openai`-Extra ist weiterhin nicht versionsbegrenzt; das ist ein Reproduzierbarkeitsrisiko, war laut Review für ToDo `6.1` aber kein Muss-Punkt.
- Die Reviewer-Anmerkung zur AST-Abdeckung außerhalb von `sfcr/` bleibt unverändert offen, gehört laut Zusatzhinweis aber nicht zum Muss-Umfang von ToDo `6.1`.
- ToDo `6.2` bleibt weiterhin dafür zuständig, dass bei Wheel- und Paketinstallationen auch nicht-pythonische Laufzeitressourcen vollständig mitgeliefert werden.
- Die bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py#L24) bestehen unverändert und waren nicht Gegenstand dieses Auftrags.

Offene Rückfragen:
- Keine.



# Ergebnis ToDo 6.2

Am 2026-03-24 wurde ToDo `6.2` im aktuellen Workspace erneut geprüft und gegenüber dem bereits vorhandenen Stand weiter abgesichert. Der zuvor dokumentierte Muss-Befund zum checkout-relativen UI-Startpfad bleibt geschlossen; in diesem Lauf wurde zusätzlich die bislang fehlende explizite Regression für Quellpakete (`sdist`) nachgezogen, damit der Auftrag nicht nur für Wheels, sondern auch für reguläre Paketinstallationen belastbar belegt ist.

Getroffene Richtungsentscheidungen:
- Laufzeitressourcen bleiben im Paket unter `sfcr/` gebündelt; CLI-Defaults müssen konsequent dieselben paketierten Pfade verwenden wie der übrige Runtime-Code.
- Explizite Nutzer-Overrides via `--fields` bleiben unverändert möglich; nur der Default-Fall bleibt auf die paketierte Ressource gebogen.
- Die UI-Pfadauflösung gehört für `6.2` zum Packaging-Auftrag, weil die UI-Komponente zwar mitgeliefert wurde, aus einer regulären Installation aber erst mit paketiertem Startpfad belastbar nutzbar ist.
- Die weiterhin vorhandene Verwendung von `check=False` im UI-Start bleibt ein separates CLI-Härtungsthema aus ToDo `6.3`.

Umgesetzte Änderungen:
- [scripts/cli.py](scripts/cli.py) führt neben `_resolve_fields_path(...)` jetzt auch `_resolve_ui_app_path()` ein und nutzt dafür [sfcr/runtime_resources.py](sfcr/runtime_resources.py) als führende Quelle für paketierte Runtime-Ressourcen.
- [scripts/cli.py](scripts/cli.py) verwendet im Command `ui` nicht mehr den repo-relativen String `sfcr/ui_app.py`, sondern den aufgelösten paketierten Pfad aus `bundled_ui_app_path()`. Damit bleibt der Startpfad auch außerhalb eines Checkouts korrekt.
- [scripts/cli.py](scripts/cli.py) verwendet für `extract` und `extract-dir` weiterhin den bereits nachgezogenen paketierten Default für [sfcr/extract/fields.yaml](sfcr/extract/fields.yaml).
- [tests/test_cli.py](tests/test_cli.py) ergänzt eine gezielte Regression für `ui` und prüft, dass `streamlit run` mit dem paketierten Pfad aus `bundled_ui_app_path()` aufgerufen wird.
- [tests/test_packaging.py](tests/test_packaging.py#L102) baut zusätzlich ein `sdist` über `setuptools.build_meta.build_sdist(...)` und prüft, dass `catalog.csv`, `manual_overrides.yaml`, `fields.yaml`, `policy.md` und `sfcr/ui_app.py` auch im Quellpaket enthalten sind.
- Der bereits vorhandene Packaging-/Runtime-Stand für gebündelte Ressourcen bleibt gültig: [pyproject.toml](pyproject.toml), [sfcr/db.py](sfcr/db.py), [sfcr/extract/extractor.py](sfcr/extract/extractor.py), [sfcr/ui_app.py](sfcr/ui_app.py) und [tests/test_packaging.py](tests/test_packaging.py) tragen weiterhin die eigentliche Ressourcen-Mitlieferung im Paket und Wheel.

Regression-Absicherung:
- Die CLI-Tests schlagen fehl, sobald `extract` oder `extract-dir` im Default-Fall wieder auf einen checkout-relativen `fields.yaml`-Pfad zurückfallen.
- Der neue UI-CLI-Test schlägt fehl, sobald `ui` wieder einen checkout-relativen App-Pfad statt des paketierten Pfads aus [sfcr/runtime_resources.py](sfcr/runtime_resources.py) verwendet.
- Die Packaging-Tests sichern jetzt getrennt ab, dass `catalog.csv`, `manual_overrides.yaml`, `fields.yaml`, `policy.md` und `sfcr/ui_app.py` sowohl im gebauten Wheel als auch im erzeugten Quellpaket (`sdist`) enthalten sind.
- Der Default-Fields-Test in [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py) sichert zusätzlich ab, dass die paketierte `fields.yaml` weiterhin fachlich verwertbar geladen wird.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 15:03:31 CET: Sichtprüfung gegen [pyproject.toml](pyproject.toml#L1), [sfcr/runtime_resources.py](sfcr/runtime_resources.py#L1), [scripts/cli.py](scripts/cli.py#L1) und [tests/test_packaging.py](tests/test_packaging.py#L1): die benötigten Laufzeitressourcen liegen weiter im Paketbaum, und `6.2` ist jetzt auch explizit für `sdist`-Artefakte abgesichert.
- Lauf am 2026-03-24 15:03:31 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_packaging.py` war erfolgreich mit `9 passed in 1.58s`.
- Lauf am 2026-03-24 15:03:31 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_cli.py` war erfolgreich mit `3 passed, 2 warnings in 0.18s`.
- Lauf am 2026-03-24 15:03:31 CET: `python - <<'PY' ... build_sdist(...) ... PY` war erfolgreich; das erzeugte Artefakt `sfcr_extractor-1.0.0.tar.gz` enthielt die paketierten Ressourcen ebenfalls.
- Lauf am 2026-03-24 14:57:04 CET: Sichtprüfung gegen [scripts/cli.py](scripts/cli.py), [sfcr/runtime_resources.py](sfcr/runtime_resources.py), [tests/test_cli.py](tests/test_cli.py), [tests/test_packaging.py](tests/test_packaging.py) und [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py): der bisherige Muss-Befund zum UI-Startpfad ist im aktuellen Workspace geschlossen.
- Lauf am 2026-03-24 14:57:04 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_cli.py` war erfolgreich mit `3 passed, 2 warnings in 0.18s`.
- Lauf am 2026-03-24 14:57:04 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_packaging.py sfcr/extract/tests/test_extractor.py` war erfolgreich mit `25 passed in 1.47s`.
- Lauf am 2026-03-24 14:57:04 CET: Die frühere Aussage, der UI-Launcher sei für `6.2` nur ein Restrisiko, wurde verworfen; nach der Korrektur nutzt die CLI den paketierten UI-Pfad konsistent.

Restrisiken / nicht-blockierende Hinweise:
- Die Fallbacks für [sfcr/data/catalog.csv](sfcr/data/catalog.csv) und [sfcr/data/manual_overrides.yaml](sfcr/data/manual_overrides.yaml) sind vorhanden, werden aber weiterhin nicht mit einem gezielten Laufzeit-Regressionstest für fehlende Workspace-Dateien abgesichert; für `6.2` war das laut Review kein Muss-Punkt.
- Das paketierte [sfcr/data/catalog.csv](sfcr/data/catalog.csv) verweist weiterhin auf repo-lokale PDF-Pfade unter `data/sfcrs/...`; das ist für die Mitlieferung der Ressource tolerierbar, macht die Katalogdaten im Wheel aber nicht vollständig selbsttragend.
- [scripts/cli.py](scripts/cli.py) verwendet im UI-Start weiterhin `check=False`; das ist kein Packaging-Defekt mehr, bleibt aber als CLI-Härtungspunkt Gegenstand von ToDo `6.3`.
- Die bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py) bestehen unverändert fort und waren nicht Teil dieses Auftrags.

Offene Rückfragen:
- Keine.


# Ergebnis ToDo 6.3

Am 2026-03-24 wurde ToDo `6.3` im aktuellen Workspace umgesetzt und verifiziert. Der CLI-Start ist jetzt auch dann robust, wenn [scripts/cli.py](scripts/cli.py#L1) direkt außerhalb des Repository-CWD aufgerufen wird, und fehlgeschlagene UI-Starts enden nicht mehr stillschweigend mit einem scheinbar erfolgreichen Exit-Code.

Getroffene Richtungsentscheidungen:
- Der Quellcheckout unter [sfcr/](sfcr) bleibt für direkte Aufrufe von [scripts/cli.py](scripts/cli.py#L1) die bevorzugte Importquelle; der Bootstrap setzt deshalb den Projektwurzelpfad vor allen `sfcr`-Imports.
- Der UI-Unterbefehl soll Fehler des gestarteten Streamlit-Prozesses sichtbar und maschinenlesbar propagieren; deshalb wird nicht mehr mit `check=False` weitergelaufen.
- Der bereits in `6.2` korrigierte paketierte UI-Pfad aus [sfcr/runtime_resources.py](sfcr/runtime_resources.py#L1) bleibt unverändert die führende Quelle auch für die Härtung aus `6.3`.

Umgesetzte Änderungen:
- [scripts/cli.py](scripts/cli.py#L8) bootstrapped jetzt `PROJECT_ROOT` direkt nach den Standardbibliotheksimports und fügt den Checkout-Pfad nur dann in `sys.path` ein, wenn daneben tatsächlich ein `sfcr`-Paketbaum existiert. Dadurch greifen die nachfolgenden `sfcr`-Imports in [scripts/cli.py](scripts/cli.py#L18) auch bei direkten Skriptaufrufen außerhalb des Repo-CWD belastbar auf den Workspace-Stand.
- [scripts/cli.py](scripts/cli.py#L410) startet `streamlit run` jetzt mit `check=True` und wandelt einen `CalledProcessError` in `typer.Exit(exc.returncode)` um. Damit bleibt die Fehlermeldung des Child-Prozesses sichtbar, und die CLI liefert den echten Non-Zero-Exitcode zurück.
- [tests/test_cli.py](tests/test_cli.py#L36) ergänzt eine Regression, die `python /abs/path/scripts/cli.py --help` bewusst aus einem temporären Fremdverzeichnis und ohne `PYTHONPATH` startet. Ohne den vorgezogenen Importpfad-Bootstrap würde dieser Pfad an `ModuleNotFoundError` scheitern.
- [tests/test_cli.py](tests/test_cli.py#L156) prüft jetzt explizit `check=True` für den UI-Start, und [tests/test_cli.py](tests/test_cli.py#L181) sichert ab, dass ein fehlgeschlagener Streamlit-Start mit Exit-Code `7` auch tatsächlich als CLI-Fehler zurückgegeben wird.

Regression-Absicherung:
- Der neue Starttest schlägt fehl, sobald `scripts/cli.py` wieder `sfcr` importiert, bevor der Projektwurzelpfad gesetzt ist.
- Der aktualisierte UI-Test schlägt fehl, sobald der Streamlit-Start wieder mit `check=False` aufgerufen wird.
- Der neue Fehlerpfadtest schlägt fehl, sobald ein nicht erfolgreich gestarteter UI-Prozess wieder stillschweigend als erfolgreicher CLI-Lauf endet.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 15:11:51 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q tests/test_cli.py` war erfolgreich mit `5 passed, 2 warnings in 0.37s`.
- Lauf am 2026-03-24 15:11:51 CET: `python scripts/cli.py --help` wurde aus einem temporären Verzeichnis mit entferntem `PYTHONPATH` gestartet und war erfolgreich; die Hilfe der CLI wurde vollständig angezeigt.

Restrisiken / nicht-blockierende Hinweise:
- Die bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py#L24) bestehen unverändert fort und waren nicht Gegenstand dieses Auftrags.
- Die Härtung betrifft bewusst [scripts/cli.py](scripts/cli.py#L1); der separate Runner [scripts/run_ui.py](scripts/run_ui.py#L1) blieb unverändert, weil er bereits mit `check=True` arbeitet und nicht Teil des Muss-Befunds aus `6.3` war.

Offene Rückfragen:
- Keine.
