from pathlib import Path

import typer

from sfcr.config import get_settings
from sfcr.extract.extractor import LLMExtractor, extract_for_document, write_jsonl
from sfcr.llm.llm_text_client_factory import create_llm_text_client

if __name__ == "__main__":
    doc_id = "axakv_2024"

    cfg = get_settings()
    pdfs = sorted(Path(cfg.pdfs_dir).glob("*.pdf"))
    if not pdfs:
        typer.secho("No PDFs found; specify --pdf", fg="red")
        raise typer.Exit(1)
    pdf_cand = [f for f in pdfs if doc_id in f.stem]
    if len(pdf_cand) != 1:
        raise ValueError(f"Could not find unique PDF for {doc_id}")
    pdf = pdf_cand[0]

    cand = Path(cfg.output_dir_ingest) / f"{doc_id}.ingest.json"
    if not cand.exists():
        typer.secho(f"Missing ingestion JSON: {cand}", fg="red")
        raise typer.Exit(1)
    ingest_json = cand

    filename_fields_yaml = "fields.yaml"
    fields = Path(cfg.project_root) / "sfcr" / "extract" / filename_fields_yaml
    if not fields.exists():
        typer.secho(f"{filename_fields_yaml} not found: {fields}", fg="red")
        raise typer.Exit(1)

    out = Path(cfg.output_dir_extract) / f"{doc_id}.extractions.jsonl"

    llm = create_llm_text_client(provider="openai", model="gpt-5-mini")
    extractor = LLMExtractor(text_client=llm)
    rows = extract_for_document(doc_id, pdf, ingest_json, fields, extractor=extractor)
    write_jsonl(rows, out)
    print(f"[green]✓[/green] wrote {out}")
