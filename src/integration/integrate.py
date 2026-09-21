"""CDK16 integration pipeline: raw acquisitions -> processed normalized tables.

Produces:
  data/processed/cdk16_variants_master.csv   (variant master table)
  data/processed/cdk16_protein.json          (protein, features, domains, landmarks)
  data/processed/cdk16_conservation.json     (per-residue conservation scores)
  data/processed/cdk16_literature.json       (PubMed articles)
  data/processed/cdk16_interactions.json     (UniProt interaction partners)
  data/processed/cdk16_structures.json       (PDB + AlphaFold metadata)
  data/processed/pipeline_manifest.json      (run metadata + provenance)
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("integrate")

# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
KINASE_LANDMARKS = {  # UniProt Q00536 annotated functional residues
    "active_site": [33, 145],
    "binding_site": [33, 35, 81, 82, 145, 163, 165],
    "modified_residue": [13, 14, 95, 169, 180, 329, 341, 343],
}

PIP_SUPPORTED = {"L": 3.8, "I": 4.9, "V": 3.2, "F": 4.2, "M": 4.5, "W": 2.1,
                 "C": 2.5, "A": 2.85, "T": 2.7, "G": 0.0, "S": 0.0,
                 "Y": 0.0, "P": 0.0, "H": 0.0, "D": 0.0, "E": 0.0,
                 "N": 0.0, "Q": 0.0, "K": 0.0, "R": 0.0, "X": 0.0}

AA3 = {"A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys", "Q": "Gln",
       "E": "Glu", "G": "Gly", "H": "His", "I": "Ile", "L": "Leu", "K": "Lys",
       "M": "Met", "F": "Phe", "P": "Pro", "S": "Ser", "T": "Thr", "W": "Trp",
       "Y": "Tyr", "V": "Val", "*": "Ter"}

WEIGHTS = {
    "clinical": 0.20, "computational": 0.15, "conservation": 0.15,
    "structural": 0.15, "domain": 0.10, "literature": 0.10,
    "cross_db": 0.15,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def jload(path: Path):
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def jsave(obj, name: str) -> None:
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                            encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. Protein reference
# --------------------------------------------------------------------------- #
def build_protein() -> dict:
    up = jload(RAW / "uniprot_Q00536.json")
    if not up:
        log.critical("UniProt record missing — cannot build protein reference")
        sys.exit(1)

    seq = ""
    fpath = RAW / "uniprot_Q00536.fasta"
    if fpath.exists():
        seq = "".join(fpath.read_text().splitlines()[1:])
    else:
        seq = up.get("sequence", {}).get("value", "")

    features = []
    for f in up.get("features", []):
        loc = f.get("location", {})
        features.append({
            "type": f.get("type", ""),
            "start": loc.get("start", {}).get("value"),
            "end": loc.get("end", {}).get("value"),
            "description": (f.get("description") or "")[:200],
            "evidences": len(f.get("evidences", []) or []),
        })

    domains = []
    for f in features:
        if f["type"] in ("Domain", "Region"):
            domains.append(f)
    # kinase domain: prefer explicit "Protein kinase" domain annotation
    kinase = next((d for d in domains if "kinase" in d["description"].lower()), None)
    if kinase is None:
        # fall back to InterPro/CDD-style: the catalytic domain of PCTAIRE-type kinases
        kinase = {"type": "Domain", "start": 75, "end": 323,
                  "description": "Protein kinase domain (PCTAIRE-type; CDD/InterPro)",
                  "evidences": 0}
        domains.append(kinase)

    landmarks = []
    for ltype, positions in KINASE_LANDMARKS.items():
        for pos in positions:
            if 1 <= pos <= len(seq):
                landmarks.append({
                    "type": ltype, "position": pos,
                    "residue": seq[pos - 1],
                    "description": f"UniProt-annotated {ltype.replace('_', ' ')} residue",
                })

    interactions = []
    for c in up.get("comments", []):
        if c.get("commentType") == "INTERACTION":
            for it in c.get("interactions", []):
                p2 = it.get("interactantTwo", {})
                acc = p2.get("accession", "")
                if acc == "Q00536":  # self-interaction entry — skip
                    continue
                interactions.append({
                    "partner": p2.get("shortName") or acc,
                    "partner_accession": acc,
                    "experiments": it.get("experiments", 0),
                    "evidence_type": ("experimental" if it.get("experiments", 0) > 0
                                      else "database_predicted"),
                })

    def _comment(ct: str) -> str:
        for c in up.get("comments", []):
            if c.get("commentType") == ct:
                for t in c.get("texts", []):
                    v = t.get("value", "")
                    if v:
                        return v
        return ""

    similarity = _comment("SIMILARITY")
    family = "CMGC kinase family"
    for sep in (". Subfamily", "Subfamily"):
        if sep in similarity:
            family = similarity.split("family")[0].split(sep)[-1].strip(" .") + " family" if "family" in similarity else family
            break
    function_text = _comment("FUNCTION")
    keywords = [k.get("name", "") for k in up.get("keywords", [])][:14]

    protein = {
        "accession": "Q00536",
        "entry_name": up.get("primaryAccession", "Q00536") + "_" +
                      up.get("uniProtkbId", "CDK16_HUMAN"),
        "name": (up.get("proteinDescription", {}).get("recommendedName", {})
                 .get("fullName", {}).get("value", "Cyclin-dependent kinase 16")),
        "gene": next((g.get("geneName", {}).get("value", "CDK16")
                      for g in up.get("genes", [])), "CDK16"),
        "organism": up.get("organism", {}).get("scientificName", "Homo sapiens"),
        "length": len(seq),
        "sequence": seq,
        "mw_kda": round(up.get("sequence", {}).get("molWeight", 0) / 1000, 1),
        "family": family or "CMGC kinase family",
        "function": function_text[:220],
        "keywords": keywords,
        "features": features,
        "domains": domains,
        "landmarks": landmarks,
        "interactions": interactions,
        "uniprot_version": str(up.get("entryAudit", {}).get("entryVersion", "?")),
    }
    jsave(protein, "cdk16_protein.json")
    log.info("protein: %d aa, %d features, %d domains, %d landmarks, %d interactions",
             len(seq), len(features), len(domains), len(landmarks), len(interactions))
    return protein


# --------------------------------------------------------------------------- #
# 2. Conservation from homologs (needleman-wunsch-free: position-wise where
#    aligned via simple MAFFT-free approach — use pairwise identity to human at
#    the human position after global alignment via Bio.Align.PairwiseAligner)
# --------------------------------------------------------------------------- #
def conservation_scores(seq: str, homologs: list[dict]) -> tuple[list[float], list[int]]:
    """Per-human-residue conservation: fraction of aligned orthologs sharing
    the human residue (weighted 0/0.5/1 by similarity class)."""
    from Bio import Align
    aligner = Align.PairwiseAligner()
    aligner.mode = "global"
    aligner.open_gap_score = -11
    aligner.extend_gap_score = -1
    aligner.substitution_matrix = Align.substitution_matrices.load("BLOSUM62")

    similar_groups = [
        set("ILV"), set("FWY"), set("KRH"), set("DE"), set("NQ"), set("ST"),
        set("GA"), set("MIL"), set("TS"), set("QEK"),
    ]

    def sim_class(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if {a, b} in [set(g) for g in similar_groups]:
            return 0.5
        return 0.0

    scores: list[float] = []
    n_shared: list[int] = []
    for i, aa in enumerate(seq):
        vals = []
        shared = 0
        for h in homologs:
            hseq = h.get("sequence", "")
            if not hseq:
                continue
            try:
                aln = aligner.align(seq, hseq)[0]
                h_aln, q_aln = aln[0], aln[1]
                # map human position i to aligned column
                col = None
                hpos = 0
                for c, (a, b) in enumerate(zip(q_aln, h_aln)):
                    if a != "-":
                        if hpos == i:
                            col = c
                            break
                        hpos += 1
                if col is not None and h_aln[col] != "-":
                    v = sim_class(seq[i], h_aln[col])
                    vals.append(v)
                    if v == 1.0:
                        shared += 1
            except Exception:
                continue
        if vals:
            scores.append(round(sum(vals) / len(vals), 3))
            n_shared.append(shared)
        else:
            scores.append(None)
            n_shared.append(0)
    return scores, n_shared


# --------------------------------------------------------------------------- #
# 3. Variants master table
# --------------------------------------------------------------------------- #
VEP_CONSEQUENCE_MAP = {
    "missense_variant": "missense", "synonymous_variant": "synonymous",
    "stop_gained": "nonsense", "frameshift_variant": "frameshift",
    "splice_acceptor_variant": "splice", "splice_donor_variant": "splice",
    "start_lost": "start_lost", "stop_lost": "stop_lost",
    "inframe_insertion": "other", "inframe_deletion": "other",
}


def classify_consequence(consequences: list[str]) -> str:
    for c in consequences:
        key = VEP_CONSEQUENCE_MAP.get(c)
        if key:
            return key
    if any("splice" in c for c in consequences):
        return "splice"
    if any("coding" in c for c in consequences):
        return "other"
    return "other"


def aa_short(hgvs_p: str) -> tuple[int, str, str] | None:
    """Parse protein HGVS like 'ENSP00000349762.4:p.Ser484Leu' or 'p.Lys194Asn'
    -> (484, 'S', 'L'). Accepts an optional transcript/protein accession prefix."""
    m = re.search(r"p\.([A-Za-z]{3})(\d+)([A-Za-z]{3})$", hgvs_p or "")
    if not m:
        return None
    rev = {v: k for k, v in AA3.items()}
    ref = rev.get(m.group(1).capitalize())
    alt = rev.get(m.group(3).capitalize())
    if not ref or not alt:
        return None
    return int(m.group(2)), ref, alt


# AlphaMissense enrichment via EBI ProtVar (scores precomputed for the human
# proteome; per-variant lookup by UniProt accession + position + mutant aa).
PROTVAR_BASE = "https://www.ebi.ac.uk/ProtVar/api/score"

# --------------------------------------------------------------------------- #
# ClinVar enrichment: per-variant clinical significance via NCBI esummary.
# --------------------------------------------------------- ----------------- #
CLINVAR_REVIEW = {
    "0": "no assertion criteria provided",
    "1": "criteria provided, single submitter",
    "2": "criteria provided, multiple submitters, no conflicts",
    "3": "criteria provided, conflicting interpretations",
    "4": "criteria provided, single submitter (practice guideline)",
    "5": "no assertion provided",
    "6": "practice guideline",
    "7": "review status not assigned",
}


def fetch_clinvar_significance(clinvar_ids: list[str]) -> dict:
    """Return {clinvar_id: {significance, review_status, condition, hgvs_c,
    protein_change, rsid}} via esummary in batches, cached on disk.
    Failures degrade gracefully (missing annotations stay empty)."""
    import urllib.request

    cache_path = RAW / "clinvar_significance.json"
    out: dict = {k: v for k, v in (jload(cache_path) or {}).items()}
    todo = [str(c) for c in clinvar_ids if c and str(c) not in out]
    if not todo:
        return out
    BATCH = 40
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
               "?db=clinvar&id=" + ",".join(chunk) + "&retmode=json")
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "cdk16-workbench/1.0"})
                with urllib.request.urlopen(req, timeout=40) as resp:
                    d = json.loads(resp.read())
                res = d.get("result", {})
                for uid in chunk:
                    rec = res.get(uid)
                    if not rec or uid == "uids":
                        continue
                    gc = rec.get("germline_classification", {}) or {}
                    sig = str(gc.get("description", "")).strip()
                    review = str(gc.get("review_status", "")).strip() or CLINVAR_REVIEW.get(
                        str(gc.get("review_status", "")), "")
                    cond = ""
                    for t in (gc.get("trait_set", []) or []) + (rec.get("trait_set", []) or []):
                        if t.get("trait_name"):
                            cond = t["trait_name"][:120]
                            break
                    hgvs_c = ""
                    pchange = str(rec.get("protein_change", "") or "")
                    rsid = None
                    for vs in (rec.get("variation_set", []) or []):
                        vn = vs.get("variation_name", "") or ""
                        if not hgvs_c:
                            m2 = re.search(r"(NM_\d+\.\d+[^:]*:c\.[^ ]+)", vn)
                            if m2:
                                hgvs_c = m2.group(1)
                        m3 = re.match(r"^(rs\d+)", vn)
                        if m3 and rsid is None:
                            rsid = m3.group(1)
                        for x in (vs.get("variation_xrefs", []) or []):
                            if x.get("db_source") == "dbSNP" and rsid is None:
                                rsid = f"rs{x.get('db_id')}"
                    if not hgvs_c:
                        # some records carry the HGVS only in the record title
                        m4 = re.search(r"(NM_\d+\.\d+[^:]*:c\.[^ ]+)", str(rec.get("title", "")))
                        if m4:
                            hgvs_c = m4.group(1)
                    locs = []
                    for vs in (rec.get("variation_set", []) or []):
                        for loc in (vs.get("variation_loc", []) or []):
                            if (loc.get("assembly_name") == "GRCh38"
                                    and loc.get("start") and loc.get("stop")
                                    and str(loc.get("start")) == str(loc.get("stop"))):
                                locs.append((loc.get("chr", ""), int(loc["start"])))
                    out[uid] = {"significance": sig, "review_status": review,
                                "condition": cond, "hgvs_c": hgvs_c,
                                "protein_change": pchange, "rsid": rsid,
                                "variation_locs": locs}
                break
            except Exception:
                if attempt == 2:
                    log.warning("ClinVar esummary failed for batch %d", i // BATCH + 1)
                else:
                    time.sleep(1.5)
        time.sleep(0.4)  # NCBI rate limit
    cache_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def fetch_am_scores(positions_aas: list[tuple[int, str]], cache: dict | None = None) -> dict:
    """Return {(pos, mt): (score, class)} for each (position, one-letter alt aa).
    Cached results are reused; failures degrade gracefully to missing scores."""
    import urllib.request
    import urllib.error

    out: dict = cache if cache is not None else {}
    for pos, mt in positions_aas:
        key = (int(pos), str(mt))
        if key in out or not mt or pd.isna(mt):
            continue
        url = f"{PROTVAR_BASE}/Q00536/{int(pos)}?type=AM&mt={mt}"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    arr = json.loads(resp.read())
                if arr and isinstance(arr, list):
                    row = arr[0]
                    out[key] = (float(row["amPathogenicity"]), str(row.get("amClass", "")))
                else:
                    out[key] = (None, None)
                break
            except Exception:
                if attempt == 2:
                    log.warning("ProtVar AM lookup failed for pos %d mt %s", pos, mt)
                    out[key] = (None, None)
                else:
                    time.sleep(1.0 + attempt)
        time.sleep(0.15)  # polite rate limiting
    return out


def build_variants(protein: dict) -> pd.DataFrame:
    seq = protein["sequence"]
    up = jload(RAW / "uniprot_Q00536.json")
    vep = jload(RAW / "vep_results.json") or {}

    rows: list[dict] = []
    uid_seen: set[str] = set()

    def add_row(r: dict) -> None:
        uid = r["variant_uid"]
        if uid in uid_seen:
            # merge: keep first, cross-ref the second source
            return
        uid_seen.add(uid)
        rows.append(r)

    # ---- A. dbSNP rsIDs + VEP consequences (primary source) ----
    for rid, item in vep.items():
        # pick the canonical NM_006201 transcript annotation if present
        tconfs = item.get("transcript_consequences", [])
        canonical = None
        for tc in tconfs:
            if tc.get("canonical") == 1 or tc.get("mane") == "NM_006201.5":
                canonical = tc
                break
        tc = canonical or (tconfs[0] if tconfs else None)
        if tc is None:
            variant_class = "other"
            protein_pos = None
            aa_change = ""
            hgvs_t = ""
            hgvs_p = ""
        else:
            cons = tc.get("consequence_terms", [])
            variant_class = classify_consequence(cons)
            hgvs_t = tc.get("hgvsc", "")
            hgvs_p = tc.get("hgvsp", "").replace("%3D", "=")
            protein_pos = tc.get("protein_start")
            aa_change = ""
            parsed = aa_short(hgvs_p)
            if parsed:
                pos, ref, alt = parsed
                aa_change = f"{ref}{pos}{alt}"
                protein_pos = pos
                # verify ref amino acid against canonical sequence
                if 1 <= pos <= len(seq) and seq[pos - 1] != ref:
                    aa_change = ""
                    protein_pos = None

        rows_src = "Ensembl VEP (dbSNP)"
        g = item.get("seq_region_name", "")
        pos_g = item.get("start")
        alleles = item.get("allele_string", "").replace("/", "\t")
        add_row({
            "variant_uid": f"rs{rid}",
            "source": rows_src,
            "source_record_id": f"rs{rid}",
            "rsid": f"rs{rid}",
            "clinvar_id": None,
            "chromosome": g,
            "genomic_position": pos_g,
            "reference_allele": item.get("allele_string", "").split("/")[0] if item.get("allele_string") else None,
            "alternate_allele": (item.get("allele_string", "").split("/")[1]
                                 if item.get("allele_string", "").count("/") >= 1 else None),
            "hgvs_genomic": item.get("input", ""),
            "hgvs_transcript": hgvs_t,
            "hgvs_protein": hgvs_p,
            "transcript_id": (tc or {}).get("transcript_id", "") if tc else "",
            "protein_id": "NP_006192.1" if tc else "",
            "protein_position": protein_pos,
            "ref_amino_acid": aa_change[0] if aa_change else None,
            "alt_amino_acid": aa_change[-1] if aa_change else None,
            "aa_change": aa_change,
            "variant_class": variant_class,
            "molecular_consequence": ";".join(tc.get("consequence_terms", [])) if tc else "",
            "clinical_significance": None,
            "review_status": None,
            "condition": None,
            "allele_frequency": None,
            "literature_ids": "",
            "sift_score": (tc or {}).get("sift_score") if tc else None,
            "sift_prediction": (tc or {}).get("sift_prediction") if tc else None,
            "polyphen_score": (tc or {}).get("polyphen_score") if tc else None,
            "polyphen_prediction": (tc or {}).get("polyphen_prediction") if tc else None,
        })

    # ---- B. UniProt natural variants / mutagenesis ----
    for f in (up or {}).get("features", []):
        ftype = f.get("type", "")
        if ftype not in ("Natural variant", "Mutagenesis"):
            continue
        loc = f.get("location", {})
        pos = loc.get("start", {}).get("value")
        if pos is None or not (1 <= pos <= len(seq)):
            continue
        alt_res = ""
        desc = f.get("description") or ""
        m = re.search(r"->\s*([A-Z])", desc)
        if m:
            alt_res = m.group(1)
        ref_res = seq[pos - 1]
        var_class = "missense" if alt_res and alt_res != ref_res else "other"
        add_row({
            "variant_uid": f"UNIPROT_{ftype}_{pos}_{alt_res or 'X'}",
            "source": "UniProt",
            "source_record_id": f"Q00536:{ftype}:{pos}",
            "rsid": None, "clinvar_id": None,
            "chromosome": None, "genomic_position": None,
            "reference_allele": None, "alternate_allele": None,
            "hgvs_genomic": None,
            "hgvs_transcript": f"c.{3 * pos - 2}_{3 * pos}>{'?' if not alt_res else '?'}",
            "hgvs_protein": f"p.{AA3.get(ref_res, ref_res)}{pos}"
                            + (f"{AA3.get(alt_res, alt_res)}" if alt_res else ""),
            "transcript_id": "NM_006201.5", "protein_id": "NP_006192.1",
            "protein_position": pos,
            "ref_amino_acid": ref_res, "alt_amino_acid": alt_res or None,
            "aa_change": f"{ref_res}{pos}{alt_res}" if alt_res else f"{ref_res}{pos}?",
            "variant_class": var_class,
            "molecular_consequence": ftype.lower().replace(" ", "_"),
            "clinical_significance": None, "review_status": None, "condition": None,
            "allele_frequency": None, "literature_ids": "",
            "sift_score": None, "sift_prediction": None,
            "polyphen_score": None, "polyphen_prediction": None,
        })

    # ---- B1. ClinVar SNV records as first-class variant rows ----
    # Adds SNV ClinVar submissions (missense / nonsense / synonymous / splice /
    # start/stop-lost) that are absent from the dbSNP-derived set. CNVs and
    # records without a resolvable protein position are logged, not fabricated.
    clinvar_ids0 = jload(RAW / "clinvar_ids.json") or []
    clin_recs = fetch_clinvar_significance([str(c) for c in clinvar_ids0]) if clinvar_ids0 else {}
    added_clinvar = 0
    skipped_clinvar = 0
    existing_hgvs_p = set()
    for r in rows:
        if r.get("hgvs_protein"):
            existing_hgvs_p.add(r["hgvs_protein"])
    for cid, rec in clin_recs.items():
        sig = rec.get("significance") or ""
        hgvs_c = rec.get("hgvs_c") or ""
        pc = rec.get("protein_change") or ""
        m_pc = re.match(r"^([A-Z])(\d+)([A-Z])$", pc.split(",")[0].strip())
        if not (m_pc and sig):
            skipped_clinvar += 1
            continue
        pos = int(m_pc.group(2))
        ref_a, alt_a = m_pc.group(1), m_pc.group(3)
        if not (1 <= pos <= len(seq)) or seq[pos - 1] != ref_a:
            skipped_clinvar += 1
            continue
        hp = f"p.{AA3.get(ref_a, ref_a)}{pos}{AA3.get(alt_a, alt_a)}"
        if hp in existing_hgvs_p:
            skipped_clinvar += 1  # already present from dbSNP/UniProt; enrichment joins later
            continue
        existing_hgvs_p.add(hp)
        cls = "missense" if ref_a != alt_a and "*" not in alt_a else (
            "nonsense" if alt_a == "*" else "other")
        rows.append({
            "variant_uid": f"CLINVAR_{cid}",
            "source": "ClinVar",
            "source_record_id": f"VCV{cid}",
            "rsid": rec.get("rsid"), "clinvar_id": cid,
            "chromosome": "X", "genomic_position": None,
            "reference_allele": None, "alternate_allele": None,
            "hgvs_genomic": None,
            "hgvs_transcript": hgvs_c or None,
            "hgvs_protein": hp,
            "transcript_id": "NM_006201.5", "protein_id": "NP_006192.1",
            "protein_position": pos,
            "ref_amino_acid": ref_a, "alt_amino_acid": alt_a,
            "aa_change": f"{ref_a}{pos}{alt_a}",
            "variant_class": cls,
            "molecular_consequence": "clinvar_snv",
            "clinical_significance": sig,
            "review_status": rec.get("review_status"),
            "condition": rec.get("condition"),
            "allele_frequency": None, "literature_ids": "",
            "sift_score": None, "sift_prediction": None,
            "polyphen_score": None, "polyphen_prediction": None,
        })
        added_clinvar += 1
    if added_clinvar or skipped_clinvar:
        log.info("ClinVar records added as rows: %d (skipped %d: CNV/no position/already present)",
                 added_clinvar, skipped_clinvar)

    df = pd.DataFrame(rows)
    if df.empty:
        log.warning("no variants collected")
        return df

    # ---- B0. ClinVar enrichment (join by c.HGVS primary, rsID fallback) ----
    clinvar_ids = jload(RAW / "clinvar_ids.json") or []
    if clinvar_ids:
        log.info("enriching clinical annotations for %d ClinVar submissions ...", len(clinvar_ids))
        clin = fetch_clinvar_significance([str(c) for c in clinvar_ids])
        by_hgvs: dict[str, dict] = {}
        by_rsid: dict[str, dict] = {}
        for cid, rec in clin.items():
            rec = dict(rec)
            rec["clinvar_id"] = cid
            hc = rec.get("hgvs_c") or ""
            m5 = re.search(r":(c\..+)$", hc)  # strip 'NM_006201.5(CDK16):' prefix
            if m5:
                by_hgvs.setdefault(m5.group(1), rec)
            if rec.get("rsid"):
                by_rsid.setdefault(rec["rsid"], rec)
        # position index from ClinVar records carrying GRCh38 SNV coordinates
        by_pos: dict[tuple, dict] = {}
        for cid, rec in clin.items():
            for vs in (rec.get("variation_locs") or []):
                key = (str(vs[0]).lower(), int(vs[1]))
                # only accept unambiguous positions
                if key in by_pos and by_pos[key].get("clinvar_id") != cid:
                    by_pos[key] = {"clinvar_id": None}  # ambiguous -> block
                else:
                    by_pos.setdefault(key, rec)
        n_matched = n_hgvs = n_rs = n_pos = 0
        for idx, r in df.iterrows():
            rec = None
            how = None
            hgvs_t = r.get("hgvs_transcript")
            if isinstance(hgvs_t, str) and hgvs_t:
                # normalize VEP hgvsc 'NM_006201.5:c.1098G>A' -> 'c.1098G>A'
                m3 = re.search(r":(c\..+)$", hgvs_t)
                key = m3.group(1) if m3 else hgvs_t
                rec = by_hgvs.get(key)
                how = "hgvs"
            if rec is None and isinstance(r.get("rsid"), str):
                rec = by_rsid.get(r["rsid"])
                how = "rsid"
            if rec is None and r.get("genomic_position") is not None:
                try:
                    gpos = int(float(r["genomic_position"]))
                    cand = by_pos.get((str(r.get("chromosome", "")).lower(), gpos))
                    if cand and cand.get("clinvar_id"):
                        rec = cand
                        how = "position"
                except (ValueError, TypeError):
                    pass
            if rec:
                n_matched += 1
                n_hgvs += how == "hgvs"
                n_rs += how == "rsid"
                n_pos += how == "position"
                df.at[idx, "clinvar_id"] = rec["clinvar_id"]
                df.at[idx, "clinical_significance"] = rec.get("significance") or None
                df.at[idx, "review_status"] = rec.get("review_status") or None
                df.at[idx, "condition"] = rec.get("condition") or None
        log.info("ClinVar: %d / %d variants matched (hgvs=%d, rsid=%d, position=%d; "
                 "%d c.HGVS keys, %d rsID keys, %d position keys)",
                 n_matched, len(df), n_hgvs, n_rs, n_pos,
                 len(by_hgvs), len(by_rsid), len(by_pos))

    # ---- C. domain + landmark mapping ----
    domains = protein["domains"]
    def domain_of(pos):
        if pos is None or pd.isna(pos):
            return None
        for d in domains:
            if d["start"] <= pos <= d["end"]:
                return d["description"].split("(")[0].strip() or d["description"]
        return None
    df["domain_name"] = df["protein_position"].apply(domain_of)

    lm_by_pos = {l["position"]: l["type"] for l in protein["landmarks"]}
    df["landmark_type"] = df["protein_position"].map(lm_by_pos).fillna("none")

    # ---- D. conservation join (per protein position) ----
    cons = jload(OUT / "cdk16_conservation.json") or {}
    scores = cons.get("scores", [])
    n_sp = cons.get("n_shared", [])
    if scores:
        pos_series = pd.to_numeric(df["protein_position"], errors="coerce")
        df["conservation_score"] = pos_series.apply(
            lambda p: scores[int(p) - 1] if pd.notna(p) and 1 <= int(p) <= len(scores) else None)
        df["n_species_shared"] = pos_series.apply(
            lambda p: n_sp[int(p) - 1] if pd.notna(p) and 1 <= int(p) <= len(n_sp) else None)
    else:
        df["conservation_score"] = None
        df["n_species_shared"] = None

    # ---- E. AlphaMissense scores ----
    # Primary: local CSV (Swiss-Model export) if present; otherwise live
    # enrichment via EBI ProtVar for the missense variants that need scores.
    am_path = RAW / "alphamissense_Q00536.csv"
    am_scores: dict = {}
    if am_path.exists() and am_path.stat().st_size > 0:
        try:
            am = pd.read_csv(am_path)
            am.columns = [c.strip().lower() for c in am.columns]
            if "protein_pos" in am.columns:
                am["protein_pos"] = pd.to_numeric(am["protein_pos"], errors="coerce")
                am = am.dropna(subset=["protein_pos"])
                am["protein_pos"] = am["protein_pos"].astype(int)
                def am_lookup(pos, alt):
                    if pd.isna(pos):
                        return None, None
                    sub = am[am["protein_pos"] == int(pos)]
                    if len(sub) == 0:
                        return None, None
                    if alt and "alt_aa" in sub.columns:
                        m2 = sub[sub["alt_aa"].astype(str).str.upper() == str(alt).upper()]
                        sub = m2 if len(m2) else sub
                    row = sub.iloc[0]
                    return (float(row.get("am_pathogenicity", np.nan)),
                            str(row.get("am_class", "")))
                amres = df.apply(lambda r: am_lookup(r["protein_position"], r["alt_amino_acid"]), axis=1)
                df["am_pathogenicity_score"] = [x[0] for x in amres]
                df["am_pathogenicity_class"] = [x[1] for x in amres]
                log.info("AM scores from local CSV: %d", df["am_pathogenicity_score"].notna().sum())
        except Exception:
            am_scores = {}
    if "am_pathogenicity_score" not in df.columns or df["am_pathogenicity_score"].notna().sum() == 0:
        if am_path.exists() and am_path.stat().st_size > 0:
            df["am_pathogenicity_score"] = None
            df["am_pathogenicity_class"] = None
        log.info("enriching AlphaMissense scores via EBI ProtVar for %d missense variants ...",
                 int((df["variant_class"] == "missense").sum()))
        needed = [(int(r.protein_position), str(r.alt_amino_acid))
                  for r in df[df["variant_class"] == "missense"].itertuples()
                  if pd.notna(r.protein_position) and pd.notna(r.alt_amino_acid)]
        am_cache_path = RAW / "protvar_am_scores.json"
        cached = jload(am_cache_path) or {}
        cache = {(int(k.split(":")[0]), k.split(":")[1]): tuple(v) for k, v in cached.items()}
        fetch_am_scores(needed, cache)
        (RAW / "protvar_am_scores.json").write_text(
            json.dumps({f"{p}:{m}": v for (p, m), v in cache.items()}, indent=1),
            encoding="utf-8")
        def am_row(r):
            if pd.isna(r["protein_position"]) or pd.isna(r["alt_amino_acid"]):
                return (None, None)
            return cache.get((int(r["protein_position"]), str(r["alt_amino_acid"])), (None, None))
        amres = df.apply(am_row, axis=1)
        df["am_pathogenicity_score"] = [x[0] for x in amres]
        df["am_pathogenicity_class"] = [x[1] for x in amres]
        n_am = df["am_pathogenicity_score"].notna().sum()
        log.info("AM scores via ProtVar: %d / %d missense", n_am,
                 int((df["variant_class"] == "missense").sum()))

    # ---- F. priority score (documented heuristic, NOT clinical) ----
    def clinical_evidence(cs):
        if not cs:
            return 0.0
        s = str(cs).lower()
        if "pathogenic" in s and "likely" in s and "conflict" not in s:
            return 1.0
        if s.strip() == "pathogenic":
            return 1.0
        if "conflicting" in s:
            return 0.5
        if "uncertain significance" in s or s.strip() == "vus":
            return 0.6
        if "benign" in s:
            return 0.2
        return 0.4
    def computational_evidence(row):
        s = row.get("am_pathogenicity_score")
        if s is None or pd.isna(s):
            return 0.0
        return min(1.0, max(0.0, float(s)))
    def conservation_evidence(row):
        c = row.get("conservation_score")
        return 0.0 if c is None or pd.isna(c) else min(1.0, max(0.0, float(c)))
    def structural_evidence(row):
        return 0.5 if row.get("landmark_type") not in (None, "none") else \
               (0.25 if row.get("domain_name") else 0.0)
    def domain_evidence(row):
        if not row.get("domain_name"):
            return 0.0
        return 0.6 if "kinase" in str(row["domain_name"]).lower() else 0.3
    def literature_evidence(row):
        return 0.5 if row.get("literature_ids") else 0.0
    def cross_db_evidence(row):
        n = sum(bool(row.get(c)) for c in
                ("rsid", "hgvs_transcript", "hgvs_protein", "protein_position"))
        return min(1.0, n / 4)

    df["ev_clinical"] = df["clinical_significance"].apply(clinical_evidence)
    df["ev_computational"] = df.apply(computational_evidence, axis=1)
    df["ev_conservation"] = df.apply(conservation_evidence, axis=1)
    df["ev_structural"] = df.apply(structural_evidence, axis=1)
    df["ev_domain"] = df.apply(domain_evidence, axis=1)
    df["ev_literature"] = df.apply(literature_evidence, axis=1)
    df["ev_cross_db"] = df.apply(cross_db_evidence, axis=1)
    df["priority_score"] = (
        WEIGHTS["clinical"] * df["ev_clinical"] +
        WEIGHTS["computational"] * df["ev_computational"] +
        WEIGHTS["conservation"] * df["ev_conservation"] +
        WEIGHTS["structural"] * df["ev_structural"] +
        WEIGHTS["domain"] * df["ev_domain"] +
        WEIGHTS["literature"] * df["ev_literature"] +
        WEIGHTS["cross_db"] * df["ev_cross_db"]
    ).round(4) * 100

    df["priority_score"] = df["priority_score"].round(2)

    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "cdk16_variants_master.csv", index=False)
    log.info("master table: %d variants (%d missense)",
             len(df), (df["variant_class"] == "missense").sum())
    return df


# --------------------------------------------------------------------------- #
# 4. Literature + structures + manifest
# --------------------------------------------------------------------------- #
def build_literature() -> list[dict]:
    arts = jload(RAW / "pubmed_articles.json") or []
    jsave(arts, "cdk16_literature.json")
    log.info("literature: %d articles", len(arts))
    return arts


def build_structures() -> dict:
    pdb = jload(RAW / "pdb_structures.json") or []
    out = {"experimental": pdb, "predicted": {
        "alphafold_id": "AF-Q00536-F1",
        "file": str(ROOT / "data" / "structures" / "AF-Q00536-F1.cif"),
        "version": "model_v4",
    }}
    jsave(out, "cdk16_structures.json")
    log.info("structures: %d experimental + AlphaFold", len(pdb))
    return out


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    protein = build_protein()

    homologs = jload(RAW / "homologs.json") or []
    cons_path = OUT / "cdk16_conservation.json"
    if not cons_path.exists() and homologs:
        log.info("computing conservation (%d homologs) ...", len(homologs))
        scores, n_shared = conservation_scores(protein["sequence"], homologs)
        jsave({"method": "pairwise BLOSUM62 alignment identity fraction (similarity-weighted)",
               "n_homologs": len(homologs),
               "homologs": [{"species": h["species"], "accession": h["accession"]}
                            for h in homologs],
               "scores": scores, "n_shared": n_shared}, "cdk16_conservation.json")
    elif cons_path.exists():
        log.info("conservation cached")

    build_variants(protein)
    build_literature()
    build_structures()

    manifest = {
        "generated_at": utcnow(),
        "pipeline": "cdk16-integration v2.0",
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "elapsed_s": round(time.time() - t0, 1),
    }
    prov = RAW / "data_provenance.csv"
    if prov.exists():
        manifest["provenance_file"] = str(prov)
    jsave(manifest, "pipeline_manifest.json")
    log.info("integration complete in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
