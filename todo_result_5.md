# Ergebnis ToDo 5.1

Am 2026-03-24 wurde ToDo `5.1` aus `todos.md` umgesetzt.

Getroffene Richtungsentscheidung:
- Die Seitenauflösung für Summary und Extraktion wurde nicht separat nachgezogen, sondern in einen gemeinsamen Helper zentralisiert. Dadurch verwenden beide Pfade dieselbe Übersetzung von logischen Ingestion-Seiten auf physische PDF-Seiten inklusive identischer Offset-Anwendung und Bounds-Clamping.
- Summary-JSONLs schreiben `start_page` und `end_page` jetzt in derselben physischen PDF-Seitenlogik wie die Extraktion. Das beseitigt den in `diagnosis.md` beschriebenen Koordinatenbruch zwischen extrahierten Evidenzseiten und Abschnittssummaries.
- `sfcr/summarize/summarize.py` importiert `fitz` jetzt analog zur Extraktion fehlertolerant und bricht erst bei tatsächlicher PDF-Nutzung mit einer klaren Runtime-Meldung ab. Das war kein Primärziel von ToDo `5.1`, ist aber die saubere Folge daraus, dass die neue Summary-Regression ohne installiertes PyMuPDF importierbar bleiben musste.

Umgesetzte Änderungen:
- [sfcr/utils/page_ranges.py](sfcr/utils/page_ranges.py#L10) führt mit `PdfPageOffsetInfo`, `load_pdf_page_offset_info(...)` und `resolve_pdf_page_span(...)` einen zentralen Resolver für PDF-Seitenoffsets ein. Der Helper kapselt die bisher nur im Extraktor vorhandene Offset-Erkennung und sorgt für einheitliches Clamping auf reale PDF-Seiten.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L406) nutzt die Offset-Erkennung jetzt über den gemeinsamen Helper und löst jede Ingestion-Section/Subsection über [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L447) mit `resolve_pdf_page_span(...)` auf, bevor Text gelesen, der Prompt gebaut und Evidence-Seiten lokalisiert werden.
- [sfcr/summarize/summarize.py](sfcr/summarize/summarize.py#L51) ergänzt `_resolve_sections_to_pdf_pages(...)` und wendet in [sfcr/summarize/summarize.py](sfcr/summarize/summarize.py#L240) denselben Offset-Resolver vor dem eigentlichen Summary-Lauf auf alle Sections an. Damit werden sowohl die gelesenen PDF-Seiten als auch die in JSONL geschriebenen `start_page`-/`end_page`-Werte in physischer Seitenlogik vereinheitlicht.
- [sfcr/summarize/summarize.py](sfcr/summarize/summarize.py#L90) schützt den Summary-Pfad zusätzlich gegen fehlendes `PyMuPDF`, sodass Modulimport und Tests nicht schon bei der Sammlung an `ModuleNotFoundError: fitz` scheitern.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L558) ergänzt eine Regression dafür, dass der Extraktionspfad den neuen gemeinsamen Resolver tatsächlich benutzt und logische Seiten `3..4` bei erkanntem Offset `+2` als physische Seiten `5..6` lädt.
- [sfcr/summarize/test_summarize.py](sfcr/summarize/test_summarize.py#L26) ergänzt den fehlenden End-to-End-Test für Summary-Offsets: ein erkannter Offset `+3` verschiebt die gelesenen und persistierten Seiten konsistent von `2..3` auf `5..6` bzw. von `7..8` auf `10..11`. [sfcr/summarize/test_summarize.py](sfcr/summarize/test_summarize.py#L98) sichert den Nullfall ab, dass ohne erkannten Offset die Ingestion-Seiten unverändert bleiben.

Regression-Absicherung:
- Die neue Summary-Regression schließt genau die bisher offene Lücke aus `diagnosis.md`: die Summarization liest und schreibt bei erkannter PDF-Verschiebung nun dieselben physischen Seiten, auf denen auch die Extraktion arbeitet.
- Die neue Extraktions-Regression stellt sicher, dass beide Verarbeitungsschritte wirklich denselben Resolver verwenden und künftig nicht erneut auseinanderlaufen, wenn die Offset-Behandlung angepasst wird.
- Das zusätzliche Bounds-Clamping im gemeinsamen Helper verhindert nebenbei, dass negative oder übergroße Offset-Ergebnisse unterschiedliche Seitenausschnitte zwischen Prompt, Seitentext-Lesen und Summary-Ausgabe erzeugen.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 13:57:29 CET: `python -m compileall sfcr/utils/page_ranges.py sfcr/extract/extractor.py sfcr/summarize/summarize.py sfcr/extract/tests/test_extractor.py sfcr/summarize/test_summarize.py` war erfolgreich mit Exit-Code `0`.
- Lauf am 2026-03-24 13:57:29 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q sfcr/extract/tests/test_extractor.py sfcr/summarize/test_summarize.py` war erfolgreich mit `19 passed in 0.09s`.
- Lauf am 2026-03-24 13:57:29 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `83 passed, 2 warnings in 0.13s`.

Restrisiken / nicht-blockierende Hinweise:
- Vereinheitlicht ist weiterhin nur die arabische Offset-Logik, weil auch der bisherige Extraktionspfad ausschließlich `offset_arabic` produktiv verwendet. Eine explizite Nutzung von `offset_roman` wäre ein eigenes Folge-Thema.
- Die Summary-Ausgabe verwendet jetzt physische PDF-Seiten. Falls Downstream-Verbraucher bisher implizit logische Ingestion-Seiten erwartet haben, müssen sie diese Koordinatenumstellung berücksichtigen; fachlich ist das jedoch die gewünschte Angleichung an die Extraktion.
- Die bereits bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py) bestehen unverändert und waren nicht Gegenstand dieses Auftrags.

Offene Rückfragen:
- Keine.


