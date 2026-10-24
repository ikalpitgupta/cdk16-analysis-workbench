import os
import pandas as pd
import pytest
from pathlib import Path
from api.report_generator import (
    _fmt,
    _esc,
    _fig_src,
    fig_counts,
    fig_histogram,
    fig_positions,
    fig_priority,
    table_variants,
    build_interpretation,
    generate_html,
    generate_pdf,
    create_report,
    SECTIONS,
)

def test_formatting_and_escaping():
    assert _fmt(None) == "—"
    assert _fmt(float("nan")) == "—"
    assert _fmt(123.4567) == "123.457"
    assert _fmt(5) == "5"
    assert _fmt("custom") == "custom"

    import html
    raw = "<script>alert('x & y')</script>"
    assert _esc(raw) == html.escape(raw)

def test_table_variants_rendering():
    empty_html = table_variants(pd.DataFrame())
    assert "No variants matched" in empty_html

    df = pd.DataFrame([
        {"variant_uid": "V1", "aa_change": "R285Q", "protein_position": 285, "priority_score": 85.0},
        {"variant_uid": "V2", "aa_change": "T145M", "protein_position": 145, "priority_score": 75.0},
    ])
    html = table_variants(df, n=1)
    assert "V1" in html
    assert "Showing first 1 of 2 variants" in html

def test_interpretation_builder():
    res_zero = {
        "summary": {"n_available": 100, "n_matched": 0, "n_returned": 0},
        "statistics": {}
    }
    interp_zero = build_interpretation(res_zero, pd.DataFrame())
    assert any("returned no matching variants" in s for s in interp_zero)

    res_matched = {
        "summary": {"n_available": 4000, "n_matched": 25, "n_returned": 25},
        "statistics": {
            "by_class": {"missense": 20, "synonymous": 5},
            "by_domain": {"Protein kinase": 15},
            "landmark_counts": {"active_site": 2},
            "by_am_class": {"pathogenic": 8},
        }
    }
    df = pd.DataFrame([{"conservation_score": 0.9}, {"conservation_score": 0.8}])
    interp = build_interpretation(res_matched, df)
    assert any("missense" in s for s in interp)
    assert any("kinase" in s for s in interp)
    assert any("active-site" in s for s in interp)
    assert any("AlphaMissense" in s for s in interp)

def test_figures_generation():
    df = pd.DataFrame({
        "variant_class": ["missense", "missense", "synonymous", "frameshift"],
        "am_pathogenicity_score": [0.95, 0.8, 0.2, 0.4],
        "protein_position": [50, 100, 150, 200],
        "priority_score": [90.0, 80.0, 40.0, 10.0],
    })
    p_counts = fig_counts(df, "variant_class", "Class Distribution", "test_class.png")
    assert p_counts is not None and p_counts.exists()

    p_hist = fig_histogram(df, "am_pathogenicity_score", "AM Distribution", "Score", "test_hist.png")
    assert p_hist is not None and p_hist.exists()

    p_pos = fig_positions(df, "test_pos.png", protein_length=496)
    assert p_pos is not None and p_pos.exists()

    p_pri = fig_priority(df, "test_pri.png")
    assert p_pri is not None and p_pri.exists()

def test_create_report_and_html_generation():
    result = {
        "analysis_id": "A-TEST-REP",
        "analysis_name": "Test Report Generation",
        "run_number": 1,
        "constraint_hash": "testhash1234",
        "constraints": {"variant_type": ["missense"], "min_conservation": 0.5},
        "generated_at": "2026-10-24T12:00:00Z",
        "summary": {
            "n_available": 1000,
            "n_matched": 10,
            "n_returned": 10,
            "n_truncated": False,
            "zero_results": False,
        },
        "statistics": {
            "by_class": {"missense": 10},
            "by_domain": {"Protein kinase": 8},
            "by_am_class": {"pathogenic": 6},
            "landmark_counts": {"active_site": 1},
        },
        "variants": [
            {
                "variant_uid": f"VAR_{i}",
                "aa_change": f"R{i}Q",
                "protein_position": 100 + i,
                "variant_class": "missense",
                "domain_name": "Protein kinase",
                "landmark_type": "active_site" if i == 0 else "none",
                "am_pathogenicity_score": 0.9,
                "am_pathogenicity_class": "pathogenic",
                "conservation_score": 0.85,
                "priority_score": 80.0,
            }
            for i in range(10)
        ],
        "top_variants": [],
        "warnings": [],
    }
    # Test all report sections
    for sec in SECTIONS:
        meta = create_report(result, section=sec, version=1)
        assert meta["report_id"].startswith(f"RPT-A-TEST-REP-{sec}")
        assert Path(meta["html_path"]).exists()
        html_content = Path(meta["html_path"]).read_text(encoding="utf-8")
        assert "<html" in html_content.lower()
        if sec == "full":
            assert meta["pdf_generated"] is True
            assert Path(meta["pdf_path"]).exists()
