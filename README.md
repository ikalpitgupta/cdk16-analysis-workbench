# CDK16 Analysis Workbench

> **Structural and Functional Landscape of CDK16 Variants: An Integrative Bioinformatics Analysis Platform**

[![Live Application](https://img.shields.io/badge/Live%20Platform-cdk--variant--explorer.vercel.app-00dfa2?style=for-the-badge&logo=vercel)](https://cdk-variant-explorer.vercel.app/)
[![GitHub Repository](https://img.shields.io/badge/GitHub-ikalpitgupta%2Fcdk16--analysis--workbench-blue?style=for-the-badge&logo=github)](https://github.com/ikalpitgupta/cdk16-analysis-workbench)
[![Build & Test Status](https://img.shields.io/badge/Test%20Suite-25%20Passed-emerald?style=for-the-badge&logo=pytest)](https://github.com/ikalpitgupta/cdk16-analysis-workbench)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11+-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript-61DAFB?style=for-the-badge&logo=react)](https://react.dev)

---

## 🌐 Live Deployment & Links

- **Production URL**: [https://cdk-variant-explorer.vercel.app/](https://cdk-variant-explorer.vercel.app/)
- **Source Code**: [https://github.com/ikalpitgupta/cdk16-analysis-workbench](https://github.com/ikalpitgupta/cdk16-analysis-workbench)
- **API Documentation**: [https://cdk-variant-explorer.vercel.app/docs](https://cdk-variant-explorer.vercel.app/docs) (OpenAPI / Swagger interactive docs)

---

## 🔬 Project Overview & Objectives

**Cyclin-Dependent Kinase 16 (CDK16)**, also known as **PCTK1** (PCTAIRE-motif protein kinase 1), is a non-canonical member of the cyclin-dependent kinase family predominantly expressed in brain and testis tissue. CDK16 plays critical biological roles in:
- Spermatogenesis and vesicle-mediated transport,
- Neurite outgrowth and synaptic vesicle trafficking,
- Signal transduction through interactions with CCNY (Cyclin Y) and 14-3-3 scaffolding complexes.

Despite its physiological importance, navigating the variant landscape of CDK16 across fragmented public databases (UniProt, dbSNP, ClinVar, Ensembl, AlphaFold DB, PubMed) poses significant challenges for biomedical researchers.

The **CDK16 Analysis Workbench** solves this by providing an end-to-end, reproducible, and interactive bioinformatics system. It integrates genetic, evolutionary, structural, functional, computational, and clinical evidence into a unified analysis environment. Researchers can filter variants using rigorous multidimensional constraints, run reproducible multi-stage analysis workflows, inspect residues in interactive 3D structures, compute prioritized candidate rankings (via CEPS), and generate audit-grade versioned scientific reports in HTML and PDF formats.

> **Research & Educational Disclaimer**: This platform is intended solely for scientific research and educational purposes. Computational pathogenicity scores, evolutionary conservation metrics, and heuristic composite priority scores do not establish clinical pathogenicity or diagnostic certainty.

---

## ✨ Key Features

1. **Comprehensive CDK16 Variant Master Table**:
   - 4,137 harmonized variants (including 216 missense, 153 synonymous, 118 splice, nonsense, and frameshift variants).
   - Unified genomic (GRCh38), transcript (ENST00000309995), and canonical protein (UniProt Q00536, 496 amino acids) coordinates.
   - Annotations include Ensembl VEP consequences, SIFT, PolyPhen-2, ClinVar germline submissions, and AlphaMissense pathogenicity predictions.

2. **Interactive 3D Macromolecular Structure Viewer**:
   - Integrated with experimental X-ray crystallographic structures from RCSB PDB (`3MTL`, `5G6V`, `9R2I`) and high-confidence AlphaFold DB models (`AF-Q00536-F1`).
   - One-click variant inspection: jumping from a variant table immediately highlights the exact residue in 3D space with domain boundaries and catalytic landmarks (ATP-binding pocket, catalytic triad, phosphorylation sites).

3. **Reproducible Constraint-Based Analysis Engine**:
   - Define custom analysis constraints (variant consequence class, kinase domain restriction, minimum evolutionary conservation threshold, AlphaMissense classification, catalytic site proximity, priority cutoffs, and sample limits).
   - SQLite-backed state machine with stage-by-stage progress tracking (`validating` → `loading` → `filtering` → `conservation` → `predictions` → `structure` → `evidence` → `ranking` → `completed`).
   - Strict versioning: if constraints are modified on an existing analysis, it is flagged as `OUTDATED`, ensuring historical reproducibility and preserving previous run artifacts.

4. **Automated Versioned Scientific Report Generator**:
   - Generates publication-ready reports for individual analysis sections (`variants`, `predictions`, `conservation`, `structure`, `ranking`) or a complete comprehensive report.
   - Outputs both self-contained HTML (with embedded base64 figures) and PDF documents (built via ReportLab).
   - Dedicated Report Center with instant downloads (`HTML`, `PDF`, `JSON`), version history, and interactive in-app viewing.

5. **Modern Glassmorphism UI & Accessibility**:
   - Custom responsive design system featuring sleek dark and light themes with dynamic switching.
   - Responsive tables with horizontal scroll protection, custom filter bars, CSV export, and clear visual chips.

---

## 🏗️ Architecture & Repository Structure

```
cdk16-analysis-workbench/
├── api/                                # FastAPI Backend & Engines
│   ├── analysis_engine.py             # SQLite state machine, execution stages, validation
│   ├── index.py                       # Vercel serverless entrypoint
│   ├── report_generator.py            # Matplotlib plotting, HTML rendering, ReportLab PDF builder
│   └── server.py                      # REST endpoints, CORS, static SPA serving
├── data/
│   ├── raw/                           # Cached verbatim upstream responses & provenance logs
│   ├── processed/                     # Harmonized master datasets
│   │   ├── cdk16_variants_master.csv  # 4,137 normalized variants with CEPS scores
│   │   ├── cdk16_protein.json         # UniProt Q00536 sequence, domains, landmarks
│   │   ├── cdk16_conservation.json    # Ortholog alignment & BLOSUM62 scores
│   │   ├── cdk16_literature.json      # PubMed article records
│   │   ├── cdk16_structures.json      # PDB & AlphaFold metadata
│   │   └── pipeline_manifest.json     # Checksums, timestamps, pipeline metadata
│   └── structures/                    # PDB mmCIF files and AlphaFold model PDBs
├── frontend/                          # React + TypeScript Frontend
│   ├── src/
│   │   ├── api/client.ts              # Typed API client & data interfaces
│   │   ├── components/                # Layout, Navigation, Notification bar, Theme toggles
│   │   ├── pages/                     # Dashboard, Variants, Structure, Analysis, Reports
│   │   └── index.css                  # Custom design tokens, glassmorphism, responsive tables
│   ├── package.json                   # Frontend dependencies
│   └── vite.config.ts                 # Vite bundler configuration & local API proxy
├── src/                               # Offline Data Acquisition & Integration Pipeline
│   ├── acquisition/                   # Automated scrapers & API fetchers (UniProt, NCBI, Ensembl...)
│   └── integration/                   # Normalization, coordinate mapping, CEPS scoring
├── tests/                             # Automated Test Suite (Pytest)
│   ├── test_analysis_engine.py        # Constraint validation, hashes, run lifecycle
│   ├── test_api.py                    # REST API integration tests & download endpoints
│   ├── test_report_generator.py       # HTML/PDF formatting, tables, figures
│   └── test_spa.py                    # Single-Page Application client routing
├── .env.example                       # Documented environment variables template
├── requirements.txt                   # Backend Python dependencies
├── vercel.json                        # Vercel build & serverless function routing
└── README.md                          # Comprehensive project documentation
```

---

## 📊 Bioinformatics Data Sources & Ingestion Pipeline

All master datasets are derived from authoritative, publicly available bioinformatics repositories with full provenance tracking recorded in `data/raw/data_provenance.csv`:

| Database | Version / Accession | Retrieved Content |
|---|---|---|
| **UniProtKB** | `Q00536` (CDK16_HUMAN) | Canonical 496 aa sequence, protein kinase domain (residues 154–447), landmarks (ATP binding, active site, phosphorylation targets), PPI network. |
| **Ensembl REST & VEP** | Release 113 / GRCh38 | Transcript `ENST00000309995`, coding consequences, cDNA coordinates, SIFT & PolyPhen-2 scores for dbSNP alleles. |
| **NCBI dbSNP & Gene** | Gene ID `5127` | Genomic coordinates, rsIDs, functional consequence classes, allele designations. |
| **NCBI ClinVar** | Current Monthly Release | Germline clinical significance, review status (stars), submission accessions, associated phenotypes/conditions. |
| **EBI ProtVar & AlphaMissense** | Release 2023 | High-precision deep learning pathogenicity predictions (`am_pathogenicity_score`, `am_pathogenicity_class`) for missense mutations. |
| **RCSB PDB & AlphaFold DB** | `3MTL`, `5G6V`, `9R2I`, `AF-Q00536-F1` | Experimental X-ray crystallographic mmCIF coordinates and AlphaFold v4 pLDDT monomer models. |
| **NCBI PubMed** | E-utilities API | Curated bibliographic citations (115+ articles) linking variant alleles to functional literature. |

---

## 🧮 Methodology: Composite Evidence Priority Score (CEPS)

To assist researchers in triaging variants for downstream functional validation, the workbench calculates a transparent **Composite Evidence Priority Score (CEPS)**. The priority score ranges from `0.0` to `100.0` and represents a weighted linear combination of 7 distinct lines of evidence:

$$\text{CEPS} = 100 \times \sum_{i} (w_i \times E_i)$$

| Evidence Dimension ($E_i$) | Weight ($w_i$) | Scoring Criteria & Normalization |
|---|---|---|
| **Clinical Significance** (`ev_clinical`) | **20%** (`0.20`) | ClinVar classification: Pathogenic / Likely Pathogenic = `1.0`, VUS = `0.6`, Conflicting = `0.5`, Benign = `0.2`, Unreported = `0.0`. |
| **Computational Pathogenicity** (`ev_computational`) | **15%** (`0.15`) | Normalized AlphaMissense continuous score ($0.0 - 1.0$), capturing structural disruption potential. |
| **Evolutionary Conservation** (`ev_conservation`) | **15%** (`0.15`) | BLOSUM62-weighted identity score ($0.0 - 1.0$) computed across vertebrate CDK16 orthologs. |
| **Structural Proximity** (`ev_structural`) | **15%** (`0.15`) | Direct overlap with catalytic or regulatory landmark: Active site/binding pocket residue = `0.5`, within kinase domain = `0.25`, other = `0.0`. |
| **Domain Localization** (`ev_domain`) | **10%** (`0.10`) | Catalytic core localization: Kinase domain (aa 154–447) = `0.6`, flanking regulatory regions = `0.3`, unannotated = `0.0`. |
| **Literature Association** (`ev_literature`) | **10%** (`0.10`) | Mapped PubMed citations in biomedical literature: Associated = `0.5`, No published records = `0.0`. |
| **Cross-Database Concordance** (`ev_cross_db`) | **15%** (`0.15`) | Agreement across orthogonal databases (dbSNP rsID, HGVS cDNA, HGVS protein, UniProt residue): $n/4$ ($0.25$ per matched source up to `1.0`). |

### CEPS Limitations
- **Heuristic Nature**: CEPS is a research prioritization index, **not a clinical diagnostic classifier**.
- **No Population Allele Frequency Factor**: gnomAD exome/genome frequencies are not yet incorporated; the `max_frequency` filter currently serves as an architectural placeholder until population frequency tables are integrated.
- **Ortholog Depth**: Evolutionary conservation is derived from primary vertebrate orthologs; extreme deep phylogenetic conservation may require broader sampling.

---

## ⚙️ Environment Variables

The project uses sensible defaults and does not require mandatory external API tokens for runtime operation. An environment template is provided in [`.env.example`](file:///e:/DBBIO_kt/.env.example):

```bash
# Server Binding
HOST=127.0.0.1
PORT=8000

# Data Directories (Defaults point to local repository paths)
# CDK16_DATA_DIR=./data/processed
# CDK16_RESULTS_DIR=./results

# Execution Mode
# Set CDK16_SYNC=1 in serverless / Vercel environments to run pipeline stages
# synchronously before the HTTP response terminates. In standard daemon servers,
# leave as 0 for non-blocking asynchronous thread pools.
CDK16_SYNC=0
```

---

## 🚀 Installation & Local Development

### Prerequisites
- **Python**: Version 3.11 or higher (tested on Python 3.13)
- **Node.js**: Version 18.0 or higher
- **npm**: Version 9.0 or higher
- **Git**

### 1. Clone Repository
```bash
git clone https://github.com/ikalpitgupta/cdk16-analysis-workbench.git
cd cdk16-analysis-workbench
```

### 2. Backend Setup
Create and activate a virtual environment, then install Python dependencies:
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

Start the FastAPI backend server:
```bash
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```
The backend API is now accessible at `http://127.0.0.1:8000`.

### 3. Frontend Setup
In a separate terminal, navigate to the `frontend/` directory and start the Vite dev server:
```bash
cd frontend
npm install
npm run dev -- --port 5173
```
Open your browser to `http://localhost:5173`. Vite will automatically proxy API calls to the FastAPI backend running on port 8000.

### 4. Optional: Rebuild Master Datasets
If you wish to refresh raw database caches or rerun the integration pipeline:
```bash
python src/acquisition/fetch_all.py    # Fetches upstream data with local caching
python src/integration/integrate.py    # Generates master CSV and JSON datasets
```

---

## 📡 REST API Reference

The backend provides a comprehensive RESTful API adhering to standard OpenAPI specifications:

### Public Metadata & Protein Information
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/protein` | Returns CDK16 canonical sequence, molecular weight, domains, landmarks, and PPIs. |
| `GET` | `/api/variants` | Paginated variant catalog. Query params: `page`, `page_size`, `search`, `variant_class`, `am_class`, `domain`, `landmark`, `min_conservation`, `min_am_score`, `min_priority`, `sort_by`, `sort_desc`. |
| `GET` | `/api/variants/{variant_uid}` | Single variant detail including coordinates, predictions, literature links, and structural context. |
| `GET` | `/api/conservation` | CDK16 ortholog multiple sequence alignment and per-residue BLOSUM62 conservation scores. |
| `GET` | `/api/literature` | Cached PubMed articles with keyword filtering. |
| `GET` | `/api/structures` | Catalog of available experimental PDB structures and AlphaFold predicted models. |
| `GET` | `/api/structures/{pdb_id}/download` | Raw coordinate file download (`.cif` or `.pdb`). |
| `GET` | `/api/interactions` | CDK16 protein-protein interaction partner network. |
| `GET` | `/api/metadata` | Pipeline manifest checksums, record counts, and data provenance logs. |

### Analysis Workbench & Reports
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyses` | Creates a new analysis session with custom constraint parameters. |
| `GET` | `/api/analyses` | Returns all analysis sessions with execution status and summary stats. |
| `GET` | `/api/analyses/{sid}` | Fetches detailed session configuration, run history, and generated reports. |
| `DELETE` | `/api/analyses/{sid}` | Deletes an analysis session and associated result artifacts. |
| `PUT` | `/api/analyses/{sid}/constraints` | Updates constraints for a session, automatically transitioning status to `OUTDATED`. |
| `POST` | `/api/analyses/{sid}/run` | Triggers pipeline stage execution (`validating` → `filtering` → `ranking` → `completed`). |
| `GET` | `/api/analyses/{sid}/results` | Retrieves computed outputs, summary metrics, and prioritized variant tables. |
| `POST` | `/api/reports` | Generates an immutable versioned report (HTML & PDF) for an analysis session. |
| `GET` | `/api/reports` | Lists all generated reports across analyses. |
| `GET` | `/api/reports/{report_id}` | Retrieves report metadata and HTML content. |
| `GET` | `/api/reports/{report_id}/download` | Downloads the generated report file with `Content-Disposition: attachment`. Formats: `html`, `pdf`, `json`. |

---

## 🗄️ Database Architecture & Session Persistence

The analysis workbench utilizes an embedded **SQLite database** stored at `data/processed/analysis_sessions.db` with **Write-Ahead Logging (WAL)** enabled for concurrency and crash resilience:

```sql
-- Core Analysis Sessions
CREATE TABLE analysis_sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'CREATED',  -- CREATED, RUNNING, COMPLETED, FAILED, OUTDATED
    constraints_json TEXT NOT NULL,
    constraint_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Execution Run Audit Logs
CREATE TABLE analysis_runs (
    session_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    message TEXT,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    PRIMARY KEY (session_id, run_number),
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
);

-- Serialized Run Results
CREATE TABLE analysis_results (
    session_id TEXT PRIMARY KEY,
    run_number INTEGER NOT NULL,
    constraint_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
);

-- Versioned Reports Registry
CREATE TABLE analysis_reports (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    section TEXT NOT NULL,                  -- full, variants, predictions, conservation, structure, ranking
    version INTEGER NOT NULL,
    constraint_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CURRENT', -- CURRENT, OUTDATED
    format TEXT NOT NULL DEFAULT 'html',
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
);
```

---

## 🧪 Testing & Quality Assurance

The codebase includes an automated test suite implemented with `pytest` covering unit and integration testing:

```bash
# Run complete test suite
python -m pytest tests/ -v
```

### Test Coverage Highlights
- **`tests/test_analysis_engine.py`**: Validates constraint bounds, hash generation, default values, session creation, and stage progression.
- **`tests/test_api.py`**: Exercises REST endpoints, variant queries, structural metadata, analysis run triggering, and report generation/download attachment headers.
- **`tests/test_report_generator.py`**: Validates HTML escaping, figure generation (base64 PNG encoding), interpretation narrative synthesis, and PDF builds.
- **`tests/test_spa.py`**: Ensures client-side routing and SPA fallback mechanics function correctly without 404 errors.

---

## 🚢 Deployment (Vercel & Production)

### Vercel Deployment
The repository is pre-configured for automated continuous deployment to Vercel via [`vercel.json`](file:///e:/DBBIO_kt/vercel.json):
- **Build Command**: `cd frontend && npm install --no-audit --no-fund && npm run build`
- **Output Directory**: `frontend/dist`
- **Install Command**: `pip install --break-system-packages -r requirements.txt`
- **Serverless Entrypoint**: `api/index.py` handles API requests and serves static assets with automatic fallback.

Whenever changes are pushed to `main` on GitHub, Vercel triggers a new build and deploys the live version to [https://cdk-variant-explorer.vercel.app/](https://cdk-variant-explorer.vercel.app/).

### Standalone Production (Single Process)
You can also run the complete application as a single production service. First build the frontend assets, then launch FastAPI:
```bash
cd frontend && npm run build
cd ..
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
```
FastAPI automatically serves the compiled `frontend/dist` files at `/` and the API endpoints at `/api/*`.

---

## 🛠️ Troubleshooting

| Issue | Likely Cause | Solution |
|---|---|---|
| **Port 8000 already in use** | A previous uvicorn instance is running. | Terminate the existing process or run uvicorn with `--port 8001`. |
| **Reports table text overlapping** | Outdated CSS cache in browser. | Hard refresh the browser (`Ctrl+F5` or `Cmd+Shift+R`) to load the updated `.constraint-chip` flexbox styles. |
| **PDF download button shows 404** | Report was generated before PDF support was enabled. | Click **Generate Complete Report** again in the analysis results page to produce fresh HTML and PDF versions. |
| **`pytest` command not found** | Virtual environment not active or pytest not in PATH. | Run using `python -m pytest tests/`. |

---

## 📄 License & Intellectual Property

This project is created for scientific research, academic exploration, and bioinformatics education. Upstream data remains under the respective terms of UniProt, NCBI, Ensembl, RCSB PDB, and DeepMind.
