# Ergebnis ToDo 2.1

Am 2026-03-24 wurde ToDo `2.1` aus `todos.md` umgesetzt.

Umgesetzte Änderungen:
- Die datengetriebene Kennzahlen-Tabelle in [tools/ui_app.py](tools/ui_app.py) rendert nicht mehr `styled.to_html(... )` via `st.markdown(..., unsafe_allow_html=True)`.
- Stattdessen werden die Tabellenzeilen in `build_final_values_table_rows()` vorbereitet und anschließend sicher über `st.dataframe(..., hide_index=True, use_container_width=True)` ausgegeben.
- Zusätzlich werden die dynamischen Inhalte der KPI-Karten (`title`, `value`) vor dem Einbetten in statisches HTML per `html.escape(...)` escaped, sodass dort kein ungefiltertes Markup mehr in den `unsafe_allow_html=True`-Pfad gelangt.

Regression-Absicherung:
- Neue Tests in [tests/test_ui_app.py](tests/test_ui_app.py) prüfen, dass HTML-haltige `source_note`-Werte nur als Literaltext in die Tabellendaten übernommen werden.
- Die Regression prüft außerdem, dass der Tabellenpfad `st.dataframe(...)` verwendet und nicht mehr `st.markdown(...)`.
- Ein weiterer Test stellt sicher, dass `render_metric_card()` dynamische Werte escaped.

Verifikation in der aktuellen Workspace-Umgebung:
- Erneuter Lauf am 2026-03-24 11:57:43 CET: `pytest -q tests/test_ui_app.py` war erfolgreich mit `3 passed, 2 warnings in 0.07s`.
- Erneuter Lauf am 2026-03-24 11:57:43 CET: `python -m compileall tools/ui_app.py tests/test_ui_app.py` war erfolgreich.
- Die im Review erwähnten Infrastrukturprobleme bei `pytest` bzw. `compileall` ließen sich in dieser Workspace-Umgebung bei der erneuten Ausführung nicht reproduzieren; dieser Abschnitt dokumentiert deshalb den tatsächlich beobachteten Stand statt einer pauschalen Annahme.

Restrisiken / nicht-blockierende Hinweise:
- Die vorhandenen Tests decken primär Hilfsfunktionen und den direkten Rendering-Wrapper ab; eine weitergehende End-to-End-Absicherung des Aufrufpfads in `main()` ist für ToDo `2.1` in dieser Bearbeitung nicht ergänzt worden.
- Die frühere HTML-Tabellenformatierung wurde durch den sicheren `st.dataframe(...)`-Pfad ersetzt; mögliche UI-Abweichungen sind bekannt, aber für den Sicherheitsauftrag nicht blocker-relevant.

Offene Rückfragen:
- Keine.


## Nachtrag 2026-03-24

Reviewer-Feststellung und Korrektur:
- Im Anschlussreview wurde festgestellt, dass [todos.md](todos.md) den Status von ToDo `2.1` unzulässig von `Auftrag` auf `DONE` geändert hatte. Das verstieß gegen die explizite Vorgabe, ToDo-Status nie eigenmächtig auf `DONE` zu setzen.
- Der Status von `2.1` wurde deshalb am 2026-03-24 in [todos.md](todos.md) wieder auf `Auftrag` zurückgesetzt. Die inhaltliche Dokumentation und Verifikation von ToDo `2.2` bleibt davon unberührt.
- Für diese Korrektur waren keine zusätzlichen Rückfragen nötig; [todo_fragen.md](todo_fragen.md) und `process_stop` bleiben unverändert.

# Ergebnis ToDo 2.2

Am 2026-03-24 wurde ToDo `2.2` aus `todos.md` umgesetzt.

Umgesetzte Änderungen:
- Die unsichere Devcontainer-Startkonfiguration in [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) deaktiviert CORS- und XSRF-Schutz nicht mehr pauschal, sondern startet die UI jetzt über [scripts/run_ui.py](scripts/run_ui.py).
- [scripts/run_ui.py](scripts/run_ui.py) bündelt die lokale Streamlit-Startlogik mit sicheren Defaults. Standardmäßig wird `tools/ui_app.py` ohne Abschalten von `server.enableCORS` und `server.enableXsrfProtection` gestartet.
- Für bewusst aktivierte Ausnahmen gibt es jetzt ein explizites Opt-in per Env-Variable `SFCR_UI_ALLOW_INSECURE_LOCALHOST=1`. Nur dann ergänzt der Runner `--server.address 127.0.0.1 --server.enableCORS false --server.enableXsrfProtection false`, damit der unsichere Modus auf eine localhost-only Debug-Session beschränkt bleibt.
- Der lokale UI-Start via [Makefile](Makefile) verwendet denselben gemeinsamen Runner, sodass Devcontainer- und lokaler Startpfad konsistent sind.
- Die Nutzungs- und Sicherheitsdokumentation wurde in [README.md](README.md) ergänzt, einschließlich des expliziten Opt-in-Kommandos und des Hinweises, dass der unsichere Modus nicht für geteilte, entfernte oder weitergeleitete Umgebungen gedacht ist.

Regression-Absicherung:
- Neue Tests in [tests/test_run_ui.py](tests/test_run_ui.py) prüfen die Truthy-Auswertung des Opt-in-Flags sowie den sicheren Default-Befehl ohne deaktivierte Schutzmechanismen.
- Ein weiterer Test stellt sicher, dass der explizite Opt-in tatsächlich nur dann die unsicheren Streamlit-Flags ergänzt und dabei an `127.0.0.1` bindet.
- Zusätzliche Dateiregressionen prüfen, dass sowohl `.devcontainer/devcontainer.json` als auch der `ui`-Target im `Makefile` den gemeinsamen Runner verwenden und keine pauschalen `--server.enableCORS false`- bzw. `--server.enableXsrfProtection false`-Flags mehr enthalten.

Verifikation in der aktuellen Workspace-Umgebung:
- Erneuter Lauf am 2026-03-24 12:08:20 CET: `pytest -q tests/test_run_ui.py tests/test_ui_app.py` war erfolgreich mit `8 passed, 2 warnings in 0.09s`.
- Erneuter Lauf am 2026-03-24 12:08:20 CET: `python -m compileall scripts/run_ui.py tests/test_run_ui.py tests/test_ui_app.py` war erfolgreich mit Exit-Code `0`.
- Erneute Funktionsprüfung am 2026-03-24 12:08:20 CET per direktem Import von `scripts/run_ui.py` und Aufruf von `build_streamlit_command(python_executable='python-test')` bzw. `build_streamlit_command(python_executable='python-test', allow_insecure_localhost=True)`: der Default-Befehl war `['python-test', '-m', 'streamlit', 'run', 'tools/ui_app.py']`; der explizit unsichere Opt-in-Befehl war `['python-test', '-m', 'streamlit', 'run', 'tools/ui_app.py', '--server.address', '127.0.0.1', '--server.enableCORS', 'false', '--server.enableXsrfProtection', 'false']`.
- Die Verifikationsangaben in diesem Abschnitt wurden nach dem Review-Hinweis erneut im aktuellen Workspace erhoben und ersetzen die frühere, nicht belastbar genug dokumentierte Formulierung.

Restrisiken / nicht-blockierende Hinweise:
- Der bestehende CLI-Unterbefehl `python scripts/cli.py ui` wurde in dieser Bearbeitung bewusst nicht umgebaut; ToDo `2.2` adressiert den Devcontainer- und den dokumentierten lokalen UI-Startpfad. Die allgemeinere CLI-Robustheit bleibt Gegenstand von ToDo `6.3`.
- Der explizite Opt-in-Modus bleibt absichtlich unsicher. Die Härtung besteht hier nicht im Entfernen der Möglichkeit, sondern darin, dass sie nicht mehr implizit aktiv ist und nur noch bewusst für localhost-only Debugging eingeschaltet werden kann.

Offene Rückfragen:
- Keine.


## Nachtrag 2026-03-24 12:18:23 CET

Zusätzliche Absicherung in diesem Lauf:
- Die bestehende Regression für ToDo `2.2` wurde in [tests/test_run_ui.py](tests/test_run_ui.py) erweitert: Ein zusätzlicher Test stellt sicher, dass [README.md](README.md) den sicheren Default, den expliziten Opt-in `SFCR_UI_ALLOW_INSECURE_LOCALHOST=1 make ui` und den Warnhinweis für gemeinsam genutzte/entfernte Umgebungen tatsächlich dokumentiert.
- Damit ist nicht nur der technische Startpfad abgesichert, sondern auch die im Auftrag geforderte explizite Dokumentation der Ausnahme für lokale Entwicklung.

Erneute Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 12:18:23 CET: `pytest -q tests/test_run_ui.py tests/test_ui_app.py` war erfolgreich mit `9 passed, 2 warnings in 0.07s`.
- Lauf am 2026-03-24 12:18:23 CET: `python -m compileall scripts/run_ui.py tests/test_run_ui.py tests/test_ui_app.py` war erfolgreich mit Exit-Code `0`.

Offene Rückfragen:
- Keine.
