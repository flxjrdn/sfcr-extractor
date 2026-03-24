## Statusupdate 2026-03-24

Die nachfolgenden Befunde sind der historische Ausgangsstand vor Umsetzung der ToDos `2.X` bis `8.X`. Auf Basis der umgesetzten ToDos und der dokumentierten Verifikation ist der Status der ursprünglichen Diagnosepunkte jetzt wie folgt:

1. Behoben durch ToDo `2.1`: Die UI rendert datengetriebene Tabellen nicht mehr über `unsafe_allow_html=True`; dynamische KPI-Inhalte werden escaped.
2. Behoben durch ToDo `2.2`: Der Dev-/Lokallauf verwendet sichere Streamlit-Defaults; unsichere CORS-/XSRF-Deaktivierung ist nur noch per explizitem localhost-Opt-in möglich.
3. Behoben durch ToDos `3.1` und `3.2`: Die Test-Sammlung löst keine Ollama-Requests mehr aus und die Suite ist im aktuellen Workspace grün.
4. Behoben durch ToDo `4.1`: `status="ambiguous"` ist in Prompt, Schema und Folgebehandlung konsistent unterstützt.
5. Behoben durch ToDo `5.1`: Extraktion und Summarization verwenden dieselbe PDF-Seitenoffset-Logik.
6. Behoben durch ToDo `4.2`: Evidence-Seiten werden nur noch bei tatsächlicher Lokalisierung des `source_text` gespeichert.
7. Behoben durch ToDo `4.3`: Evidenz-/Textsignale haben Vorrang vor Modellangaben; Ratio-Widersprüche blockieren Verifikation.
8. Behoben durch ToDo `3.3`: `verifier_notes` haben wieder einen stabilen strukturierten Maschinenvertrag.
9. Behoben durch ToDos `6.1` und `6.2`: Paketmetadaten, Extras und mitgelieferte Laufzeitressourcen sind konsistent abgesichert.
10. Behoben durch ToDo `6.3`: Die CLI setzt Importpfade vor Modulimports und propagiert UI-Startfehler korrekt.
11. Behoben durch ToDo `7.1`: Konfigurationspfade werden deterministisch relativ zum Projekt aufgelöst; `Settings()` bleibt seiteneffektfrei.
12. Behoben durch ToDo `7.2`: SQLite-Foreign-Keys werden pro Verbindung aktiviert und bestehende Default-Datenbanken werden in einen FK-konsistenten Zustand überführt.
13. Behoben durch ToDo `8.1`: Repo-Hygiene-Regeln decken die beanstandeten Artefakte ab; die Demo-DB bleibt bewusst versioniert.

Aktueller Verifikationsstand im Workspace:
- Lauf am 2026-03-24 16:12:52 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `112 passed, 2 warnings in 2.09s`.
- Die verbliebenen Warnungen betreffen Pydantic-Deprecations in [sfcr/config.py](sfcr/config.py); sie waren nicht Teil der ursprünglichen Diagnose-ToDos.
- Das generierte Artefakt `ace_playbook.jsonl` war im aktuellen Workspace zwischenzeitlich erneut vorhanden und wurde in diesem Lauf wieder entfernt, damit die Repo-Hygiene-Regression dem dokumentierten Zielzustand entspricht.

## Ursprüngliche Diagnose

Ich habe das Repo statisch geprüft und die wichtigsten Teile lokal ausprobiert. Mein Fazit: **die Grundidee ist gut, aber das Repo hat mehrere echte Schwachstellen in Sicherheit, Packaging, Testbarkeit und Datenintegrität**. Ein Teil davon ist schnell behebbar, ein Teil sitzt tiefer in der Extraktionslogik.

## Die wichtigsten Probleme

1. **Latente HTML-/XSS-Schwachstelle in der Streamlit-UI**

   * In `tools/ui_app.py:270-272` wird `styled.to_html(index=False)` direkt mit `st.markdown(..., unsafe_allow_html=True)` gerendert.
   * In dieselbe Tabelle fließen u. a. `source_note`/`Hinweise` aus `final_values` ein (`tools/ui_app.py:237-247`).
   * Ich habe lokal geprüft: `pandas.Styler.to_html()` lässt HTML-Tags wie `<script>` und `<b>` in der Ausgabe stehen. In Kombination mit `unsafe_allow_html=True` ist das ein klarer Injection-Pfad.
   * Streamlit dokumentiert ausdrücklich, dass `unsafe_allow_html=True` HTML rendert und dass benutzerdefiniertes HTML Sicherheits- und Wartungsrisiken mit sich bringt. ([Streamlit Docs][1])

2. **Unsichere Dev-Server-Konfiguration**

   * In `.devcontainer/devcontainer.json:22` wird Streamlit mit `--server.enableCORS false --server.enableXsrfProtection false` gestartet.
   * Auch wenn das nur für den Devcontainer gedacht ist: so ein Kommando wird oft kopiert. Für eine Web-App ist das eine unnötige Aufweichung.
   * Die Streamlit-Doku beschreibt beide Optionen explizit als Sicherheitsmechanismen; Standard ist jeweils `true`. ([Streamlit Docs][2])

3. **Die Test-Suite ist aktuell kaputt**

   * `pytest -q` scheitert schon bei der Sammlung, weil `scripts/test_ollama.py` als Test erkannt wird und **beim Import sofort** einen echten Request an `localhost:11434` absetzt (`scripts/test_ollama.py:16-32`).
   * Danach habe ich gezielt `pytest -q sfcr` ausgeführt: **44 Tests bestanden, 6 schlugen fehl**.
   * Das ist kein Schönheitsfehler, sondern ein echter Qualitätsindikator: der aktuelle Stand ist nicht testgrün.

4. **Prompt und Schema widersprechen sich**

   * Der Extraktionsprompt erlaubt `status="ambiguous"` (`sfcr/extract/extractor.py:199, 227`).
   * Das Pydantic-Schema erlaubt aber nur `Literal["ok", "not_found"]` (`sfcr/extract/schema.py:8, 20-25`).
   * Wenn das Modell der Anweisung folgt und `"ambiguous"` liefert, crasht `ResponseLLM.model_validate_json(raw)` statt sauber damit umzugehen.
   * Das ist ein echter Robustheitsbug.

5. **Die Seitenzuordnung ist inkonsistent zwischen Extraction und Summary**

   * In der Extraktion wird ein PDF-Page-Offset erkannt und auf Abschnittsseiten aufgeschlagen (`sfcr/extract/extractor.py:276-313`).
   * In der Summarization werden die Seiten aus der Ingestion **direkt** verwendet (`sfcr/summarize/summarize.py:23-37, 46-55, 128-129`).
   * Das sieht nach einem Logikbruch aus: Bei PDFs mit Vorspann/Roman-Nummerierung können Summaries auf anderen physischen Seiten landen als die Extraktion.
   * Ich würde das als **wahrscheinlichen Data-Quality-Bug** einordnen.

6. **Evidence/Page-Provenance ist zu grob und oft falsch**

   * In `LLMExtractor.extract()` wird die Evidence-Seite immer auf `page_start` gesetzt (`sfcr/extract/extractor.py:180-187`).
   * Damit ist die gespeicherte Seitennummer nicht die echte Fundstelle, sondern nur der Start des Abschnitts.
   * Folge: DB-Seitenangaben sind ungenau, und die spätere Scale-Inferenz nutzt häufig den falschen Seitentext.

7. **Der Verifier vertraut dem Modell an der falschen Stelle**

   * In `sfcr/extract/verify.py:215-226` gewinnt die **modellgelieferte** Skalierung vor der aus Quelltext/Seitentext abgeleiteten Skalierung.
   * Gerade Scale/Unit sind klassische Halluzinationsfelder; hier sollte die textbasierte Evidenz Vorrang haben.
   * Zusätzlich ist die Ratio-Prüfung zu weich: bei Abweichungen wird nur eine Notiz angehängt (`sfcr/extract/verify.py:301-307`), der Wert kann trotzdem `verified=True` bleiben (`:318`).

8. **Vertragsbruch bei `verifier_notes`**

   * Die fehlschlagenden Tests zeigen, dass `verifier_notes` offenbar früher maschinenlesbare Codes wie `looks_like_prev_year_value` oder `ratio_mismatch` erwartete.
   * Der Code schreibt jetzt freie deutsche Sätze (`sfcr/extract/verify.py:63-64, 307, 331`).
   * Damit brechen Tests und potenziell auch Downstream-Auswertungen. Für interne Pipelines sind strukturierte Codes stabiler als Freitext.

9. **Packaging/Installation ist inkonsistent**

   * `Makefile:48-50` nutzt `pip install -e .[dev]`, aber `pyproject.toml` definiert **kein** `dev`-Extra.
   * `pyproject.toml:5` enthält nur einen Teil der Laufzeit-Abhängigkeiten; wichtige Pakete wie `streamlit`, `pandas`, `pyyaml`, `python-dotenv`, `requests`, `openai` fehlen dort ganz oder teilweise.
   * `requirements.txt` ergänzt zwar einiges, aber auch dort fehlen `requests` und `openai`.
   * Ich habe zusätzlich ein Wheel gebaut: darin fehlten `sfcr/extract/fields.yaml`, `data/catalog.csv`, `data/manual_overrides.yaml` und `tools/ui_app.py`. Das heißt: **eine reguläre Wheel-Installation ist funktional unvollständig**.

10. **CLI ist fragil und teils nicht direkt nutzbar**

    * In `scripts/cli.py` werden `sfcr.*`-Module importiert, **bevor** das Repo-Verzeichnis in `sys.path` eingefügt wird (`scripts/cli.py:11-26`).
    * Lokal reproduzierbar: `python scripts/cli.py ui` endet mit `ModuleNotFoundError: No module named 'sfcr'`, wenn das Paket nicht vorher installiert wurde.
    * Dazu kommt: `ui_cmd()` startet Streamlit mit `check=False` (`scripts/cli.py:395-404`) und verschluckt damit Fehler unnötig.

11. **Pfad- und Config-Bugs**

    * `sfcr/config.py:66-67` prüft `if not self.data_dir:`. Für `Path("data")` ist das praktisch nie `False`; dadurch wird `data_dir` im Gegensatz zu `pdfs_dir`/`output_dir` nicht sauber auf `project_root` aufgelöst.
    * Das macht das Verhalten vom aktuellen Arbeitsverzeichnis abhängig.
    * Zusätzlich hat das `Settings`-Objekt Seiteneffekte beim Erzeugen von Verzeichnissen (`computed_field` + `model_post_init`, `sfcr/config.py:46-77`). Konfiguration sollte idealerweise nicht schon beim Instanziieren das Dateisystem verändern.

12. **SQLite-Foreign-Keys sind deklariert, aber faktisch nicht aktiviert**

    * In `sfcr/db.py:22-30` wird pro Verbindung kein `PRAGMA foreign_keys = ON` gesetzt.
    * Die Tabellen definieren zwar Foreign Keys und `ON DELETE CASCADE`, aber in SQLite sind Foreign Keys standardmäßig deaktiviert und müssen pro Verbindung aktiviert werden. ([SQLite][3])
    * Praktisch heißt das: die referenzielle Integrität ist schwächer als das Schema suggeriert.

13. **Repo-Hygiene**

    * Im ZIP stecken `__MACOSX/`, `.DS_Store` und eine echte `artifacts/sfcr.sqlite`.
    * `.gitignore` ignoriert weder `*.jsonl` noch `*.sqlite` (`.gitignore:1-6`).
    * Für ein Code-Repo ist das unnötig laut und erhöht das Risiko, Build-Artefakte oder Datenbankstände versehentlich mitzuschleppen.

## Was ich zuerst beheben würde

1. **UI härten**: `unsafe_allow_html=True` nur für statisches CSS/Markup verwenden, nicht für datengetriebene Tabellen; Tabelle escapen oder mit nativen Streamlit-Komponenten rendern.
2. **Tests reparieren**: `scripts/test_ollama.py` umbenennen oder unter `if __name__ == "__main__":` kapseln; dann die 6 fehlschlagenden Unit-Tests sauber grün machen.
3. **Schema/Prompt konsistent machen**: `ambiguous` entweder sauber unterstützen oder aus dem Prompt entfernen.
4. **Packaging bereinigen**: echte Runtime-Dependencies in `pyproject.toml`, `dev`-Extras definieren, Package-Data explizit mitliefern.
5. **Datenintegrität verbessern**: `PRAGMA foreign_keys=ON`, strukturierte `verifier_notes`, echte Evidence-Seiten statt `page_start`.
6. **Page-Offset vereinheitlichen**: dieselbe Logik für Extraction und Summarization.

In Summe würde ich den Stand als **brauchbaren Prototypen, aber noch nicht als sauberes produktionsreifes Repo** einstufen.

[1]: https://docs.streamlit.io/develop/api-reference/text/st.markdown "https://docs.streamlit.io/develop/api-reference/text/st.markdown"
[2]: https://docs.streamlit.io/develop/api-reference/configuration/config.toml "https://docs.streamlit.io/develop/api-reference/configuration/config.toml"
[3]: https://www.sqlite.org/foreignkeys.html "https://www.sqlite.org/foreignkeys.html"
