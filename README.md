# CDK16 Analysis Workbench

**Interactive Structural & Functional Variant Analysis Platform**

*"Structural and Functional Landscape of CDK16 Variants: An Integrative Bioinformatics Analysis"*

This platform integrates CDK16 genetic, protein, clinical, computational, evolutionary, and
structural information to investigate how reported CDK16 variants may affect the protein and to
prioritize variants that deserve further biological investigation.

> Research and educational use only. Computational evidence does not establish clinical
> pathogenicity. The platform integrates evidence for prioritization — it does not diagnose.

---

## Architecture

```
frontend/  React 18 + TypeScript + Vite + custom glass design system (light/dark themes)
api/       FastAPI server, analysis engine (SQLite-persisted jobs), report generator (HTML+PDF)
src/
  acquisition/   Data retrieval from public databases (provenance-tracked)
  integration/   Normalization -> master variant table, protein, conservation, literature
data/
  raw/           Verbatim API responses + provenance CSV (UniProt, NCBI, Ensembl, dbSNP,
                 VEP, ClinVar, RCSB PDB, AlphaFold DB, PubMed, ProtVar)
  processed/     cdk16_variants_master.csv, protein/conservation/structures/literature JSON,
                 analysis_sessions.db (SQLite: sessions, runs, reports)
  structures/    Experimental PDB mmCIF (3MTL, 5G6V, 9R2I) + AlphaFold AF-Q00536-F1 model
results/reports/<analysis>/<section>-v<N>/   report.html / report.pdf / report.json / figures/
```

## Data sources (retrieved at build time)

| Source | Content |
|---|---|
| UniProt | Q00536 canonical sequence, domains, features, landmarks, interactions |
| NCBI Gene / E-utilities | Gene 5127, PubMed literature (115 articles), ClinVar submissions |
| Ensembl REST | Gene model; VEP consequences/SIFT/PolyPhen for 5,210 dbSNP rsIDs |
| ClinVar | Per-record germline classification, review status, condition |
| RCSB PDB | Experimental structures of CDK16 |
| AlphaFold DB | Predicted model (version resolved via API) |
| EBI ProtVar | AlphaMissense pathogenicity scores per missense variant |

## Scientific pipeline

Data Acquisition → Normalization → Annotation (VEP, ClinVar, ProtVar) → Conservation
(BLOSUM62-weighted identity across orthologs) → Structural mapping (domains, landmarks,
3D residue mapping) → Evidence integration (documented weighted heuristic) →
Prioritization → Analysis session → Report (versioned, reproducible).

## Run

```bash
# Backend (from project root)
C:/Python313/python.exe -m uvicorn api.server:app --host 127.0.0.1 --port 8000

# Frontend dev server
cd frontend && npm install && npx vite --port 5173
# open http://localhost:5173

# Production
cd frontend && npm run build        # dist/ is served by FastAPI at http://127.0.0.1:8000
```

Rebuild the data layer (optional; raw data is cached):

```bash
C:/Python313/python.exe src/acquisition/fetch_all.py     # network retrieval (cached)
C:/Python313/python.exe src/integration/integrate.py     # master tables
```

## The Analysis workflow

1. **Analysis → New Analysis**: define constraints (variant type, domain, conservation,
   prediction class, min AM score, functional site, result cap).
2. **Run Analysis**: server-side job with stage-based progress (validating → loading →
   filtering → conservation → predictions → structure → evidence → ranking → done).
3. **Results workspace**: context chips, statistics, variant table, ranking tabs.
4. **Generate Complete Report / section reports**: each report captures the exact
   analysis configuration and results; figures and tables computed from that run.
5. **Reports Center**: all versions, status (CURRENT/OUTDATED), HTML/PDF download,
   in-app viewer.
6. Constraint changes mark a session OUTDATED; re-running creates a new immutable run
   and report version. Nothing is overwritten.

## Known limitations

- Conservation computed from 2 orthologs currently cached; extend `homologs.json` for
  deeper evolutionary sampling.
- Variant set is dbSNP-allele centric (5,210 rsIDs via VEP) plus ClinVar SNV records;
  large CNV ClinVar records are intentionally excluded.
- Population frequencies not currently joined (no gnomAD import yet); the `max_frequency`
  constraint has no effect until that column exists.
- Clinical significance covers the 200 most recent ClinVar submissions for CDK16.
