"""CDK16 Analysis Workbench — FastAPI server.

Serves processed biological data and the analysis/report workbench API.
All returned data comes from the processed pipeline datasets — nothing is
fabricated at the API layer.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from api.analysis_engine import AnalysisEngine, default_constraints, validate_constraints
from api import report_generator
from api.report_generator import SECTIONS, create_report

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
STRUCTURES = ROOT / "data" / "structures"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("server")

app = FastAPI(title="CDK16 Analysis Workbench API", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = AnalysisEngine()


def jload(path: Path):
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_master() -> pd.DataFrame:
    pq = PROCESSED / "cdk16_variants_master.parquet"
    cs = PROCESSED / "cdk16_variants_master.csv"
    if pq.exists():
        return pd.read_parquet(pq)
    if cs.exists():
        return pd.read_csv(cs, low_memory=False)
    return pd.DataFrame()


MASTER_CACHE: pd.DataFrame | None = None


def master() -> pd.DataFrame:
    global MASTER_CACHE
    if MASTER_CACHE is None:
        MASTER_CACHE = load_master()
    return MASTER_CACHE


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #
class AnalysisCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    constraints: dict = Field(default_factory=dict)


class AnalysisUpdate(BaseModel):
    constraints: dict


class ReportCreate(BaseModel):
    section: str = "full"


def _variant_payload(df: pd.DataFrame, page: int, page_size: int) -> dict:
    total = int(len(df))
    start = max(0, (page - 1) * page_size)
    chunk = df.iloc[start:start + page_size]
    cols = [c for c in ("variant_uid", "rsid", "aa_change", "protein_position",
                        "variant_class", "domain_name", "landmark_type",
                        "am_pathogenicity_score", "am_pathogenicity_class",
                        "conservation_score", "priority_score") if c in chunk.columns]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "variants": chunk[cols].replace({pd.NA: None}).to_dict(orient="records"),
    }


# --------------------------------------------------------------------------- #
# data endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/overview")
def overview() -> dict:
    protein = jload(PROCESSED / "cdk16_protein.json") or {}
    df = master()
    struct = jload(PROCESSED / "cdk16_structures.json") or {}
    lit = jload(PROCESSED / "cdk16_literature.json") or []
    cons = jload(PROCESSED / "cdk16_conservation.json") or {}
    manifest = jload(PROCESSED / "pipeline_manifest.json") or {}
    missense = int((df["variant_class"] == "missense").sum()) if not df.empty else 0
    mapped_struct = 0
    if not df.empty and "protein_position" in df.columns:
        mapped_struct = int(df["protein_position"].notna().sum())

    # Real per-metric series for the dashboard sparklines (no fabricated trends).
    def _bins(series, n=12):
        s = series.dropna()
        if s.empty:
            return [0] * n
        counts, _ = np.histogram(s, bins=n)
        return [int(x) for x in counts]

    import re as _re
    year_counts: dict[int, int] = {}
    for a in lit:
        m = _re.search(r"(19|20)\d{2}", str(a.get("pubdate", "")))
        if m:
            y = int(m.group())
            year_counts[y] = year_counts.get(y, 0) + 1
    lit_years = [year_counts.get(y, 0) for y in range(1992, 2027)]

    spark = {}
    if not df.empty:
        spark = {
            "total": _bins(df["protein_position"]),
            "missense": _bins(df.loc[df["variant_class"] == "missense", "protein_position"]),
            "pred": _bins(df["am_pathogenicity_score"]),
            "homologs": _bins(df["conservation_score"]),
            "pdb": _bins(df.loc[df["am_pathogenicity_score"].notna(), "protein_position"]),
            "lit": lit_years,
        }
    return {
        "protein": {
            "accession": protein.get("accession"), "name": protein.get("name"),
            "gene": protein.get("gene"), "length": protein.get("length"),
            "organism": protein.get("organism"),
            "n_features": len(protein.get("features", [])),
            "n_domains": len(protein.get("domains", [])),
            "n_landmarks": len(protein.get("landmarks", [])),
            "n_interactions": len(protein.get("interactions", [])),
            "family": protein.get("family"),
            "function": protein.get("function"),
            "mw_kda": protein.get("mw_kda"),
            "uniprot_version": protein.get("uniprot_version"),
        },
        "variants": {
            "total": int(len(df)),
            "missense": missense,
            "with_predictions": int(df["am_pathogenicity_score"].notna().sum())
            if not df.empty and "am_pathogenicity_score" in df.columns else 0,
            "structurally_mappable": mapped_struct,
            "by_class": df["variant_class"].value_counts().to_dict()
            if not df.empty else {},
        },
        "conservation": {
            "n_positions": len(cons.get("scores", [])),
            "n_homologs": cons.get("n_homologs", 0),
            "method": cons.get("method"),
        },
        "structures": {
            "experimental": [s.get("pdb_id") for s in struct.get("experimental", [])],
            "alphafold": struct.get("predicted", {}).get("alphafold_id"),
        },
        "literature_count": len(lit),
        "spark": spark,
        "clinvar_annotated": int(df["clinvar_id"].notna().sum())
        if not df.empty and "clinvar_id" in df.columns else 0,
        "conserved_positions": int(df["conservation_score"].notna().sum())
        if not df.empty and "conservation_score" in df.columns else 0,
        "dataset_version": manifest.get("generated_at"),
        "pipeline_version": manifest.get("pipeline"),
    }


@app.get("/api/protein")
def protein() -> dict:
    p = jload(PROCESSED / "cdk16_protein.json")
    if not p:
        raise HTTPException(404, "protein reference not built yet")
    return p


@app.get("/api/conservation")
def conservation() -> dict:
    c = jload(PROCESSED / "cdk16_conservation.json")
    if not c:
        raise HTTPException(404, "conservation not computed yet")
    return c


@app.get("/api/predictions")
def predictions() -> dict:
    df = master()
    if df.empty or "am_pathogenicity_score" not in df.columns:
        return {"available": False, "message": "AlphaMissense predictions not available"}
    vals = pd.to_numeric(df["am_pathogenicity_score"], errors="coerce").dropna()
    by_class = (df["am_pathogenicity_class"].astype(str).value_counts().to_dict()
                if "am_pathogenicity_class" in df.columns else {})
    hist, edges = [], None
    if not vals.empty:
        counts, edges = pd.cut(vals, bins=20, retbins=True, labels=False)
        vc = counts.value_counts().sort_index()
        hist = [{"bin": round(float(edges[int(b)]), 2),
                 "count": int(vc.get(b, 0))} for b in vc.index]
    return {"available": True, "n_scored": int(vals.notna().sum()),
            "mean": round(float(vals.mean()), 3) if not vals.empty else None,
            "median": round(float(vals.median()), 3) if not vals.empty else None,
            "by_class": by_class, "histogram": hist,
            "source": "AlphaMissense (Swiss-Model per-protein export)"}


@app.get("/api/variants")
def variants(page: int = 1, page_size: int = 50, search: str = "",
             variant_class: str = "", domain: str = "",
             am_class: str = "", min_conservation: float = 0.0,
             min_priority: float = 0.0, sort_by: str = "priority_score",
             sort_desc: bool = True) -> dict:
    df = master()
    if df.empty:
        return _variant_payload(df, page, page_size)
    if search:
        s = search.strip().lower()
        mask = pd.Series(False, index=df.index)
        for col in ("variant_uid", "rsid", "aa_change", "hgvs_protein"):
            if col in df.columns:
                mask |= df[col].astype(str).str.lower().str.contains(s, regex=False, na=False)
        df = df[mask]
    if variant_class and variant_class != "all":
        df = df[df["variant_class"].astype(str).str.lower() == variant_class.lower()]
    if domain and domain != "all":
        df = df[df["domain_name"].astype(str) == domain]
    if am_class and am_class != "all":
        df = df[df["am_pathogenicity_class"].astype(str).str.lower() == am_class.lower()]
    if min_conservation > 0 and "conservation_score" in df.columns:
        df = df[pd.to_numeric(df["conservation_score"], errors="coerce")
                .ge(min_conservation)]
    if min_priority > 0 and "priority_score" in df.columns:
        df = df[pd.to_numeric(df["priority_score"], errors="coerce").ge(min_priority)]
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not sort_desc, na_position="last")
    return _variant_payload(df, page, page_size)


@app.get("/api/variants/{variant_uid}")
def variant_detail(variant_uid: str) -> dict:
    df = master()
    row_df = df[df["variant_uid"].astype(str) == variant_uid]
    if row_df.empty:
        raise HTTPException(404, f"variant {variant_uid} not found")
    r = row_df.iloc[0].replace({pd.NA: None})
    protein = jload(PROCESSED / "cdk16_protein.json") or {}
    cons = jload(PROCESSED / "cdk16_conservation.json") or {}
    lit = jload(PROCESSED / "cdk16_literature.json") or []
    pos = r.get("protein_position")
    landmarks = [l for l in protein.get("landmarks", []) if l.get("position") == pos]
    return {
        "variant": r.to_dict(),
        "protein_context": {
            "domain": r.get("domain_name"),
            "landmark": landmarks[0] if landmarks else None,
            "residue": protein.get("sequence", [None] * (pos or 0))[pos - 1]
            if isinstance(pos, int) and 1 <= pos <= len(protein.get("sequence", "")) else None,
        },
        "conservation": {
            "score": r.get("conservation_score"),
            "n_shared": r.get("n_species_shared"),
            "n_homologs": cons.get("n_homologs"),
            "method": cons.get("method"),
        },
        "predictions": {
            "alphamissense": {"score": r.get("am_pathogenicity_score"),
                              "class": r.get("am_pathogenicity_class"),
                              "source": "AlphaMissense via Swiss-Model"},
            "sift": {"score": r.get("sift_score"), "prediction": r.get("sift_prediction"),
                     "source": "Ensembl VEP"},
            "polyphen": {"score": r.get("polyphen_score"),
                         "prediction": r.get("polyphen_prediction"),
                         "source": "Ensembl VEP"},
        },
        "literature": [{"pmid": a.get("pmid"), "title": a.get("title")}
                       for a in lit[:0]] or [],
    }


@app.get("/api/structures")
def structures() -> dict:
    s = jload(PROCESSED / "cdk16_structures.json")
    if not s:
        raise HTTPException(404, "structures not built yet")
    return s


@app.get("/api/structures/file/{structure_id}")
def structure_file(structure_id: str) -> FileResponse:
    safe = Path(structure_id).name
    if not safe.endswith(".cif"):
        safe += ".cif"
    path = STRUCTURES / safe
    if not path.exists():
        raise HTTPException(404, f"structure file {safe} not available")
    return FileResponse(path, media_type="chemical/x-mmcif", filename=safe)


@app.get("/api/literature")
def literature(page: int = 1, page_size: int = 0) -> dict:
    lit = jload(PROCESSED / "cdk16_literature.json") or []
    total = len(lit)
    if page_size and page_size > 0:
        start = (max(1, page) - 1) * page_size
        lit = lit[start:start + page_size]
    return {"count": total, "articles": lit}


@app.get("/api/interactions")
def interactions() -> dict:
    protein = jload(PROCESSED / "cdk16_protein.json") or {}
    return {"center": protein.get("accession", "Q00536"),
            "interactors": protein.get("interactions", [])}


@app.get("/api/metadata")
def metadata() -> dict:
    manifest = jload(PROCESSED / "pipeline_manifest.json") or {}
    prov = ROOT / "data" / "raw" / "data_provenance.csv"
    rows = pd.read_csv(prov).to_dict(orient="records") if prov.exists() else []
    return {"manifest": manifest, "provenance": rows}


# --------------------------------------------------------------------------- #
# analysis workbench endpoints
# --------------------------------------------------------------------------- #
@app.post("/api/analyses")
def create_analysis(body: AnalysisCreate) -> dict:
    try:
        sess = engine.create_session(body.name, body.description, body.constraints)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return sess


@app.get("/api/analyses")
def list_analyses() -> list[dict]:
    return engine.list_sessions()


@app.get("/api/analyses/{sid}")
def get_analysis(sid: str) -> dict:
    sess = engine.get_session(sid)
    if not sess:
        raise HTTPException(404, f"analysis {sid} not found")
    return sess


@app.delete("/api/analyses/{sid}")
def delete_analysis(sid: str) -> dict:
    if not engine.delete_session(sid):
        raise HTTPException(404, f"analysis {sid} not found")
    return {"deleted": sid}


@app.put("/api/analyses/{sid}/constraints")
def update_constraints(sid: str, body: AnalysisUpdate) -> dict:
    try:
        return engine.update_constraints(sid, body.constraints)
    except KeyError:
        raise HTTPException(404, f"analysis {sid} not found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/analyses/{sid}/run")
def run_analysis(sid: str) -> dict:
    try:
        return engine.run(sid)
    except KeyError:
        raise HTTPException(404, f"analysis {sid} not found")


@app.get("/api/analyses/{sid}/results")
def analysis_results(sid: str) -> dict:
    sess = engine.get_session(sid)
    if not sess:
        raise HTTPException(404, f"analysis {sid} not found")
    res = engine.get_results(sid)
    if res is None:
        return {"available": False, "status": sess["status"],
                "message": "no results yet — run the analysis first"}
    res["analysis_name"] = sess["name"]
    res["session_status"] = sess["status"]
    res["provenance"] = metadata()["provenance"]
    res["dataset_version"] = (jload(PROCESSED / "pipeline_manifest.json") or {})\
        .get("generated_at")
    res["pipeline_version"] = (jload(PROCESSED / "pipeline_manifest.json") or {})\
        .get("pipeline")
    return {"available": True, **res}


@app.get("/api/analyses/{sid}/reports")
def list_reports(sid: str) -> list[dict]:
    sess = engine.get_session(sid)
    if not sess:
        raise HTTPException(404, f"analysis {sid} not found")
    return sess["reports"]


@app.post("/api/analyses/{sid}/reports")
def generate_section_report(sid: str, body: ReportCreate) -> dict:
    if body.section not in SECTIONS:
        raise HTTPException(422, f"section must be one of {sorted(SECTIONS)}")
    sess = engine.get_session(sid)
    if not sess:
        raise HTTPException(404, f"analysis {sid} not found")
    res = engine.get_results(sid)
    if res is None:
        raise HTTPException(409, "analysis has no results — run it first")
    existing = [r for r in sess["reports"] if r["section"] == body.section]
    version = (max(r["version"] for r in existing) + 1) if existing else 1
    res["analysis_name"] = sess["name"]
    meta = create_report(res, body.section, version)
    with engine._lock:
        engine.conn.execute(
            "INSERT INTO analysis_reports (id, session_id, run_number, section,"
            " version, constraint_hash, status, format, title, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (meta["report_id"], sid, meta["run_number"], meta["section"],
             meta["version"], meta["constraint_hash"],
             "CURRENT" if meta["constraint_hash"] == sess["constraint_hash"]
             else "OUTDATED", "html", meta["title"], meta["created_at"]))
        engine.conn.commit()
    return meta


@app.get("/api/reports")
def all_reports() -> list[dict]:
    rows = engine.conn.execute(
        "SELECT r.*, s.name AS analysis_name FROM analysis_reports r"
        " LEFT JOIN analysis_sessions s ON r.session_id = s.id"
        " ORDER BY r.created_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict:
    row = engine.conn.execute(
        "SELECT * FROM analysis_reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"report {report_id} not found")
    return dict(row)


@app.get("/api/reports/{report_id}/html", response_class=HTMLResponse)
def report_html(report_id: str) -> FileResponse:
    row = engine.conn.execute(
        "SELECT * FROM analysis_reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"report {report_id} not found")
    import sqlite3
    rid = dict(row)
    rdir = report_generator.REPORTS / rid["session_id"] / \
        f"{rid['section']}-v{rid['version']}"
    path = rdir / "report.html"
    if not path.exists():
        raise HTTPException(410, "report file missing on disk")
    return FileResponse(path, media_type="text/html")


@app.get("/api/reports/{report_id}/download")
def report_download(report_id: str, format: str = "html") -> FileResponse:
    row = engine.conn.execute(
        "SELECT * FROM analysis_reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"report {report_id} not found")
    rid = dict(row)
    rdir = report_generator.REPORTS / rid["session_id"] / \
        f"{rid['section']}-v{rid['version']}"
    if format == "pdf":
        path = rdir / "report.pdf"
        if not path.exists():
            raise HTTPException(404, "PDF not generated for this report")
        media = "application/pdf"
    elif format == "json":
        path = rdir / "report.json"
        media = "application/json"
    else:
        path = rdir / "report.html"
        media = "text/html"
    if not path.exists():
        raise HTTPException(410, "report file missing on disk")
    return FileResponse(path, media_type=media, filename=path.name)


# --------------------------------------------------------------------------- #
# static frontend (production)
# --------------------------------------------------------------------------- #
DIST = ROOT / "frontend" / "dist"

if DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        # Serve real files from dist (favicon, images, ...) then SPA-fallback.
        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(DIST.resolve())):
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
