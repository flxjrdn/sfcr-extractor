# SFCR Extractor

A pipeline for automated extraction, validation, and analysis of Solvency and Financial Condition Reports (SFCR) using Large Language Models (LLMs).

The project transforms unstructured PDF reports into structured, validated data and provides a web interface for analysis and comparison.

---

## 🚀 Overview

SFCR reports contain key financial information about insurance companies but are published as unstructured PDF documents. Extracting relevant values manually is time-consuming and error-prone.

This project implements a **pipeline-based approach** to:

- Extract key metrics (e.g. SCR, MCR, Own Funds)
- Validate extracted values
- Store results in a structured database
- Provide a UI for exploration and comparison
- Generate summaries of report sections

---

## 🧠 Approach

Two approaches to SFCR analysis are possible:

- **Prompt-based extraction** → flexible, ad-hoc querying
- **Pipeline-based extraction (this project)** → structured, repeatable, scalable

This project follows the second approach, enabling:

- consistent results across runs
- reduced LLM cost
- validation and quality control
- reuse of extracted data

---

## 🏗️ Pipeline

The processing pipeline consists of five steps:

1. **Ingestion**
   - Read PDF reports
   - Detect sections (A–E) and subsections
   - Extract structured text

2. **Extraction**
   - Use LLMs to extract specific values
   - Field definitions configurable via `fields.yaml`

3. **Validation**
   - Check whether values appear in source text
   - Detect common issues (e.g. previous-year values)
   - Flag uncertain results

4. **Post-processing**
   - Compute derived metrics (e.g. solvency ratio)
   - Apply manual overrides

5. **Storage & UI**
   - Store results in SQLite
   - Provide web interface (Streamlit)
   - Generate section summaries

---

## ⚙️ Installation

### Requirements

- Python **3.13.0**
- pip

### Setup

```bash
make install
```

## 📂 Data & Configuration

### Input data (PDFs)

Default location:
data/sfcrs/{doc_id}.pdf

Example:
data/sfcrs/sikv_2023.pdf

Override via environment variable:
export SFCR_DATA=/path/to/pdfs

---

### Output directory

Default:
artifacts/

Override:
export SFCR_OUTPUT=/path/to/output

---

### Environment variables

Create a `.env` file (optional):

SFCR_DATA=data/sfcrs
SFCR_OUTPUT=artifacts
OPENAI_API_KEY=your_api_key

---

## 🤖 LLM Configuration

Supported providers:

- mock (default)
- ollama (local models)
- openai (used in this project)

Example:
make extract-dir MODEL=gpt-5-mini PROVIDER=openai

---

## ▶️ Usage

### Run full pipeline

make ingest-dir
make extract-dir MODEL=gpt-5-mini PROVIDER=openai
make summarize-dir MODEL=gpt-5-mini PROVIDER=openai
make db-init
make db-load
make ui

---

### Individual steps

- make ingest → Ingest a single document
- make ingest-dir → Ingest all PDFs
- make extract → Extract values from one PDF
- make extract-dir → Extract all documents
- make summarize → Summarize one document
- make summarize-dir → Summarize all documents
- make eval → Evaluate extraction
- make gold → Generate gold dataset
- make db-init → Initialize database
- make db-load → Load data into DB
- make ui → Launch web interface

---

## 📊 Evaluation

A gold dataset with 32 manually validated values is used.

- 28 / 32 values correctly extracted (~88%)
- Errors concentrated in a single company (SCR & MCR)

---

## 🧩 Manual Overrides

data/manual_overrides.yaml

---

## 🗄️ Database

SQLite database (default):
artifacts/sfcr.sqlite

---

## 🌐 Web Interface

Launch via:
make ui

Features:
- Key metrics overview
- Structured tables
- Section summaries
- Access to PDFs

---

## 📁 Project Structure

data/
artifacts/
scripts/
sfcr/
fields.yaml
Makefile
README.md

---

## 🔧 Extensibility

- Add fields via fields.yaml
- Add PDFs without code changes
- Extend validation logic
- Switch models/providers

---

## ⚠️ Limitations

- PDF parsing is imperfect
- LLM extraction may fail in edge cases
- Manual validation may be required

---

## 📌 License

This project is licensed under the MIT License.
