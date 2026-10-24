import time
import pytest
from fastapi.testclient import TestClient
from api.server import app
from api.report_generator import SECTIONS

client = TestClient(app)

def test_overview_endpoint():
    r = client.get("/api/overview")
    assert r.status_code == 200
    data = r.json()
    assert "protein" in data
    assert "variants" in data
    assert "conservation" in data
    assert "structures" in data
    assert data["variants"]["total"] > 0

def test_protein_endpoint():
    r = client.get("/api/protein")
    assert r.status_code == 200
    data = r.json()
    assert data["accession"] == "Q00536"
    assert data["gene"] == "CDK16"
    assert len(data["sequence"]) == data["length"]

def test_conservation_endpoint():
    r = client.get("/api/conservation")
    assert r.status_code == 200
    data = r.json()
    assert "scores" in data
    assert data["n_homologs"] > 0

def test_predictions_endpoint():
    r = client.get("/api/predictions")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert data["n_scored"] > 0

def test_variants_pagination_and_sorting():
    r = client.get("/api/variants?page=1&page_size=25&sort_by=priority_score&sort_desc=true")
    assert r.status_code == 200
    data = r.json()
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert len(data["variants"]) == 25
    assert data["total"] > 0

def test_variants_search():
    r = client.get("/api/variants?search=R285Q")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(v["aa_change"] == "R285Q" for v in data["variants"])

def test_variants_filters():
    r = client.get("/api/variants?variant_class=missense&am_class=pathogenic")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    for v in data["variants"]:
        assert v["variant_class"] == "missense"
        assert v["am_pathogenicity_class"].lower() == "pathogenic"

def test_variant_detail():
    r = client.get("/api/variants?page=1&page_size=1")
    uid = r.json()["variants"][0]["variant_uid"]
    r_detail = client.get(f"/api/variants/{uid}")
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert "variant" in detail
    assert "protein_context" in detail
    assert "conservation" in detail
    assert "predictions" in detail
    assert "literature" in detail

def test_structures_and_file():
    r = client.get("/api/structures")
    assert r.status_code == 200
    data = r.json()
    assert "experimental" in data
    assert "predicted" in data

    # Test downloading CIF files
    for struct_id in ["3MTL", "5G6V", "9R2I", "AF-Q00536-F1"]:
        r_file = client.get(f"/api/structures/file/{struct_id}")
        assert r_file.status_code == 200
        assert len(r_file.content) > 1000

def test_literature_and_interactions_and_metadata():
    r_lit = client.get("/api/literature")
    assert r_lit.status_code == 200
    assert r_lit.json()["count"] > 0

    r_lit_paged = client.get("/api/literature?page=1&page_size=5")
    assert r_lit_paged.status_code == 200
    assert len(r_lit_paged.json()["articles"]) == 5

    r_int = client.get("/api/interactions")
    assert r_int.status_code == 200
    assert len(r_int.json()["interactors"]) > 0

    r_meta = client.get("/api/metadata")
    assert r_meta.status_code == 200
    assert "manifest" in r_meta.json()

def test_analysis_session_lifecycle():
    # 1. Create
    r_create = client.post("/api/analyses", json={
        "name": "Automated Test Session",
        "description": "Integration test analysis",
        "constraints": {
            "variant_type": ["missense"],
            "domain": ["kinase"],
            "min_conservation": 0.5,
            "min_am_score": 0.2,
            "limit": 50
        }
    })
    assert r_create.status_code == 200
    sess = r_create.json()
    sid = sess["id"]
    assert sess["name"] == "Automated Test Session"

    # 2. Get session
    r_get = client.get(f"/api/analyses/{sid}")
    assert r_get.status_code == 200
    assert r_get.json()["id"] == sid

    # 3. Update constraints
    r_up = client.put(f"/api/analyses/{sid}/constraints", json={
        "constraints": {
            "variant_type": ["missense"],
            "domain": ["kinase"],
            "min_conservation": 0.6,
            "min_am_score": 0.3,
            "limit": 50
        }
    })
    assert r_up.status_code == 200
    assert r_up.json()["constraints"]["min_conservation"] == 0.6

    # 4. Run analysis
    r_run = client.post(f"/api/analyses/{sid}/run")
    assert r_run.status_code == 200
    
    # Wait for completion (synchronous or fast thread)
    completed = False
    for _ in range(30):
        time.sleep(0.3)
        r_check = client.get(f"/api/analyses/{sid}")
        status = r_check.json().get("status")
        if status == "COMPLETED":
            completed = True
            break
        elif status == "FAILED":
            pytest.fail(f"Analysis failed: {r_check.json()}")
    assert completed, "Analysis did not complete in time"

    # 5. Results
    r_res = client.get(f"/api/analyses/{sid}/results")
    assert r_res.status_code == 200
    res = r_res.json()
    assert res["available"] is True
    assert res["summary"]["n_matched"] > 0
    assert len(res["variants"]) > 0

    # 6. Reports generation for all sections
    for sec in SECTIONS:
        r_rep = client.post(f"/api/analyses/{sid}/reports", json={"section": sec})
        assert r_rep.status_code == 200
        rep_meta = r_rep.json()
        assert rep_meta["section"] == sec
        rid = rep_meta["report_id"]

        # Test report endpoints
        r_rep_info = client.get(f"/api/reports/{rid}")
        assert r_rep_info.status_code == 200

        r_html = client.get(f"/api/reports/{rid}/html")
        assert r_html.status_code == 200
        assert "<html" in r_html.text.lower()

        r_down_html = client.get(f"/api/reports/{rid}/download?format=html")
        assert r_down_html.status_code == 200

        r_down_json = client.get(f"/api/reports/{rid}/download?format=json")
        assert r_down_json.status_code == 200

        # PDF download (optional if reportlab generated it)
        r_down_pdf = client.get(f"/api/reports/{rid}/download?format=pdf")
        assert r_down_pdf.status_code in (200, 404)

    # 7. List reports
    r_reps = client.get(f"/api/analyses/{sid}/reports")
    assert r_reps.status_code == 200
    assert len(r_reps.json()) == len(SECTIONS)

    r_all_reps = client.get("/api/reports")
    assert r_all_reps.status_code == 200
    assert any(r["id"] == rid for r in r_all_reps.json())

    # 8. Delete
    r_del = client.delete(f"/api/analyses/{sid}")
    assert r_del.status_code == 200
    assert client.get(f"/api/analyses/{sid}").status_code == 404
