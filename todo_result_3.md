# Ergebnis ToDo 3.1

Am 2026-03-24 wurde ToDo `3.1` aus `todos.md` umgesetzt.

Umgesetzte Änderungen:
- [scripts/test_ollama.py](scripts/test_ollama.py) führt beim Modulimport keine Netzwerkzugriffe und kein `SystemExit` mehr aus. Der bisherige Inline-Ablauf wurde in `request_ollama()` und `main()` gekapselt und wird nur noch unter `if __name__ == "__main__":` explizit gestartet.
- Der Fehlerpfad behandelt jetzt gezielt `requests.RequestException` und liefert Exit-Code `1` erst bei bewusster Skriptausführung, statt bereits die `pytest`-Sammlung zu sprengen.
- Neue Regressionen in [tests/test_test_ollama.py](tests/test_test_ollama.py) stellen sicher, dass der Import des Skripts keinen `requests.post(...)` auslöst und dass der Ollama-Request nur beim expliziten Aufruf von `main()` erfolgt.

Regression-Absicherung:
- `test_importing_script_does_not_call_ollama()` patcht `requests.post` auf einen harten Fehler und lädt [scripts/test_ollama.py](scripts/test_ollama.py) per `importlib`; der Test wäre sofort rot, falls beim Import wieder ein Netzwerkaufruf eingeführt wird.
- `test_main_calls_ollama_only_when_explicitly_executed()` prüft den bewussten Laufpfad von `main()`, inklusive Request-Ziel, Payload und Erfolgsausgabe.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 12:23:28 CET: `pytest -q tests/test_test_ollama.py` war erfolgreich mit `2 passed in 0.04s`.
- Lauf am 2026-03-24 12:23:28 CET: `python -m compileall scripts/test_ollama.py tests/test_test_ollama.py` war erfolgreich mit Exit-Code `0`.
- Lauf am 2026-03-24 12:23:28 CET: `pytest -q` startete ohne laufenden Ollama-Dienst erfolgreich in die Sammlung und scheiterte nicht mehr an [scripts/test_ollama.py](scripts/test_ollama.py). Der Lauf brach erst später mit separaten Importfehlern wegen fehlendem `fitz`/PyMuPDF in `sfcr/extract/tests/test_evidence_hash.py`, `sfcr/extract/tests/test_extractor.py` und `sfcr/ingest/tests/test_subsections_spans.py` ab.

Restrisiken / nicht-blockierende Hinweise:
- ToDo `3.1` behebt nur den Sammlungs-/Netzwerk-Seiteneffekt. Weitere fachliche oder bestehende Testfehler der Suite sind nicht Teil dieses Auftrags und bleiben Gegenstand von ToDo `3.2`.
- Die aktuelle Workspace-Umgebung hat weiterhin ein Abhängigkeitsproblem rund um `fitz` (PyMuPDF). Das ist für den hier erledigten Sammel-Fix nicht blocker-relevant, verhindert aber weiterhin einen vollständig grünen Gesamtlauf.

Offene Rückfragen:
- Keine.


# Ergebnis ToDo 3.3

Am 2026-03-24 wurde ToDo `3.3` aus `todos.md` umgesetzt.

Umgesetzte Änderungen:
- [sfcr/extract/schema.py](sfcr/extract/schema.py) definiert für `verifier_notes` jetzt einen expliziten Maschinenvertrag als Liste strukturierter Note-Objekte mit festem `code`-Feld. Zulässige Codes sind über `VerifierNoteCode` eingeschränkt; `VerifiedExtraction` dedupliziert doppelte Codes deterministisch statt unstrukturierte Strings oder `;`-verkettete Texte zu akzeptieren.
- [sfcr/extract/verify.py](sfcr/extract/verify.py) erzeugt `verifier_notes` nun konsequent als strukturierte Codes, einschließlich der bisherigen Fälle `no_value_or_not_ok`, `value_not_found_in_source_text`, `looks_like_prev_year_value` und `ratio_mismatch`. Der Rückgabevertrag ist damit maschinenlesbar und mehrwertig, ohne auf String-Parsing angewiesen zu sein.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py) verwendet denselben Vertrag auch im Orchestrierungsfehlerfall ohne passende Section/Subsection und serialisiert `no_section` als strukturierten Note-Code statt als Freitext.
- [sfcr/db.py](sfcr/db.py) validiert jede JSONL-Zeile beim Import jetzt explizit gegen `VerifiedExtraction` und serialisiert erst danach `verifier_notes` kontrolliert nach JSON. Der DB-Importpfad akzeptiert damit keine Legacy-Strings wie `"ratio_mismatch"` mehr; nur strukturierte Note-Objekte gelangen in die TEXT-Spalte `issues`.

Regression-Absicherung:
- [sfcr/extract/tests/test_verify.py](sfcr/extract/tests/test_verify.py) prüft jetzt nicht mehr String-Contains, sondern den strukturierten Code-Vertrag direkt. Neue Tests sichern ab, dass mehrere Notes in stabiler Reihenfolge als `[{\"code\": ...}]` serialisiert werden, dass Legacy-Strings für `verifier_notes` vom Schema abgewiesen werden und dass doppelte Codes dedupliziert werden.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py) wurde auf den neuen `no_section`-Vertrag umgestellt, damit der Orchestrierungsfehlerpfad ebenfalls gegen Regressionen abgesichert ist.
- [tests/test_db.py](tests/test_db.py) deckt den DB-Importpfad jetzt in beiden Richtungen ab: ein Persistenztest verifiziert, dass strukturierte `verifier_notes` als JSON-Text in `extractions.issues` landen, und ein zweiter Test stellt sicher, dass ein Legacy-String im Feld `verifier_notes` beim Import mit `ValidationError` abgewiesen wird.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 12:44:46 CET: `PYTHONPATH=. pytest -q tests/test_db.py sfcr/extract/tests/test_verify.py sfcr/extract/tests/test_extractor.py` war erfolgreich mit `25 passed, 2 warnings in 0.11s`.
- Lauf am 2026-03-24 12:44:46 CET: `python -m compileall sfcr/db.py tests/test_db.py sfcr/extract/schema.py sfcr/extract/verify.py sfcr/extract/extractor.py sfcr/extract/tests/test_verify.py sfcr/extract/tests/test_extractor.py` war erfolgreich mit Exit-Code `0`.
- Lauf am 2026-03-24 12:44:46 CET: `PYTHONPATH=. pytest -q` war erfolgreich mit `66 passed, 2 warnings in 0.16s`.

Restrisiken / nicht-blockierende Hinweise:
- Die SQLite-Spalte `extractions.issues` bleibt aus Kompatibilitätsgründen `TEXT`. Der neue strukturierte Vertrag wird dort deshalb als JSON-String abgelegt. Eine echte relationale oder JSON-native DB-Modellierung ist nicht Teil von ToDo `3.3`.
- Die bereits bekannten Pydantic-Deprecation-Warnings in [sfcr/config.py](sfcr/config.py) bestehen weiter und waren nicht Gegenstand dieses Auftrags.

Offene Rückfragen:
- Keine.


# Ergebnis ToDo 3.2

Am 2026-03-24 wurde ToDo `3.2` aus `todos.md` umgesetzt.

Umgesetzte Änderungen:
- [sfcr/extract/verify.py](sfcr/extract/verify.py) verwendet für `verifier_notes` wieder stabile, testbare Codes statt teilweisem Freitext. Konkret werden die betroffenen Fälle jetzt als `no_value_or_not_ok`, `value_not_found_in_source_text`, `looks_like_prev_year_value` und `ratio_mismatch` serialisiert.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py) importiert PyMuPDF (`fitz`) nur noch optional auf Modulebene. Der eigentliche PDF-Zugriff wird erst in `extract_text_pages()` erzwungen; die Offset-Erkennung fällt bei fehlendem `fitz` kontrolliert auf einen neutralen Zustand zurück, sodass die testbaren Orchestrierungsfunktionen nicht schon beim Import oder am Heuristik-Schritt scheitern.
- [sfcr/ingest/sfcr_ingest.py](sfcr/ingest/sfcr_ingest.py) behandelt `fitz` ebenfalls optional bis zur tatsächlichen PDF-Nutzung in `PDFLoader`. Dadurch bleiben rein logische Tests für Abschnitts- und Unterabschnitts-Spans ohne installierte PDF-Bibliothek ausführbar.
- [sfcr/extract/tests/test_verify.py](sfcr/extract/tests/test_verify.py) wurde verschärft: die Regression prüft die relevanten `verifier_notes` jetzt auf exakte stabile Codes statt nur auf Teilstrings.

Analyse der ursprünglichen Fehler:
- Der Gesamtlauf scheiterte zunächst bereits in der Test-Sammlung mit `ModuleNotFoundError: No module named 'fitz'`, weil [sfcr/extract/extractor.py](sfcr/extract/extractor.py) und [sfcr/ingest/sfcr_ingest.py](sfcr/ingest/sfcr_ingest.py) PyMuPDF beim Modulimport voraussetzten.
- Nach Isolierung dieser Importfehler blieben in [sfcr/extract/tests/test_verify.py](sfcr/extract/tests/test_verify.py) zwei fachliche Vertragsverletzungen übrig: `looks_like_prev_year_value` und `ratio_mismatch` wurden nicht als maschinenstabile Codes, sondern als deutscher Freitext ausgegeben.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 12:29:17 CET: `pytest -q sfcr/extract/tests/test_verify.py` war erfolgreich mit `13 passed in 0.06s`.
- Lauf am 2026-03-24 12:29:17 CET: `pytest -q sfcr/extract/tests/test_extractor.py sfcr/extract/tests/test_evidence_hash.py sfcr/ingest/tests/test_subsections_spans.py` war erfolgreich mit `10 passed in 0.08s`.
- Lauf am 2026-03-24 12:29:17 CET: `pytest -q` war erfolgreich mit `61 passed, 2 warnings in 0.14s`.
- Lauf am 2026-03-24 12:29:17 CET: `python -m compileall sfcr/extract/verify.py sfcr/extract/extractor.py sfcr/ingest/sfcr_ingest.py sfcr/extract/tests/test_verify.py` war erfolgreich mit Exit-Code `0`.

Restrisiken / nicht-blockierende Hinweise:
- Die Gesamtsuite ist in dieser Workspace-Umgebung jetzt grün, es bleiben aber zwei bereits bekannte Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py) (`Field(..., env=...)`). Diese Warnings waren nicht Gegenstand von ToDo `3.2`.
- `verifier_notes` ist mit diesem Fix wieder stabil genug für die bestehende Test-Suite, bleibt aber weiterhin ein einzelnes String-Feld. Die weitergehende Umstellung auf einen expliziten strukturierten Maschinenvertrag bleibt Gegenstand von ToDo `3.3`.

Offene Rückfragen:
- Keine.
