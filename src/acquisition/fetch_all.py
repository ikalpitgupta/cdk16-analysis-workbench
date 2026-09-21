"""CDK16 data acquisition pipeline.

Retrieves real data from public APIs with caching, retries, timeouts and
provenance. Every response is saved verbatim under data/raw/. Nothing is
fabricated: sources that fail are recorded as unavailable in the manifest.

Run:  python -m src.acquisition.fetch_all
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache"
LOGS = ROOT / "logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOGS / "acquisition.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("acquire")

UNIPROT_ACC = "Q00536"
NCBI_GENE_ID = "5127"
ENSEMBL_GENE = "ENSG00000102225"

HEADERS_JSON = {"Accept": "application/json"}
HEADERS_FASTA = {"Accept": "text/x-fasta"}

PROVENANCE: list[dict] = []


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_provenance(source: str, url: str, record_id: str, version: str | None,
                      status: str, n_records: int | None = None) -> None:
    PROVENANCE.append({
        "source_database": source,
        "source_url": url,
        "retrieval_timestamp": stamp(),
        "database_version": version or "not_provided",
        "record_id": record_id,
        "status": status,
        "n_records": n_records if n_records is not None else "",
    })


def fetch(url: str, *, headers: dict | None = None, params: dict | None = None,
          method: str = "GET", body: dict | None = None, tries: int = 4,
          timeout: int = 45, sleep_on_retry: float = 3.0) -> requests.Response | None:
    """HTTP fetch with retries and rate-limit handling. Returns None on failure."""
    hdr = dict(headers or {})
    for attempt in range(1, tries + 1):
        try:
            if method == "POST":
                r = requests.post(url, headers=hdr, params=params, json=body, timeout=timeout)
            else:
                r = requests.get(url, headers=hdr, params=params, timeout=timeout)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "10") or 10)
                log.warning("429 rate-limited on %s; sleeping %ss", url, wait)
                time.sleep(wait)
                continue
            if r.status_code == 404:
                log.error("404 not found: %s", url)
                return None
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            log.warning("attempt %d/%d failed for %s: %s", attempt, tries, url, exc)
            time.sleep(sleep_on_retry * attempt)
    log.error("giving up on %s", url)
    return None


def save_raw(name: str, content: str) -> Path:
    path = RAW / name
    path.write_text(content, encoding="utf-8")
    return path


def load_or_fetch(name: str, url: str, **kw) -> str | None:
    """Use cached raw file when present, else fetch and cache."""
    path = RAW / name
    if path.exists() and path.stat().st_size > 0:
        log.info("cache hit: %s", name)
        return path.read_text(encoding="utf-8")
    r = fetch(url, **kw)
    if r is None:
        return None
    save_raw(name, r.text)
    return r.text


# --------------------------------------------------------------------------- #
# 1. UniProt
# --------------------------------------------------------------------------- #
def fetch_uniprot() -> dict | None:
    log.info("=== UniProt Q00536 ===")
    base = f"https://rest.uniprot.org/uniprotkb/{UNIPROT_ACC}"
    jtxt = load_or_fetch("uniprot_Q00536.json", base + ".json", headers=HEADERS_JSON)
    if not jtxt:
        record_provenance("UniProt", base, UNIPROT_ACC, None, "FAILED")
        return None
    rec = json.loads(jtxt)

    fasta = load_or_fetch("uniprot_Q00536.fasta", base + ".fasta", headers=HEADERS_FASTA)
    seq = rec.get("sequence", {}).get("value", "")
    if fasta:
        seq_lines = fasta.splitlines()
        seq = "".join(seq_lines[1:]) if len(seq_lines) > 1 else seq

    # release version
    ver = None
    rv = fetch("https://rest.uniprot.org/uniprotkb/search",
               headers=HEADERS_JSON,
               params={"query": f"accession:{UNIPROT_ACC}", "fields": "accession", "format": "json"})
    if rv is not None:
        entry_audit = rec.get("entryAudit", {})
        ver = entry_audit.get("lastSequenceUpdateDate") or entry_audit.get("entryVersion")

    record_provenance("UniProt", base, UNIPROT_ACC, f"entry v{rec.get('entryAudit', {}).get('entryVersion', '?')}",
                      "OK", len(rec.get("features", [])))
    log.info("UniProt OK: %s aa, %d features", len(seq), len(rec.get("features", [])))
    return {"record": rec, "sequence": seq, "fasta": fasta or ""}


# --------------------------------------------------------------------------- #
# 2. NCBI Gene (E-utilities)
# --------------------------------------------------------------------------- #
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def fetch_ncbi_gene() -> dict | None:
    log.info("=== NCBI Gene %s ===", NCBI_GENE_ID)
    url = f"{EUTILS}/efetch.fcgi"
    params = {"db": "gene", "id": NCBI_GENE_ID, "retmode": "xml"}
    path = RAW / "ncbi_gene_5127.xml"
    text = None
    if path.exists() and path.stat().st_size > 0:
        text = path.read_text(encoding="utf-8")
    else:
        r = fetch(url, params=params)
        if r is not None:
            text = r.text
            save_raw("ncbi_gene_5127.xml", text)
    if not text:
        record_provenance("NCBI Gene", url, NCBI_GENE_ID, None, "FAILED")
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        log.error("NCBI gene XML parse error")
        record_provenance("NCBI Gene", url, NCBI_GENE_ID, None, "PARSE_ERROR")
        return None
    record_provenance("NCBI Gene", url, NCBI_GENE_ID, None, "OK")
    log.info("NCBI gene OK (%d bytes)", len(text))
    return {"xml_text": text}


# --------------------------------------------------------------------------- #
# 3. Ensembl gene / transcript / sequence
# --------------------------------------------------------------------------- #
def fetch_ensembl() -> dict | None:
    log.info("=== Ensembl %s ===", ENSEMBL_GENE)
    out: dict = {}
    gurl = f"https://rest.ensembl.org/lookup/id/{ENSEMBL_GENE}"
    gj = load_or_fetch("ensembl_gene.json", gurl, headers=HEADERS_JSON,
                       params={"expand": "1"})
    if gj:
        rec = json.loads(gj)
        out["gene"] = rec
        record_provenance("Ensembl", gurl, ENSEMBL_GENE,
                          rec.get("release", "?"), "OK", 1)
    # canonical transcript CDS/protein sequence (RefSeq accessions are not
    # accepted by /sequence/id without a fallback to the Ensembl transcript)
    turl = "https://rest.ensembl.org/sequence/id/NM_006201.5"
    ts = load_or_fetch("ensembl_NM006201_cds.json", turl, headers=HEADERS_JSON,
                       params={"type": "cds", "content-type": "application/json"})
    if not ts:
        # lookup the Ensembl transcript id for NM_006201.5, then fetch its CDS
        xl = fetch("https://rest.ensembl.org/xrefs/id/NM_006201.5",
                   headers=HEADERS_JSON, params={"content-type": "application/json"})
        if xl is not None:
            try:
                enst = next((x["id"] for x in xl.json()
                             if str(x.get("id", "")).startswith("ENST")), None)
            except ValueError:
                enst = None
            if enst:
                ts = load_or_fetch("ensembl_canonical_cds.json",
                                   f"https://rest.ensembl.org/sequence/id/{enst}",
                                   headers=HEADERS_JSON,
                                   params={"type": "cds", "content-type": "application/json"})
    if ts:
        out["canonical_cds"] = json.loads(ts)
        record_provenance("Ensembl", turl, "NM_006201.5", None, "OK", 1)
    else:
        record_provenance("Ensembl", turl, "NM_006201.5", None, "FAILED", 0)
    return out or None


# --------------------------------------------------------------------------- #
# 4. dbSNP rsIDs for CDK16 (E-utilities, db=snp)
# --------------------------------------------------------------------------- #
def fetch_dbsnp_ids() -> list[str]:
    log.info("=== dbSNP rsIDs for CDK16 ===")
    path = RAW / "dbsnp_rsids.json"
    if path.exists() and path.stat().st_size > 0:
        ids = json.loads(path.read_text())
        log.info("cache hit: %d rsIDs", len(ids))
        return ids
    url = f"{EUTILS}/esearch.fcgi"
    ids: list[str] = []
    retmax = 10000
    start = 0
    while True:
        params = {"db": "snp", "term": f"{NCBI_GENE_ID}[geneid]",
                  "retmax": retmax, "retstart": start, "retmode": "json"}
        r = fetch(url, params=params)
        if r is None:
            break
        data = r.json().get("esearchresult", {})
        batch = data.get("idlist", [])
        ids.extend(batch)
        count = int(data.get("count", "0"))
        start += retmax
        log.info("dbSNP esearch: %d/%d", len(ids), count)
        if not batch or start >= count:
            break
        time.sleep(0.5)
    save_raw("dbsnp_rsids.json", json.dumps(ids))
    record_provenance("dbSNP", url, f"{NCBI_GENE_ID}[geneid]", None,
                      "OK" if ids else "EMPTY", len(ids))
    log.info("dbSNP: %d rsIDs collected", len(ids))
    return ids


# --------------------------------------------------------------------------- #
# 5. Ensembl VEP on rsIDs (consequences + SIFT/PolyPhen)
# --------------------------------------------------------------------------- #
def fetch_vep(rsids: list[str], batch_size: int = 200) -> dict:
    log.info("=== Ensembl VEP for %d rsIDs ===", len(rsids))
    path = RAW / "vep_results.json"
    if path.exists() and path.stat().st_size > 0:
        results = json.loads(path.read_text())
        log.info("cache hit: %d VEP results", len(results))
        return results
    url = "https://rest.ensembl.org/vep/human/id"
    results: dict = {}
    total = (len(rsids) + batch_size - 1) // batch_size
    ok_batches = 0
    for i in range(0, len(rsids), batch_size):
        batch = rsids[i:i + batch_size]
        # VEP /vep/human/id expects identifiers WITH the "rs" prefix
        body_ids = [rid if str(rid).startswith("rs") else f"rs{rid}" for rid in batch]
        def vep_call(ids):
            return fetch(url, method="POST", body={"ids": ids},
                         headers={**HEADERS_JSON, "Content-Type": "application/json"},
                         params={"hgvs": "1", "protein": "1", "numbers": "1",
                                 "canonical": "1", "mane": "1", "pick": "0"},
                         timeout=90, tries=2, sleep_on_retry=5.0)

        r = vep_call(body_ids)
        if r is None and len(body_ids) > 25:
            # degrade gracefully: bisect the batch to isolate bad IDs
            collected = []
            mid = len(body_ids) // 2
            for half in (body_ids[:mid], body_ids[mid:]):
                if not half:
                    continue
                rh = vep_call(half)
                if rh is not None:
                    collected.append(rh)
                elif len(half) > 10:
                    for k in range(0, len(half), 10):
                        rk = vep_call(half[k:k + 10])
                        if rk is not None:
                            collected.append(rk)
                        else:
                            log.warning("VEP: dropping unresolvable IDs %s..%s",
                                        half[k], half[min(k + 9, len(half) - 1)])
                        time.sleep(0.6)
            if collected:
                arr_list = []
                for rh in collected:
                    try:
                        arr_list.extend(rh.json())
                    except ValueError:
                        pass
                r = None
                arr = arr_list
        if r is not None:
            try:
                arr = r.json()
            except ValueError:
                log.error("VEP batch non-JSON response at offset %d", i)
                continue
        for item in arr:
            rid = item.get("id", "").replace("rs", "")
            results[rid] = item
        ok_batches += 1
        log.info("VEP %d/%d batches done (%d variants)", (i // batch_size) + 1, total, len(results))
        time.sleep(1.2)
    save_raw("vep_results.json", json.dumps(results))
    record_provenance("Ensembl VEP", url, "CDK16 rsID set", None,
                      "OK" if ok_batches else "FAILED", len(results))
    return results


# --------------------------------------------------------------------------- #
# 6. RCSB PDB structures
# --------------------------------------------------------------------------- #
def fetch_pdb() -> dict | None:
    log.info("=== RCSB PDB search ===")
    meta_path = RAW / "pdb_structures.json"
    if meta_path.exists() and meta_path.stat().st_size > 0:
        return json.loads(meta_path.read_text())
    url = "https://search.rcsb.org/rcsbsearch/v2/query"
    query = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": UNIPROT_ACC,
            },
        },
        "request_options": {"scoring_strategy": "combined", "paginate": {"start": 0, "rows": 50}},
        "return_type": "polymer_instance",
    }
    r = fetch(url, method="POST", body=query,
              headers={**HEADERS_JSON, "Content-Type": "application/json"})
    if r is None:
        record_provenance("RCSB PDB", url, UNIPROT_ACC, None, "FAILED")
        return None
    hits = r.json().get("result_set", [])
    pdb_ids = sorted({h["identifier"].split(".")[0] for h in hits})
    log.info("PDB hits: %s", pdb_ids)

    structures = []
    for pid in pdb_ids:
        jurl = f"https://data.rcsb.org/rest/v1/core/entry/{pid}"
        rj = fetch(jurl, headers=HEADERS_JSON)
        if rj is None:
            continue
        entry = rj.json()
        # find the entity mapped to Q00536 and its chains
        chains = []
        for ent in entry.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", []):
            eurl = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pid}/{ent}"
            re_ = fetch(eurl, headers=HEADERS_JSON)
            if re_ is None:
                continue
            edata = re_.json()
            refs = (edata.get("rcsb_polymer_entity_container_identifiers", {})
                          .get("reference_sequence_identifiers", []))
            if any(x.get("database_accession") == UNIPROT_ACC for x in refs):
                chains = (edata.get("rcsb_polymer_entity_container_identifiers", {})
                               .get("asym_ids", []))
                seq_len = edata.get("entity_poly", {}).get("seq_length")
        method = (entry.get("exptl", [{}])[0].get("method", "?"))
        resolution = None
        for rc in entry.get("rcsb_entry_info", {}).get("resolution_combined", []) or []:
            resolution = rc
        ligands = []
        for cl in entry.get("rcsb_nonpolymer_entity_instance_container_identifiers", {})\
                       .get("non_polymer_instance_ids", []) or []:
            ligands.append(cl)
        title = entry.get("struct", {}).get("title", "")
        dep_date = entry.get("rcsb_accession_info", {}).get("deposit_date", "")
        structures.append({
            "pdb_id": pid, "method": method, "resolution_A": resolution,
            "chains": chains, "title": title, "deposit_date": dep_date,
            "uniprot_entity_chains": chains,
        })
        # download PDB/mmCIF file for viewer
        fdir = ROOT / "data" / "structures"
        fdir.mkdir(parents=True, exist_ok=True)
        fpath = fdir / f"{pid}.cif"
        if not fpath.exists():
            fr = fetch(f"https://files.rcsb.org/download/{pid}.cif", timeout=90)
            if fr is not None:
                fpath.write_text(fr.text, encoding="utf-8")
        time.sleep(0.4)
    save_raw("pdb_structures.json", json.dumps(structures, indent=2))
    record_provenance("RCSB PDB", url, UNIPROT_ACC, None, "OK", len(structures))
    return {"structures": structures}


# --------------------------------------------------------------------------- #
# 7. AlphaFold model
# --------------------------------------------------------------------------- #
def fetch_alphafold() -> dict | None:
    log.info("=== AlphaFold AF-Q00536-F1 ===")
    pid = f"AF-{UNIPROT_ACC}-F1"
    fdir = ROOT / "data" / "structures"
    fdir.mkdir(parents=True, exist_ok=True)
    cif = fdir / f"{pid}.cif"
    if not cif.exists():
        # resolve the current model version via the AlphaFold DB API
        api = f"https://alphafold.ebi.ac.uk/api/prediction/{UNIPROT_ACC}"
        version = "latest"
        cif_url = None
        r = fetch(api, timeout=60, tries=3)
        if r is not None:
            try:
                rec = r.json()[0]
                cif_url = rec.get("cifUrl")
                version = f"v{rec.get('latestVersion', '?')}"
            except Exception:
                cif_url = None
        if not cif_url:
            cif_url = f"https://alphafold.ebi.ac.uk/files/{pid}-model_v4.cif"
        r2 = fetch(cif_url, timeout=120, tries=3)
        if r2 is None:
            record_provenance("AlphaFold DB", cif_url, pid, version, "FAILED")
            return None
        cif.write_text(r2.text, encoding="utf-8")
    record_provenance("AlphaFold DB", "https://alphafold.ebi.ac.uk/api/prediction/" + UNIPROT_ACC,
                      pid, "latest", "OK", 1)
    return {"alphafold_id": pid, "file": str(cif)}


# --------------------------------------------------------------------------- #
# 8. AlphaMissense per-protein scores (attempted; recorded if unavailable)
# --------------------------------------------------------------------------- #
def fetch_alphamissense() -> dict | None:
    log.info("=== AlphaMissense (Swiss-Model per-protein) ===")
    url = f"https://swissmodel.expasy.org/alphamissense/{UNIPROT_ACC}.csv"
    r = fetch(url, timeout=120, tries=2)
    if r is None:
        record_provenance("AlphaMissense (Swiss-Model)", url, UNIPROT_ACC, None, "UNAVAILABLE")
        log.warning("AlphaMissense per-protein CSV unavailable — will be documented as a gap")
        return None
    path = RAW / "alphamissense_Q00536.csv"
    path.write_text(r.text, encoding="utf-8")
    n = len(r.text.splitlines()) - 1
    record_provenance("AlphaMissense (Swiss-Model)", url, UNIPROT_ACC, None, "OK", n)
    log.info("AlphaMissense: %d rows", n)
    return {"file": str(path), "rows": n}


# --------------------------------------------------------------------------- #
# 9. PubMed literature (E-utilities)
# --------------------------------------------------------------------------- #
PUBMED_QUERIES = [
    "CDK16 variant", "CDK16 mutation", "CDK16 kinase", "PCTAIRE1",
    "PCTAIRE1 mutation", "CDK16 cyclin Y", "CDK16 14-3-3", "PCTK1 kinase",
    "CDK16 phosphorylation", "CDK16 protein structure",
]

def fetch_pubmed() -> list[dict]:
    log.info("=== PubMed literature ===")
    path = RAW / "pubmed_articles.json"
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text())
    pmids: set[str] = set()
    for q in PUBMED_QUERIES:
        r = fetch(f"{EUTILS}/esearch.fcgi", params={
            "db": "pubmed", "term": q, "retmax": 60, "retmode": "json"})
        if r is None:
            continue
        got = r.json().get("esearchresult", {}).get("idlist", [])
        pmids.update(got)
        time.sleep(0.4)
    pmids = sorted(pmids)
    log.info("PubMed: %d unique PMIDs", len(pmids))
    articles = []
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        r = fetch(f"{EUTILS}/esummary.fcgi", params={
            "db": "pubmed", "id": ",".join(chunk), "retmode": "json"})
        if r is None:
            continue
        res = r.json().get("result", {})
        for pid in chunk:
            doc = res.get(pid)
            if doc:
                articles.append({
                    "pmid": pid,
                    "title": doc.get("title", ""),
                    "journal": doc.get("source", ""),
                    "pubdate": doc.get("pubdate", ""),
                    "authors": [a.get("name", "") for a in doc.get("authors", [])[:6]],
                    "query_hits": [q for q in PUBMED_QUERIES],
                })
        time.sleep(0.5)
    save_raw("pubmed_articles.json", json.dumps(articles, indent=1))
    record_provenance("PubMed", f"{EUTILS}/esearch.fcgi", "CDK16 queries", None,
                      "OK" if articles else "EMPTY", len(articles))
    return articles


# --------------------------------------------------------------------------- #
# 10. ClinVar (recorded even when empty)
# --------------------------------------------------------------------------- #
def fetch_clinvar() -> dict:
    log.info("=== ClinVar ===")
    url = f"{EUTILS}/esearch.fcgi"
    r = fetch(url, params={"db": "clinvar", "term": f"{NCBI_GENE_ID}[geneid]",
                           "retmax": 200, "retmode": "json"})
    ids = []
    if r is not None:
        ids = r.json().get("esearchresult", {}).get("idlist", [])
    record_provenance("ClinVar", url, f"{NCBI_GENE_ID}[geneid]", None,
                      "OK" if ids is not None else "FAILED", len(ids))
    log.info("ClinVar: %d submissions for gene %s", len(ids), NCBI_GENE_ID)
    (RAW / "clinvar_ids.json").write_text(json.dumps(ids, indent=1), encoding="utf-8")
    return {"clinvar_ids": ids}


# --------------------------------------------------------------------------- #
# 11. Homologs for conservation (UniProt orthologs)
# --------------------------------------------------------------------------- #
HOMOLOG_QUERIES = [
    ("Mouse", "gene:CDK16 AND organism_id:10090 AND reviewed:true"),
    ("Rat", "gene:CDK16 AND organism_id:10116 AND reviewed:true"),
    ("Dog", "gene:CDK16 AND organism_id:9615 AND reviewed:true"),
    ("Chicken", "gene:CDK16 AND organism_id:9031 AND reviewed:true"),
    ("Zebrafish", "gene:CDK16 AND organism_id:7955 AND reviewed:true"),
    ("African clawed frog", "gene:cdk16 AND organism_id:8355 AND reviewed:true"),
]

def fetch_homologs() -> list[dict]:
    log.info("=== UniProt homologs ===")
    path = RAW / "homologs.json"
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text())
    homologs = []
    for species, query in HOMOLOG_QUERIES:
        r = fetch("https://rest.uniprot.org/uniprotkb/search", headers=HEADERS_JSON,
                  params={"query": query, "format": "json", "fields": "accession,id,protein_name,organism_name,sequence", "size": "1"})
        if r is None:
            continue
        res = r.json().get("results", [])
        if not res:
            log.warning("no reviewed homolog for %s", species)
            continue
        e = res[0]
        acc = e["primaryAccession"]
        seq = e.get("sequence", {}).get("value", "")
        homologs.append({"species": species, "accession": acc,
                         "name": e.get("proteinDescription", {}).get("recommendedName", {})
                                        .get("fullName", {}).get("value", acc),
                         "organism": e.get("organism", {}).get("scientificName", species),
                         "sequence": seq})
        time.sleep(0.4)
    save_raw("homologs.json", json.dumps(homologs, indent=1))
    record_provenance("UniProt (homologs)", "https://rest.uniprot.org/uniprotkb/search",
                      "CDK16 orthologs", None, "OK", len(homologs))
    return homologs


# --------------------------------------------------------------------------- #
# 12. UniProt interactions (cross-references + comment INTERACTION)
# --------------------------------------------------------------------------- #
def extract_interactions(uniprot_rec: dict) -> list[dict]:
    out = []
    for c in uniprot_rec.get("comments", []):
        if c.get("commentType") == "INTERACTION":
            for it in c.get("interactions", []):
                partner = it.get("interactantTwo", {})
                out.append({
                    "partner": partner.get("shortName") or partner.get("accession", "?"),
                    "partner_accession": partner.get("accession", ""),
                    "experiments": it.get("experiments", 0),
                    "type": "experimental" if it.get("experiments", 0) > 0 else "predicted",
                })
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    t0 = time.time()
    RAW.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "structures").mkdir(parents=True, exist_ok=True)

    up = fetch_uniprot()
    if up is None:
        log.critical("UniProt failed — cannot build reference; aborting")
        sys.exit(1)
    seq = up["sequence"]
    log.info("canonical sequence length: %d aa", len(seq))

    fetch_ncbi_gene()
    fetch_ensembl()
    rsids = fetch_dbsnp_ids()
    if rsids:
        fetch_vep(rsids)
    fetch_pdb()
    fetch_alphafold()
    fetch_alphamissense()
    fetch_pubmed()
    fetch_clinvar()
    fetch_homologs()

    manifest = {
        "generated_at": stamp(),
        "uniprot_accession": UNIPROT_ACC,
        "ncbi_gene": NCBI_GENE_ID,
        "ensembl_gene": ENSEMBL_GENE,
        "sequence_length": len(seq),
        "n_rsids": len(rsids),
        "elapsed_s": round(time.time() - t0, 1),
    }
    (RAW / "acquisition_manifest.json").write_text(json.dumps(manifest, indent=2))

    with open(RAW / "data_provenance.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["source_database", "source_url", "retrieval_timestamp",
                                           "database_version", "record_id", "status", "n_records"])
        w.writeheader()
        w.writerows(PROVENANCE)

    log.info("=== acquisition complete in %.1fs ===", time.time() - t0)


if __name__ == "__main__":
    main()
