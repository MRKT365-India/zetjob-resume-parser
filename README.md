# ZetJob Resume Parser

> Async resume parsing microservice for the ZetJob platform — FastAPI, LLM-powered extraction, OCR pipeline.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-proprietary-red.svg)](#)

---

## Overview

The ZetJob Resume Parser is a standalone microservice that accepts resumes (PDF, DOCX), extracts structured data via an LLM pipeline, and returns ATS-compatible JSON. It supports OCR for image-based resumes and antivirus scanning before processing.

---

## Features

- **Multi-format support** — PDF (via PyMuPDF), DOCX (via python-docx)
- **LLM extraction** — structured JSON output: personal info, skills, work history, education
- **Async job queue** — non-blocking parse pipeline
- **OCR-ready** — configurable OCR provider for scanned/image-based resumes
- **Antivirus scanning** — pluggable AV provider before file processing
- **Job-description matching** — `match_score` against a JD (see `DEVELOPMENT_PLAN.md`)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/parse` | Enqueue a resume parse job |
| `GET` | `/status/{id}` | Poll job status and retrieve results |
| `DELETE` | `/resume/{id}` | Delete a resume and its parse data |

---

## Quick Start

```bash
# Clone and set up
git clone https://github.com/MRKT365-India/zetjob-resume-parser.git
cd zetjob-resume-parser

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set LLM_API_KEY, OCR_PROVIDER, AV_PROVIDER

# Run dev server
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_PROVIDER` | `stub` | OCR engine (`stub`, `tesseract`, `gemini`) |
| `AV_PROVIDER` | `stub` | Antivirus provider (`stub`, `clamav`) |
| `LLM_API_KEY` | — | API key for LLM extraction |

---

## Docker

```bash
docker build -t zetjob-resume-parser .
docker run -p 8000:8000 --env-file .env zetjob-resume-parser
```

---

## Development

See [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) for the full roadmap — ATS-grade matching, universal parsing, multi-modal OCR, and testing strategy.

---

## Part of ZetJob

This service is part of the [ZetJob](https://zetjob.in) platform — India's job marketplace.

| Repo | Description |
|------|-------------|
| `zetjob-backend` | NestJS API |
| `zetjob-frontend` | Next.js UI |
| `zetjob-devstack` | Local dev environment |
| `zetjob-resume-parser` | **This repo** |
