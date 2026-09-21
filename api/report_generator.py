"""CDK16 report generator.

Consumes an immutable AnalysisResult (from the analysis engine) and produces
versioned HTML + PDF reports with real figures and tables. All numbers come
from computed data — nothing is fabricated.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# Writable output dir: serverless (Vercel) => /tmp; local => repo results/
RESULTS = Path(os.environ.get("CDK16_RESULTS_DIR") or (ROOT / "results"))
REPORTS = RESULTS / "reports"
# Bundled read-only data (protein metadata for report context).
BUNDLED = ROOT / "data" / "processed"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("report")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)
    from reportlab.lib import colors as rl_colors
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

NAVY = "#0B1628"
PANEL = "#101E33"
CYAN = "#22d3ee"
VIOLET = "#a78bfa"
EMERALD = "#34d399"
AMBER = "#fbbf24"
CORAL = "#f87171"
INK = "#e2e8f0"
MUTED = "#94a3b8"

SECTIONS = {
    "full": "CDK16 Integrative Variant Analysis Report",
    "variants": "Variant Analysis Report",
    "clinical": "Clinical Evidence Report",
    "predictions": "Computational Prediction Report",
    "conservation": "Conservation Analysis Report",
    "structure": "Structural Analysis Report",
    "ranking": "Candidate Prioritization Report",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fmt(v) -> str:
    if v is None:
        return "—"
    try:
        if pd.isna(v):
            return "—"
    except (TypeError, ValueError):
        pass
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") or "0"
    return str(v)


def _esc(s) -> str:
    return re.sub(r"&", "&amp;", re.sub(r"<", "&lt;", str(s)))


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _style_ax(ax):
    ax.set_facecolor(NAVY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", alpha=0.2, color=MUTED)


def fig_counts(df: pd.DataFrame, col: str, title: str, fname: str) -> Path | None:
    if col not in df.columns or df[col].dropna().empty:
        return None
    counts = df[col].astype(str).value_counts().head(12)
    if counts.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=110)
    counts.plot.bar(ax=ax, color=CYAN, width=0.7)
    ax.set_title(title, fontsize=13, fontweight="bold", color=INK)
    ax.set_ylabel("Variants", color=MUTED)
    ax.set_xlabel("")
    _style_ax(ax)
    fig.patch.set_facecolor(NAVY)
    fig.tight_layout()
    out = REPORTS / "figures" / fname
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def fig_histogram(df: pd.DataFrame, col: str, title: str, xlabel: str,
                  fname: str, color: str = VIOLET) -> Path | None:
    if col not in df.columns:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna()
    if vals.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=110)
    ax.hist(vals, bins=24, color=color, edgecolor=NAVY)
    ax.set_title(title, fontsize=13, fontweight="bold", color=INK)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel("Variants", color=MUTED)
    _style_ax(ax)
    fig.patch.set_facecolor(NAVY)
    fig.tight_layout()
    out = REPORTS / "figures" / fname
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def fig_positions(df: pd.DataFrame, fname: str, protein_length: int = 496) -> Path | None:
    if "protein_position" not in df.columns:
        return None
    pos = pd.to_numeric(df["protein_position"], errors="coerce").dropna()
    if pos.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=110)
    counts, bins = np.histogram(pos, bins=np.arange(0, protein_length + 25, 25))
    ax.bar(bins[:-1], counts, width=22, color=EMERALD, align="edge")
    ax.set_title("Variant Distribution Along CDK16 (496 aa)", fontsize=13,
                 fontweight="bold", color=INK)
    ax.set_xlabel("Protein position (aa)", color=MUTED)
    ax.set_ylabel("Variants per 25-aa bin", color=MUTED)
    ax.set_xlim(0, protein_length)
    _style_ax(ax)
    fig.patch.set_facecolor(NAVY)
    fig.tight_layout()
    out = REPORTS / "figures" / fname
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def fig_priority(df: pd.DataFrame, fname: str) -> Path | None:
    if "priority_score" not in df.columns or df.empty:
        return None
    top = df.sort_values("priority_score", ascending=False).head(20)
    top = top[top["priority_score"] > 0]
    if top.empty:
        return None
    labels = [str(r.get("aa_change") or r.get("variant_uid")) for _, r in top.iterrows()]
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=110)
    ax.barh(range(len(top))[::-1], top["priority_score"], color=AMBER, height=0.65)
    ax.set_yticks(range(len(top))[::-1])
    ax.set_yticklabels(labels, fontsize=8, color=INK, family="monospace")
    ax.set_title("Top 20 Variants by Integrated Evidence Score (CEPS)", fontsize=13,
                 fontweight="bold", color=INK)
    ax.set_xlabel("Computational Evidence Priority Score (0–100)", color=MUTED)
    _style_ax(ax)
    ax.grid(axis="x", alpha=0.2, color=MUTED)
    ax.grid(axis="y", alpha=0)
    fig.patch.set_facecolor(NAVY)
    fig.tight_layout()
    out = REPORTS / "figures" / fname
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Tables (as HTML strings)
# --------------------------------------------------------------------------- #
VARIANT_COLS = [
    ("variant_uid", "Variant"), ("aa_change", "AA change"),
    ("protein_position", "Pos."), ("variant_class", "Consequence"),
    ("domain_name", "Domain"), ("landmark_type", "Functional site"),
    ("am_pathogenicity_score", "AM score"), ("am_pathogenicity_class", "AM class"),
    ("conservation_score", "Conservation"), ("priority_score", "Priority"),
]


def table_variants(df: pd.DataFrame, n: int = 25) -> str:
    if df.empty:
        return "<p class='empty'>No variants matched the analysis constraints.</p>"
    cols = [(c, label) for c, label in VARIANT_COLS if c in df.columns]
    rows_html = []
    for _, r in df.head(n).iterrows():
        cells = "".join(f"<td>{_esc(_fmt(r.get(c)))}</td>" for c, _ in cols)
        rows_html.append(f"<tr>{cells}</tr>")
    head = "".join(f"<th>{label}</th>" for _, label in cols)
    note = "" if len(df) <= n else \
        f"<p class='note'>Showing first {n} of {len(df)} variants.</p>"
    return (f"<table><thead><tr>{head}</tr></thead><tbody>"
            f"{''.join(rows_html)}</tbody></table>{note}")


# --------------------------------------------------------------------------- #
# Interpretation (data-driven only)
# --------------------------------------------------------------------------- #
def build_interpretation(result: dict, df: pd.DataFrame) -> list[str]:
    s = result["summary"]
    stats = result["statistics"]
    out: list[str] = []
    if s["n_matched"] == 0:
        out.append("The selected constraints returned no matching variants. "
                   "This is a valid analytical outcome; relax a constraint to "
                   "explore the dataset.")
        return out
    out.append(f"Among the {s['n_matched']:,} variants satisfying the analysis "
               f"constraints (from {s['n_available']:,} retrieved CDK16 variants), "
               f"{s['n_returned']:,} are included in this result set.")
    by_class = stats.get("by_class", {})
    if by_class:
        top_class = max(by_class, key=by_class.get)
        out.append(f"The most frequent molecular consequence in this selection is "
                   f"“{top_class}” ({by_class[top_class]:,} variants).")
    by_dom = stats.get("by_domain", {})
    kinase_n = sum(v for k, v in by_dom.items() if "kinase" in str(k).lower())
    if kinase_n:
        out.append(f"{kinase_n:,} variants map within the annotated kinase domain.")
    lm = stats.get("landmark_counts", {})
    lm_n = sum(v for k, v in lm.items() if k not in ("none", "nan", "None"))
    if lm_n:
        out.append(f"{lm_n:,} variants coincide with UniProt-annotated functional "
                   f"residues (active-site, binding-site or modified residues).")
    amc = stats.get("by_am_class", {})
    dam = sum(v for k, v in amc.items() if k in ("pathogenic", "likely_pathogenic"))
    if dam:
        out.append(f"{dam:,} variants carry a computationally damaging AlphaMissense "
                   f"classification (pathogenic or likely pathogenic).")
    cons = pd.to_numeric(df.get("conservation_score"), errors="coerce").dropna() \
        if "conservation_score" in df.columns else pd.Series(dtype=float)
    if len(cons):
        out.append(f"Mean residue conservation in this selection is "
                   f"{cons.mean():.2f} (range {cons.min():.2f}–{cons.max():.2f}, "
                   f"n={len(cons)}).")
    out.append("These observations describe computational and database evidence "
               "only; they do not establish clinical pathogenicity for any variant.")
    return out


# --------------------------------------------------------------------------- #
# HTML report
# --------------------------------------------------------------------------- #
CSS = f"""
body {{ font-family: 'Segoe UI', Inter, Arial, sans-serif; margin: 0; background: #f4f6fa; color: #1e293b; }}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 24px 64px; }}
header {{ background: linear-gradient(135deg, {NAVY} 0%, #123055 100%); color: #fff;
  border-radius: 14px; padding: 32px 36px; margin-bottom: 28px; }}
header h1 {{ margin: 0 0 6px; font-size: 24px; }}
header .sub {{ color: #9fc3e8; font-size: 13px; }}
.meta {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 22px; margin-bottom: 22px; font-size: 13px; }}
.meta b {{ color: #0f172a; }}
h2 {{ font-size: 18px; color: #0f172a; border-bottom: 2px solid #22d3ee33; padding-bottom: 6px; margin-top: 34px; }}
h3 {{ font-size: 15px; color: #1e3a5f; margin-top: 22px; }}
p, li {{ font-size: 14px; line-height: 1.65; }}
.badge {{ display: inline-block; background: #e0f2fe; color: #0369a1; border-radius: 6px;
  padding: 2px 8px; font-size: 12px; margin-right: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; background: #fff;
  border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; }}
th {{ background: #0f2a44; color: #dbeafe; text-align: left; padding: 8px 10px; font-weight: 600; }}
td {{ padding: 7px 10px; border-top: 1px solid #edf2f7; }}
tr:nth-child(even) td {{ background: #f8fafc; }}
img.fig {{ max-width: 100%; border-radius: 10px; border: 1px solid #e2e8f0; margin: 10px 0; }}
.figcap {{ font-size: 12px; color: #64748b; margin: 4px 0 18px; }}
.interp {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 14px 18px; }}
.limit {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 14px 18px; }}
.note {{ font-size: 12px; color: #64748b; }}
.empty {{ color: #64748b; font-style: italic; }}
footer {{ margin-top: 40px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 14px; }}
.chip {{ display:inline-block; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:14px; padding:2px 10px; margin:2px; font-size:12px; }}
code, .mono {{ font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; }}
"""


def _constraint_chips(constraints: dict) -> str:
    chips = []
    for k, v in constraints.items():
        if v in (None, [], 0, 0.0):
            continue
        chips.append(f"<span class='chip'><b>{_esc(k)}</b>: {_esc(v)}</span>")
    return "".join(chips) or "<span class='chip'>no filters (all variants)</span>"


def generate_html(result: dict, protein: dict, report_title: str,
                  section: str) -> str:
    df = pd.DataFrame(result.get("variants", []))
    s = result["summary"]
    stats = result["statistics"]
    cons_cfg = result["constraints"]

    figs = []
    if section in ("full", "variants"):
        p = fig_positions(df, "fig_positions.png")
        if p:
            figs.append(("Variant distribution along the CDK16 sequence "
                         f"({s['n_returned']:,} variants).", p))
    if section in ("full", "variants"):
        p = fig_counts(df, "variant_class", "Variant Consequence Distribution",
                       "fig_class.png")
        if p:
            figs.append(("Molecular consequence classes among selected variants.", p))
    if section in ("full", "predictions"):
        p = fig_histogram(df, "am_pathogenicity_score",
                          "AlphaMissense Pathogenicity Score Distribution",
                          "AlphaMissense score", "fig_am.png")
        if p:
            figs.append(("Distribution of AlphaMissense pathogenicity scores for "
                         "variants with available predictions.", p))
    if section in ("full", "conservation"):
        p = fig_histogram(df, "conservation_score",
                          "Residue Conservation Distribution",
                          "Conservation score (0–1)", "fig_cons.png", color=EMERALD)
        if p:
            figs.append(("Distribution of evolutionary conservation scores "
                         "(fraction of aligned orthologs sharing the human residue).", p))
    if section in ("full", "ranking"):
        p = fig_priority(df, "fig_priority.png")
        if p:
            figs.append(("Top 20 variants ranked by the integrated evidence "
                         "heuristic (CEPS). Research prioritization only — not a "
                         "clinical score.", p))

    interp = build_interpretation(result, df)

    limitations = [
        "Computational predictions (AlphaMissense, SIFT, PolyPhen) are probabilistic "
        "and must not be interpreted as clinical pathogenicity.",
        "Conservation indicates evolutionary constraint, not proven functional "
        "essentiality.",
        "No ClinVar submissions were available for this gene at retrieval time; "
        "clinical evidence columns are therefore empty rather than negative.",
        "Structural context derives from AlphaFold v4 predictions and a small number "
        "of experimental PDB entries; missing structures limit coverage.",
        "The prioritization score is a transparent research heuristic with "
        "user-configurable weights; it is not a validated diagnostic model.",
        "Population frequency data were not comprehensively available for all "
        "variants; missing frequency must not be read as rarity.",
    ]

    provenance_rows = "".join(
        f"<tr><td>{_esc(r.get('source_database'))}</td>"
        f"<td class='mono'>{_esc((r.get('source_url') or '')[:90])}</td>"
        f"<td>{_esc(r.get('retrieval_timestamp'))}</td>"
        f"<td>{_esc(r.get('status'))}</td></tr>"
        for r in result.get("provenance", []))

    figs_html = "".join(
        f"<img class='fig' src='figures/{p.name}' alt='{_esc(cap)}'>"
        f"<div class='figcap'>Figure: {_esc(cap)}</div>"
        for cap, p in figs)

    prov_html = (f"<table><thead><tr><th>Source</th><th>URL</th>"
                 f"<th>Retrieved</th><th>Status</th></tr></thead><tbody>{provenance_rows}"
                 f"</tbody></table>") if provenance_rows else \
        "<p class='empty'>Provenance records not available.</p>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{_esc(report_title)}</title><style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>{_esc(report_title)}</h1>
  <div class="sub">CDK16 Analysis Workbench · Structural &amp; Functional Landscape of CDK16 Variants</div>
</header>

<div class="meta">
  <b>Analysis:</b> {_esc(result.get('analysis_name', result['analysis_id']))}
  (<span class="mono">{_esc(result['analysis_id'])}</span>) · run {_esc(result['run_number'])}<br>
  <b>Report type:</b> {_esc(section)} · <b>Generated:</b> {_esc(utcnow())}<br>
  <b>Constraint hash:</b> <span class="mono">{_esc(result['constraint_hash'])}</span><br>
  <b>Constraints:</b> {_constraint_chips(cons_cfg)}<br>
  <b>Dataset:</b> {_esc(result.get('dataset_version', 'see provenance'))} ·
  pipeline {_esc(result.get('pipeline_version', '?'))} ·
  reference protein {_esc(protein.get('accession'))} ({protein.get('length')} aa)
</div>

<h2>1. Objective</h2>
<p>This report integrates genetic, protein, clinical, computational, evolutionary and
structural evidence for human CDK16 variants matching the analysis constraints, in
order to identify candidates that <i>may</i> warrant further biological investigation.
It is a research and educational analysis, not a clinical diagnostic tool.</p>

<h2>2. Analysis Configuration</h2>
<p>{_constraint_chips(cons_cfg)}</p>

<h2>3. Dataset Overview</h2>
<ul>
  <li>Variants available in the processed dataset: <b>{s['n_available']:,}</b></li>
  <li>Variants matching constraints: <b>{s['n_matched']:,}</b></li>
  <li>Variants in this report: <b>{s['n_returned']:,}</b>
      {"(truncated by the result cap)" if s.get("n_truncated") else ""}</li>
  <li>Zero-result selection: <b>{"yes" if s.get("zero_results") else "no"}</b></li>
</ul>

<h2>4. Results</h2>
{table_variants(df)}
{figs_html}

<h2>5. Interpretation</h2>
<div class="interp"><ul>{''.join(f'<li>{_esc(t)}</li>' for t in interp)}</ul></div>

<h2>6. Limitations</h2>
<div class="limit"><ul>{''.join(f'<li>{_esc(t)}</li>' for t in limitations)}</ul></div>

<h2>7. Data Provenance</h2>
{prov_html}

<footer>
Generated automatically by the CDK16 Analysis Workbench from computed results —
no values were manually entered. Report version stored with constraint hash
<span class="mono">{_esc(result['constraint_hash'])}</span>.
Research and educational use only.
</footer>
</div></body></html>"""


# --------------------------------------------------------------------------- #
# PDF export
# --------------------------------------------------------------------------- #
def generate_pdf(result: dict, protein: dict, report_title: str, html_path: Path,
                 pdf_path: Path) -> bool:
    if not HAS_PDF:
        log.warning("reportlab unavailable — PDF skipped")
        return False
    df = pd.DataFrame(result.get("variants", []))
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=report_title)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=17,
                        textColor=rl_colors.HexColor("#0f2a44"), spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13,
                        textColor=rl_colors.HexColor("#0f2a44"), spaceBefore=14)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("Small", parent=body, fontSize=8, leading=10.5,
                           textColor=rl_colors.HexColor("#475569"))

    story = [Paragraph(report_title, h1),
             Paragraph(f"Analysis {result['analysis_id']} · run "
                       f"{result['run_number']} · generated {utcnow()}", small),
             Spacer(1, 6)]

    s = result["summary"]
    story.append(Paragraph("Dataset overview", h2))
    story.append(Paragraph(
        f"Available variants: {s['n_available']:,} — matching constraints: "
        f"{s['n_matched']:,} — included: {s['n_returned']:,}.", body))
    story.append(Paragraph("Constraints", h2))
    chips = "; ".join(f"{k}={v}" for k, v in result["constraints"].items()
                      if v not in (None, [], 0, 0.0)) or "none (all variants)"
    story.append(Paragraph(_esc(chips), body))

    # variants table
    cols = [(c, label) for c, label in VARIANT_COLS if c in df.columns][:8]
    if not df.empty:
        story.append(Paragraph("Selected variants", h2))
        data = [[label for _, label in cols]]
        for _, r in df.head(30).iterrows():
            data.append([_fmt(r.get(c))[:28] for c, _ in cols])
        t = Table(data, repeatRows=1, colWidths=None)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#0f2a44")),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [rl_colors.white, rl_colors.HexColor("#f1f5f9")]),
        ]))
        story.append(t)
        if len(df) > 30:
            story.append(Paragraph(f"Showing first 30 of {len(df)} variants.", small))

    # figures
    figdir = REPORTS / "figures"
    for cap, fname in [("Variant distribution along CDK16", "fig_positions.png"),
                       ("Variant consequence distribution", "fig_class.png"),
                       ("AlphaMissense score distribution", "fig_am.png"),
                       ("Conservation distribution", "fig_cons.png"),
                       ("Top 20 candidates (CEPS)", "fig_priority.png")]:
        f = figdir / fname
        if f.exists() and f.stat().st_size > 0:
            story.append(Paragraph(cap, h2))
            story.append(Image(str(f), width=160 * mm, height=84 * mm))

    story.append(Paragraph("Interpretation", h2))
    for tline in build_interpretation(result, df):
        story.append(Paragraph("• " + _esc(tline), body))
    story.append(Paragraph("Limitations", h2))
    story.append(Paragraph(
        "Computational evidence does not establish clinical pathogenicity. "
        "This report is for research and educational use only.", small))
    story.append(Paragraph(
        f"Constraint hash {result['constraint_hash']} · report generated from the "
        f"immutable analysis result — reproducible from the stored configuration.",
        small))
    doc.build(story)
    return pdf_path.exists() and pdf_path.stat().st_size > 0


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def create_report(result: dict, section: str = "full",
                  version: int = 1) -> dict:
    """Generate a versioned report for an analysis result.

    Returns report metadata: {report_id, section, version, files, created_at}.
    """
    if section not in SECTIONS:
        raise ValueError(f"unknown report section: {section}")
    analysis_id = result["analysis_id"]
    rid = f"RPT-{analysis_id}-{section}-v{version}"

    rdir = REPORTS / analysis_id / f"{section}-v{version}"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "figures").mkdir(exist_ok=True)

    protein = {}
    pj = BUNDLED / "cdk16_protein.json"
    if pj.exists():
        protein = json.loads(pj.read_text(encoding="utf-8"))
    protein.setdefault("accession", "Q00536")
    protein.setdefault("length", 496)

    title = f"{SECTIONS[section]} — {result.get('analysis_name', analysis_id)}"

    html_path = rdir / "report.html"
    html_path.write_text(generate_html(result, protein, title, section),
                         encoding="utf-8")

    pdf_ok = False
    if section == "full":
        pdf_path = rdir / "report.pdf"
        pdf_ok = generate_pdf(result, protein, title, html_path, pdf_path)

    # copy figures used by html next to the report
    figsrc = REPORTS / "figures"
    for f in figsrc.glob("*.png"):
        (rdir / "figures" / f.name).write_bytes(f.read_bytes())

    meta = {
        "report_id": rid,
        "analysis_id": analysis_id,
        "analysis_name": result.get("analysis_name", analysis_id),
        "run_number": result.get("run_number"),
        "section": section,
        "version": version,
        "constraint_hash": result.get("constraint_hash"),
        "title": title,
        "created_at": utcnow(),
        "html_path": str(html_path),
        "pdf_path": str(rdir / "report.pdf") if pdf_ok else None,
        "pdf_generated": pdf_ok,
        "n_variants": result.get("summary", {}).get("n_returned", 0),
    }
    (rdir / "report.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("report created: %s (pdf=%s)", rid, pdf_ok)
    return meta
