# GitLab Issue Provisioner Design Specification

## Goal
Develop a local Python CLI tool to process structured PDF issue documents and create them in GitLab via REST API, using rules-based parsing (no LLMs).

## Technical Constraints
- **Local-Only**: 100% rules-based parsing (Regex + Text Extraction).
- **Offline Processing**: No external NLP APIs or LLMs.
- **Open Source**: Use only standard or free libraries.
- **Environment**: Python 3.10+.

## Architecture

### Components
1. **Parser (`parser.py`)**
   - Uses `pdfplumber` for text extraction.
   - Implements a state-machine regex parser to segment documents into issue blocks.
   - Handles multi-line titles and identifies fields: Tipo, Objetivo, Descripción, Alcance, Criterios de Aceptación, Dependencias.
2. **Uploader (`uploader.py`)**
   - Wrapper for `python-gitlab`.
   - Handles `.env` configuration and GitLab authentication.
   - Performs bulk creation with logging.
3. **CLI (`main.py`)**
   - Argparse interface with two subcommands: `parse` and `upload`.
   - `parse` outputs a reviewable JSON file.
   - `upload` processes the JSON file into GitLab.

### Data Model
```json
{
  "issue_data": {
    "title": "string",
    "description": "Markdown with headers",
    "labels": ["Tipo", "Automated"],
    "attributes": { "weight": null, "milestone_id": null }
  }
}
```

## Parsing Logic
- **Issue Start**: `(\d+)\)\s+(.*)`
- **Fields**: Keyword search followed by `:`.
- **Lists**: Detected by bullet points (`●` or `•`).
- **State Preservation**: Tracks the current issue and field context to handle multi-line content.

## Verification Plan
- **Unit Testing**: Test parser against known sample text fragments.
- **Integration**: Dry-run upload (print payload without calling API) and full API test.

## Environment Config (`config.env`)
- `GITLAB_URL`
- `GITLAB_TOKEN` (Private Token)
- `PROJECT_ID`
