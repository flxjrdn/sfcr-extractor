# Ergebnis ToDo 4.1

Am 2026-03-24 wurde ToDo `4.1` aus `todos.md` umgesetzt.

Getroffene Richtungsentscheidung:
- `ambiguous` wurde nicht aus dem Prompt entfernt, sondern als regulärer `status` durchgängig unterstützt. Das passt zum bereits vorhandenen fachlichen Prompt-Verhalten und beseitigt den in `diagnosis.md` beschriebenen Parse-Crash, falls das Modell bei Mehrdeutigkeit tatsächlich `"ambiguous"` liefert.

Umgesetzte Änderungen:
- [sfcr/extract/schema.py](sfcr/extract/schema.py#L8) erweitert `Status` auf `Literal["ok", "not_found", "ambiguous"]`. Dadurch akzeptieren `ResponseLLM`, `ExtractionLLM` und `VerifiedExtraction` denselben dritten Zustand entlang der gesamten Extraktionskette.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L206) präzisiert den Extraktionsprompt: `not_found` steht jetzt explizit für keinen plausiblen Kandidaten, `ambiguous` für mehrere verbleibende Kandidaten. Zusätzlich nennt die Key-Liste nur noch die tatsächlich erwarteten JSON-Felder `status, value_unscaled, scale, unit, source_text`.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L208) sichert als Regression ab, dass ein LLM-Response mit `status="ambiguous"` erfolgreich geparst wird und dass der Prompt die Mehrdeutigkeits-Regel weiterhin enthält.
- [sfcr/extract/tests/test_verify.py](sfcr/extract/tests/test_verify.py#L97) erweitert die Gate-Regression für `verify_extraction(...)`: `ambiguous` bleibt als Status erhalten, führt wie andere Nicht-`ok`-Fälle zu keiner Verifikation und wird mit dem bestehenden strukturierten Note-Code `no_value_or_not_ok` behandelt. Das berücksichtigt den bereits in [todo_result_3.md](todo_result_3.md) dokumentierten `verifier_notes`-Vertrag.

Regression-Absicherung:
- Der neue Extraktor-Test stellt sicher, dass `ResponseLLM.model_validate_json(...)` bei `status="ambiguous"` nicht mehr am Schema scheitert.
- Die Prompt-Regression verhindert, dass die Status-Regeln erneut von der tatsächlich erwarteten JSON-Struktur abweichen.
- Die Verifikations-Regression stellt sicher, dass die Folgebehandlung für `ambiguous` stabil bleibt und kein Sonderfall außerhalb des bestehenden Nicht-`ok`-Pfads nötig ist.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 12:50:35 CET: `PYTHONPATH=. pytest -q sfcr/extract/tests/test_extractor.py sfcr/extract/tests/test_verify.py` war erfolgreich mit `24 passed in 0.10s`.
- Lauf am 2026-03-24 12:50:35 CET: `PYTHONPATH=. pytest -q` war erfolgreich mit `67 passed, 2 warnings in 0.17s`.
- Lauf am 2026-03-24 12:50:35 CET: `python -m compileall sfcr/extract/schema.py sfcr/extract/extractor.py sfcr/extract/tests/test_extractor.py sfcr/extract/tests/test_verify.py` war erfolgreich mit Exit-Code `0`.

Restrisiken / nicht-blockierende Hinweise:
- `ambiguous` wird jetzt technisch und fachlich akzeptiert, aber der Verifikationspfad behandelt den Zustand weiterhin bewusst wie andere Nicht-`ok`-Fälle: keine kanonische Zahl, keine Verifikation, bestehender Note-Code `no_value_or_not_ok`. Eine feinere separate Downstream-Auswertung für `ambiguous` ist nicht Teil von ToDo `4.1`.
- Die bereits bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py) bestehen unverändert und waren nicht Gegenstand dieses Auftrags.

Offene Rückfragen:
- Keine.


# Ergebnis ToDo 4.3

Am 2026-03-24 wurde ToDo `4.3` aus `todos.md` im Workspace nachgezogen und die beiden Reviewer-Muss-Punkte wurden explizit behoben.

Getroffene Richtungsentscheidung:
- Die Ratio-Härtung bleibt fachlich auf `sii_ratio_pct = 100 * eof_total / scr_total` zugeschnitten, ist jetzt aber im Repo-Standard tatsächlich erreichbar: der Default-Feldkatalog enthält das Feld wieder und der Default-CLI-Pfad kann den zweiten Ratio-Verifikationsschritt damit real auslösen.
- `verify_extraction(...)` bekommt in der Orchestrierung jetzt zusätzlich die Felderwartung `expected_unit`. Damit hängt die Ratio-Prüfung nicht mehr davon ab, ob Modell oder Evidenz zufällig bereits `%` geliefert haben; für katalogisierte Prozentfelder bleibt die Kanonisierung auf `%` fest verdrahtet.
- Der Evidenzvorrang aus ToDo `4.3` bleibt für den generischen Verifier erhalten: ohne explizite Felderwartung schlagen `source_text` bzw. lokalisierter Seitentext weiterhin modellgelieferte Unit-/Scale-Angaben.

Umgesetzte Änderungen:
- [sfcr/extract/fields.yaml](sfcr/extract/fields.yaml#L7) ergänzt `sii_ratio_pct` im Default-Katalog inklusive `%`-Unit und Ratio-spezifischen Keywords. Damit ist der von [scripts/cli.py](scripts/cli.py#L154) genutzte Standard-Workspace nicht länger blind für den Ratio-Pfad.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L230) behält die Ableitung von `ratio_check` aus verifizierten `eof_total`-/`scr_total`-Werten bei. [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L478) und [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L492) reichen jetzt zusätzlich `expected_unit=f.unit` bzw. `expected_unit=pending.field.unit` an `verify_extraction(...)` weiter.
- [sfcr/extract/verify.py](sfcr/extract/verify.py#L210) erweitert den Verifier um `expected_unit`. [sfcr/extract/verify.py](sfcr/extract/verify.py#L247) setzt für produktive Aufrufer die katalogisierte Felderwartung vor Modellangaben ein, während [sfcr/extract/verify.py](sfcr/extract/verify.py#L331) den Ratio-Check weiterhin als blockierenden Pfad behandelt.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L299) sichert neu ab, dass der Default-Feldkatalog `sii_ratio_pct` wirklich enthält. [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L1036) prüft zusätzlich, dass die Orchestrierung `%` als `expected_unit` an den Ratio-Verifier weiterreicht.
- [sfcr/extract/tests/test_verify.py](sfcr/extract/tests/test_verify.py#L212) ergänzt die bisher fehlende Regression für seitenbasierte `%`-Evidenz gegen eine falsche Modell-Unit `EUR`. [sfcr/extract/tests/test_verify.py](sfcr/extract/tests/test_verify.py#L240) deckt den reviewer-kritischen Fall ab, dass ein Ratio-Feld ohne `%`-Evidenz und mit falscher Modell-Unit trotzdem über `expected_unit="%"` korrekt geprüft und nicht am Ratio-Check vorbeigeschleust wird.

Regression-Absicherung:
- Der Default-Katalog-Test verhindert, dass `sii_ratio_pct` erneut aus dem Standard-Workflow herausfällt.
- Die neue Verifier-Regression für seitenbasierte `%`-Evidenz schließt die bisher offene Testlücke zur Unit-Korrektur aus lokalisierter Seitenumgebung.
- Die zusätzliche `expected_unit`-Regression stellt sicher, dass Ratio-Widersprüche nicht mehr allein deshalb unentdeckt bleiben, weil Modell oder Evidenz die falsche Einheit geliefert haben.
- Die bereits vorhandenen Ratio-Mismatch- und Orchestrierungs-Tests bleiben aktiv und prüfen weiter, dass `ratio_mismatch` `verified=False` erzwingt und ohne verifizierte Basisfelder kein künstlicher Sollwert erzeugt wird.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 13:47:27 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q sfcr/extract/tests/test_verify.py sfcr/extract/tests/test_extractor.py` war erfolgreich mit `37 passed in 0.11s`.
- Lauf am 2026-03-24 13:47:27 CET: `TMPDIR=$PWD/.tmp PYTHONPATH=. pytest -q` war erfolgreich mit `80 passed, 2 warnings in 0.15s`.
- Lauf am 2026-03-24 13:47:27 CET: `python -m compileall sfcr/extract/verify.py sfcr/extract/extractor.py sfcr/extract/tests/test_verify.py sfcr/extract/tests/test_extractor.py` war erfolgreich mit Exit-Code `0`.

Restrisiken / nicht-blockierende Hinweise:
- `source_text` bleibt das stärkste Evidenzsignal. Wenn dieser Ausschnitt halluzinierte Unit-/Scale-Tokens enthält, kann er lokalisierte Seitensignale weiterhin übersteuern; das Risiko ist dokumentiert, aber nicht Teil der Muss-Korrekturen zu ToDo `4.3`.
- Die Ratio-Ableitung ist weiterhin bewusst feldspezifisch auf `sii_ratio_pct` begrenzt. Weitere Prozentfelder mit eigener Sollformel würden eine explizite Erweiterung in [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L230) benötigen.
- Die bereits bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py) bestehen unverändert und waren nicht Gegenstand dieses Auftrags.

Offene Rückfragen:
- Keine.


# Ergebnis ToDo 4.2

Am 2026-03-24 wurde ToDo `4.2` aus `todos.md` umgesetzt.

Getroffene Richtungsentscheidung:
- `Evidence.page` wird nur noch gespeichert, wenn sich das modellgelieferte `source_text` gegen konkrete `page_texts` belastbar lokalisieren lässt. Ohne lokalisierbare Fundstelle wird keine Seite erfunden, auch nicht mehr als Kompatibilitäts-Fallback auf `page_start`.

Umgesetzte Änderungen:
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L149) ergänzt mit `_normalize_evidence_text(...)`, `_source_text_locators(...)` und `_locate_evidence_page(...)` einen expliziten Lokalisierungspfad für `source_text`. Dabei werden Hyphenationsnormalisierung, Whitespace-Normalisierung und bei gekürzten Snippets (`...`) mehrere Prefix-Fingerprints verwendet, um die Fundstelle robust innerhalb der geladenen Seiten zu finden.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L180) entfernt den verbliebenen `page_start`-Fallback vollständig: `_locate_evidence_page(...)` liefert jetzt `None`, wenn `page_texts` fehlen, `source_text` nicht lokalisierbar ist oder kein Treffer vorliegt. Damit kann der generelle Evidence-Erzeuger keine unbelegte Seite mehr persistieren.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L225) erzeugt in `LLMExtractor.extract(...)` `Evidence` nur noch dann, wenn `_locate_evidence_page(...)` eine tatsächlich gefundene Seite zurückliefert. `snippet_hash` bleibt an diese lokalisierte Seite gebunden.
- [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L199) nutzt `_page_text_for_evidence(...)` weiterhin als zentralen Orchestrierungshelfer. [sfcr/extract/extractor.py](sfcr/extract/extractor.py#L418) reicht in `extract_for_document(...)` nur noch den Seitentext lokalisierter Evidence an `verify_extraction(...)` weiter; ohne Evidence bleibt `page_text_for_scale=None`.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L219) sichert weiterhin den Positivfall ab: bei Treffer auf der letzten Seite eines Drei-Seiten-Spans wird exakt diese Seite gespeichert.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L299) ergänzt die fehlende Regression für Standalone-Aufrufer ohne `page_texts`: selbst mit `source_text` darf dann keine Evidence-Seite mehr erzeugt werden.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L328) ergänzt den reviewer-kritischen Ein-Seiten-Negativpfad: wenn `source_text` auf einer einzelnen Seite nicht lokalisierbar ist, bleibt `evidence=[]` statt auf `page_start` zurückzufallen.
- [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L594) und [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L695) sichern die Orchestrierung weiterhin gegen Seitendrift ab: lokalisierte Evidence steuert den an `verify_extraction(...)` weitergereichten Seitentext, fehlende Evidence erzeugt keinen Ersatz-Fallback.

Regression-Absicherung:
- Die Extraktor-Regressionen decken jetzt Positiv- und Negativpfade für Mehrseiten-Span, Ein-Seiten-Fall und fehlende `page_texts` ab. Damit ist explizit abgesichert, dass `Evidence.page` nie mehr aus bloßem `page_start` konstruiert wird.
- Die Orchestrierungs-Regressionen sichern beide Produktionspfade ab: mit lokalisierter Evidence wird der korrekte Seitentext weitergereicht, ohne lokalisierte Evidence wird kein erfundener Fallback-Text mehr an `verify_extraction(...)` übergeben.
- Der bestehende Trunkierungs-Test in [sfcr/extract/tests/test_extractor.py](sfcr/extract/tests/test_extractor.py#L186) prüft jetzt zusätzlich, dass ein gekürztes `source_text` ohne lokalisierbare Seitenbasis nicht implizit doch noch Evidence erzeugt.

Verifikation in der aktuellen Workspace-Umgebung:
- Lauf am 2026-03-24 13:12:51 CET: `TMPDIR=$PWD/.tmp python -m pytest -q sfcr/extract/tests/test_extractor.py sfcr/extract/tests/test_verify.py sfcr/extract/tests/test_evidence_hash.py` war erfolgreich mit `30 passed in 0.09s`.
- Lauf am 2026-03-24 13:12:51 CET: `TMPDIR=$PWD/.tmp python -m pytest -q` war erfolgreich mit `72 passed, 2 warnings in 0.16s`.
- Lauf am 2026-03-24 13:12:51 CET: `python -m compileall sfcr/extract/extractor.py sfcr/extract/tests/test_extractor.py sfcr/extract/tests/test_evidence_hash.py` war erfolgreich mit Exit-Code `0`.

Restrisiken / nicht-blockierende Hinweise:
- Die Seitenermittlung bleibt heuristisch an der Qualität von `source_text` gebunden. Wenn das LLM keinen ausreichend lokalisierbaren Ausschnitt liefert oder eine Fundstelle paraphrasiert, bleibt `evidence=[]` und die Verifikation arbeitet ohne seitenlokalisierten Zusatzkontext weiter. Das ist bewusst konservativ, aber keine OCR-/Layout-genaue Positionsbestimmung.
- Bei mehrfach vorkommendem oder sehr ähnlichem `source_text` wird weiterhin die erste passende Seite im Span gewählt. Das behebt den `page_start`-Bug, ist aber noch keine positionsgenaue Disambiguierung für Dubletten.
- Die bereits bekannten Pydantic-Deprecation-Warnings aus [sfcr/config.py](sfcr/config.py) bestehen unverändert und waren nicht Gegenstand dieses Auftrags.

Offene Rückfragen:
- Keine.
