1. DONE: Ergänze diese ToDo-Liste mit Aufträgen, um die in diagnosis.md genannten Fehler und Probleme zu beheben. Einzige Ausnahme: sfcr.sqlite soll im Repo bleiben, damit die Demo direkt funktioniert. 
Die toDos hier haben das Format 
Nr. Auftrag: Auftragstext, also entsprechend diesem ToDo.
Für zusammenhängende Themen können auch Aufträge in Unternummern aufgeteilt werden, also 2.1, 2.2 usw. In diesem Fall darf aber in der Obernummer nicht das Schlüsselwort "Auftrag: " stehen, da das die Bearbeitung des Todos auslöst und dann das Haupttodo durchgeführt werden würde, das ja in Untertodos aufgeteilt ist. 

2. Sicherheit & UI
2.1 Auftrag: Härte die Streamlit-UI gegen HTML-/XSS-Injection, indem datengetriebene Tabellen nicht mehr ungefiltert per `unsafe_allow_html=True` gerendert werden; nutze stattdessen sicheres Escaping oder native Streamlit-Komponenten und ergänze eine passende Regression-Absicherung.
2.2 Auftrag: Schärfe die Devcontainer- bzw. lokale UI-Startkonfiguration, sodass CORS- und XSRF-Schutz nicht pauschal deaktiviert werden; falls Ausnahmen für lokale Entwicklung nötig sind, müssen sie explizit dokumentiert und bewusst aktivierbar sein.

3. Testbarkeit & Verträge
3.1 Auftrag: Verhindere, dass `scripts/test_ollama.py` bei der `pytest`-Sammlung echte Netzwerk-Requests ausführt, und stelle sicher, dass die Test-Suite ohne laufenden Ollama-Dienst gestartet werden kann.
3.2 Auftrag: Analysiere und behebe die aktuell fehlschlagenden Tests, sodass die Test-Suite wieder grün wird; berücksichtige dabei insbesondere den gebrochenen Vertrag rund um `verifier_notes`.
3.3 Auftrag: Stelle für `verifier_notes` einen stabilen maschinenlesbaren Vertrag mit strukturierten Codes statt freiem Fließtext her und sichere ihn durch Tests gegen erneute Regressionsfehler ab.

4. Extraktion & Verifikation
4.1 Auftrag: Mache Extraktionsprompt und Pydantic-Schema für Feld-`status` konsistent, indem `ambiguous` entweder vollständig unterstützt oder aus Prompt, Parsing und Folgebehandlung entfernt wird.
4.2 Auftrag: Ermittle und speichere für Evidence die tatsächliche Fundstelle statt pauschal `page_start`, damit Seitennachweise und nachgelagerte Prüfungen auf korrekten Seiten basieren.
4.3 Auftrag: Überarbeite die Verifikationslogik so, dass text- bzw. evidenzbasierte Scale-/Unit-Ermittlung Vorrang vor modellgelieferten Angaben erhält und Ratio-Widersprüche nicht mehr nur als weiche Notiz behandelt werden.

5. Seitenlogik & Summary-Konsistenz
5.1 Auftrag: Vereinheitliche die Seitenzuordnung zwischen Extraktion und Summarization, damit erkannte PDF-Offsets und physische Seiten in beiden Verarbeitungsschritten identisch behandelt werden.

6. Packaging & CLI
6.1 Auftrag: Bereinige Packaging und Installation, indem Runtime-Abhängigkeiten vollständig und konsistent in den Paketmetadaten gepflegt, ein funktionierendes `dev`-Extra definiert und Inkonsistenzen zu `requirements.txt` aufgelöst werden.
6.2 Auftrag: Stelle sicher, dass für reguläre Paket- und Wheel-Installationen alle zur Laufzeit benötigten Ressourcen mitgeliefert werden, insbesondere Konfigurationsdateien, Katalogdaten, Overrides und die UI-Komponenten.
6.3 Auftrag: Mache die CLI robust nutzbar, indem Importpfade vor Modulimporten korrekt gesetzt werden und fehlgeschlagene UI-Starts nicht stillschweigend mit `check=False` unterdrückt werden.

7. Konfiguration & Datenintegrität
7.1 Auftrag: Behebe die Pfad- und Initialisierungsprobleme in der Konfiguration, sodass `data_dir`, `pdfs_dir` und `output_dir` deterministisch relativ zum Projekt aufgelöst werden und das Erzeugen von `Settings` keine unnötigen Dateisystem-Seiteneffekte mehr auslöst.
7.2 Auftrag: Aktiviere SQLite-Foreign-Keys zuverlässig pro Verbindung und ergänze Tests, damit referenzielle Integrität und `ON DELETE CASCADE` tatsächlich wirksam sind.

8. Repo-Hygiene
8.1 Auftrag: Bereinige Repo-Hygiene und Ignore-Regeln für typische Artefakte wie `.DS_Store`, `__MACOSX`, `*.jsonl` und nicht benötigte SQLite-Dateien, ohne die im Auftrag ausdrücklich ausgenommene Demo-Datenbank `sfcr.sqlite` aus dem Repository zu entfernen.
