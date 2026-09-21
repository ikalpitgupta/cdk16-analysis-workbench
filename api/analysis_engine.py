"""CDK16 Analysis Engine.

Persistent analysis jobs (SQLite) executed in background threads with
stage-based progress. Produces an AnalysisResult that is the single source of
truth for both the frontend and report generation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
DB_PATH = DATA / "analysis_sessions.db"
DATASET = DATA / "cdk16_variants_master.csv"
DATASET2 = DATA / "cdk16_variants_master.parquet"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("analysis")

STAGES = [
    "validating", "loading_data", "filtering_variants", "clinical",
    "conservation", "predictions", "structure", "evidence", "ranking",
    "storing_results",
]

CONSTRAINT_KEYS = {
    "variant_type": (list, str),        # e.g. ["missense"]
    "domain": (list, str),              # e.g. ["Kinase domain"] or ["all"]
    "min_conservation": (int, float),   # 0..1
    "am_class": (list, str),            # e.g. ["pathogenic", "likely_pathogenic"]
    "min_am_score": (int, float),       # 0..1
    "landmark": (list, str),            # active_site / binding_site / ...
    "max_frequency": (int, float),      # 0..1 (None/absent = no constraint)
    "min_priority": (int, float),       # 0..100
    "limit": (int,),                    # max rows stored (cap for perf)
}

VALID_VARIANT_TYPES = {"missense", "synonymous", "nonsense", "frameshift",
                       "splice", "start_lost", "stop_lost", "other"}

VALID_AM_CLASSES = {"pathogenic", "likely_pathogenic", "ambiguous",
                    "likely_benign", "benign"}

VALID_LANDMARKS = {"active_site", "binding_site", "modified_residue", "none"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def constraint_hash(constraints: dict) -> str:
    canon = json.dumps(constraints, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def validate_constraints(c: dict) -> tuple[dict, list[str]]:
    """Validate and coerce the analysis configuration. Returns (clean, errors)."""
    errors: list[str] = []
    clean: dict = {}
    for key, value in (c or {}).items():
        if key not in CONSTRAINT_KEYS:
            errors.append(f"Unknown constraint: {key}")
            continue
        types = CONSTRAINT_KEYS[key]
        if list in types:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                errors.append(f"{key} must be a list of strings")
                continue
            clean[key] = value
        elif int in types or float in types:
            if not isinstance(value, (int, float)):
                errors.append(f"{key} must be a number")
                continue
            clean[key] = float(value)
        else:  # pragma: no cover
            errors.append(f"{key} has unsupported type spec")
    # semantic validation
    vt = clean.get("variant_type", [])
    bad = [t for t in vt if t not in VALID_VARIANT_TYPES and t != "all"]
    if bad:
        errors.append(f"Unknown variant types: {bad}")
    amc = clean.get("am_class", [])
    bad = [a for a in amc if a not in VALID_AM_CLASSES]
    if bad:
        errors.append(f"Unknown AM classes: {bad}")
    lm = clean.get("landmark", [])
    bad = [l for l in lm if l not in VALID_LANDMARKS]
    if bad:
        errors.append(f"Unknown landmarks: {bad}")
    if "min_conservation" in clean and not (0 <= clean["min_conservation"] <= 1):
        errors.append("min_conservation must be within [0, 1]")
    if "min_am_score" in clean and not (0 <= clean["min_am_score"] <= 1):
        errors.append("min_am_score must be within [0, 1]")
    if "max_frequency" in clean and not (0 < clean["max_frequency"] <= 1):
        errors.append("max_frequency must be within (0, 1]")
    if "min_priority" in clean and not (0 <= clean["min_priority"] <= 100):
        errors.append("min_priority must be within [0, 100]")
    if "limit" in clean and not (1 <= clean["limit"] <= 20000):
        errors.append("limit must be within [1, 20000]")
    return clean, errors


def default_constraints() -> dict:
    return {"variant_type": ["missense"], "domain": ["all"],
            "min_conservation": 0.0, "min_am_score": 0.0, "limit": 5000}


class AnalysisEngine:
    """SQLite-backed analysis sessions with background execution."""

    def __init__(self) -> None:
        DATA.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._init_db()

    # ------------------------------------------------------------------ db
    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(DB_PATH, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        with self._lock:
            c = self.conn
            # Drop incompatible legacy schema if present (fresh install only:
            # this project was recovered from a wiped disk, no legacy data kept)
            tables = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            legacy = {"analysis_sessions", "analysis_runs", "analysis_reports",
                      "analysis_results"} & tables
            for t in legacy:
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()}
                if t == "analysis_sessions" and "name" not in cols:
                    c.execute(f"DROP TABLE {t}")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'CREATED',
                constraints_json TEXT NOT NULL,
                constraint_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                run_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                stage TEXT DEFAULT '',
                message TEXT DEFAULT '',
                constraint_hash TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
            );
            CREATE TABLE IF NOT EXISTS analysis_results (
                session_id TEXT PRIMARY KEY,
                run_number INTEGER NOT NULL,
                constraint_hash TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
            );
            CREATE TABLE IF NOT EXISTS analysis_reports (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                run_number INTEGER NOT NULL,
                section TEXT NOT NULL,
                version INTEGER NOT NULL,
                constraint_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'CURRENT',
                format TEXT NOT NULL DEFAULT 'html',
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
            );
            """)
            c.commit()

    # ------------------------------------------------------------ sessions
    def create_session(self, name: str, description: str = "",
                       constraints: dict | None = None) -> dict:
        clean, errors = validate_constraints(constraints or default_constraints())
        if errors:
            raise ValueError("; ".join(errors))
        sid = "A-" + hashlib.sha1(f"{name}{utcnow()}{time.time_ns()}".encode()).hexdigest()[:12]
        now = utcnow()
        with self._lock:
            self.conn.execute(
                "INSERT INTO analysis_sessions (id, name, description, status,"
                " constraints_json, constraint_hash, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (sid, name, description, "CREATED", json.dumps(clean),
                 constraint_hash(clean), now, now))
            self.conn.commit()
        log.info("session created: %s (%s)", sid, name)
        return self.get_session(sid)

    def get_session(self, sid: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM analysis_sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        runs = [dict(r) for r in self.conn.execute(
            "SELECT * FROM analysis_runs WHERE session_id=? ORDER BY run_number",
            (sid,)).fetchall()]
        reports = [dict(r) for r in self.conn.execute(
            "SELECT * FROM analysis_reports WHERE session_id=? ORDER BY created_at",
            (sid,)).fetchall()]
        s = dict(row)
        s["constraints"] = json.loads(s.pop("constraints_json"))
        s["runs"] = runs
        s["reports"] = reports
        return s

    def list_sessions(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM analysis_sessions ORDER BY created_at DESC").fetchall()
        out = []
        for row in rows:
            s = dict(row)
            s["constraints"] = json.loads(s.pop("constraints_json"))
            n = self.conn.execute(
                "SELECT COUNT(*) FROM analysis_results WHERE session_id=?",
                (s["id"],)).fetchone()[0]
            s["has_results"] = n > 0
            out.append(s)
        return out

    def update_constraints(self, sid: str, constraints: dict) -> dict:
        sess = self.get_session(sid)
        if not sess:
            raise KeyError(sid)
        clean, errors = validate_constraints(constraints)
        if errors:
            raise ValueError("; ".join(errors))
        new_hash = constraint_hash(clean)
        with self._lock:
            self.conn.execute(
                "UPDATE analysis_sessions SET constraints_json=?, constraint_hash=?,"
                " status=CASE WHEN ? != constraint_hash THEN 'OUTDATED' ELSE status END,"
                " updated_at=? WHERE id=?",
                (json.dumps(clean), new_hash, new_hash, utcnow(), sid))
            self.conn.commit()
        return self.get_session(sid)

    def delete_session(self, sid: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM analysis_sessions WHERE id=?", (sid,))
            self.conn.execute("DELETE FROM analysis_runs WHERE session_id=?", (sid,))
            self.conn.execute("DELETE FROM analysis_results WHERE session_id=?", (sid,))
            self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------------- run
    def run(self, sid: str) -> dict:
        """Queue a run; execution continues in a daemon thread."""
        sess = self.get_session(sid)
        if not sess:
            raise KeyError(sid)
        if sess["status"] == "RUNNING":
            return {"analysis_id": sid, "status": "RUNNING",
                    "message": "analysis already running"}
        run_number = (sess["runs"][-1]["run_number"] + 1) if sess["runs"] else 1
        now = utcnow()
        with self._lock:
            self.conn.execute(
                "INSERT INTO analysis_runs (session_id, run_number, status,"
                " constraint_hash, started_at) VALUES (?,?,?,?,?)",
                (sid, run_number, "RUNNING", sess["constraint_hash"], now))
            self.conn.execute(
                "UPDATE analysis_sessions SET status='RUNNING', updated_at=? WHERE id=?",
                (now, sid))
            self.conn.commit()
        t = threading.Thread(target=self._execute, args=(sid, run_number), daemon=True)
        t.start()
        return {"analysis_id": sid, "run_number": run_number,
                "status": "RUNNING", "message": "analysis started"}

    def _set_stage(self, sid: str, run_number: int, stage: str, message: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE analysis_runs SET stage=?, message=? WHERE session_id=?"
                " AND run_number=?", (stage, message, sid, run_number))
            self.conn.commit()

    def _fail(self, sid: str, run_number: int, err: str) -> None:
        log.error("analysis %s run %d failed: %s", sid, run_number, err)
        with self._lock:
            self.conn.execute(
                "UPDATE analysis_runs SET status='FAILED', error=?, completed_at=?"
                " WHERE session_id=? AND run_number=?",
                (err[:2000], utcnow(), sid, run_number))
            self.conn.execute(
                "UPDATE analysis_sessions SET status='FAILED', updated_at=? WHERE id=?",
                (utcnow(), sid))
            self.conn.commit()

    # ----------------------------------------------------------- pipeline
    def _load_variants(self) -> pd.DataFrame:
        if DATASET2.exists():
            return pd.read_parquet(DATASET2)
        if DATASET.exists():
            return pd.read_csv(DATASET, low_memory=False)
        raise FileNotFoundError(
            "Processed variant dataset not found — run the integration pipeline first")

    def _execute(self, sid: str, run_number: int) -> None:
        try:
            sess = self.get_session(sid)
            cons = sess["constraints"]

            self._set_stage(sid, run_number, "validating", "Validating configuration")
            clean, errors = validate_constraints(cons)
            if errors:
                raise ValueError("; ".join(errors))

            self._set_stage(sid, run_number, "loading_data",
                            "Loading CDK16 processed dataset")
            df = self._load_variants()
            n_available = int(len(df))

            self._set_stage(sid, run_number, "filtering_variants",
                            "Applying variant constraints")
            mask = pd.Series(True, index=df.index)
            vt = cons.get("variant_type") or []
            if vt and "all" not in vt:
                mask &= df["variant_class"].astype(str).str.lower().isin(vt)

            self._set_stage(sid, run_number, "clinical",
                            "Processing clinical annotations")
            # (clinical filters apply only when ClinVar-mapped rows exist)

            self._set_stage(sid, run_number, "conservation",
                            "Applying conservation thresholds")
            if cons.get("min_conservation", 0) > 0 and "conservation_score" in df.columns:
                mask &= pd.to_numeric(df["conservation_score"], errors="coerce")\
                          .ge(cons["min_conservation"])

            self._set_stage(sid, run_number, "predictions",
                            "Filtering computational predictions")
            amc = cons.get("am_class") or []
            if amc and "am_pathogenicity_class" in df.columns:
                mask &= df["am_pathogenicity_class"].astype(str).str.lower().isin(amc)
            if cons.get("min_am_score", 0) > 0 and "am_pathogenicity_score" in df.columns:
                mask &= pd.to_numeric(df["am_pathogenicity_score"], errors="coerce")\
                          .ge(cons["min_am_score"])

            self._set_stage(sid, run_number, "structure",
                            "Filtering structural mappings")
            lm = cons.get("landmark") or []
            if lm and "landmark_type" in df.columns:
                lmask = df["landmark_type"].astype(str).str.lower().isin(lm)
                if "none" in lm:
                    lmask = lmask | (df["landmark_type"].isna()) | \
                            (df["landmark_type"].astype(str).str.lower() == "none")
                mask &= lmask

            self._set_stage(sid, run_number, "evidence",
                            "Integrating evidence dimensions")
            if "domain_name" in df.columns:
                dom = cons.get("domain") or []
                if dom and "all" not in dom:
                    dom_names = df["domain_name"].astype(str)
                    dmask = pd.Series(False, index=df.index)
                    no_domain = df["domain_name"].isna() | \
                                dom_names.isin(["None", "none", "", "nan"])
                    for d in dom:
                        dl = str(d).lower().strip()
                        if dl in ("none", "outside", "outside_annotated_domains"):
                            dmask |= no_domain
                        else:
                            dmask |= dom_names.str.lower().str.contains(dl, regex=False)
                    mask &= dmask
            if cons.get("min_priority", 0) > 0 and "priority_score" in df.columns:
                mask &= pd.to_numeric(df["priority_score"], errors="coerce")\
                          .ge(cons["min_priority"])

            sel = df[mask].copy()
            if "priority_score" in sel.columns:
                sel = sel.sort_values("priority_score", ascending=False)
            limit = int(cons.get("limit", 5000))
            matched = int(len(sel))
            sel = sel.head(limit)

            self._set_stage(sid, run_number, "ranking",
                            "Ranking variants by integrated evidence")
            top = sel.head(20)

            self._set_stage(sid, run_number, "storing_results",
                            "Storing analysis results")
            cols = [c for c in ("variant_uid", "aa_change", "protein_position",
                                "variant_class", "rsid", "domain_name", "landmark_type",
                                "am_pathogenicity_score", "am_pathogenicity_class",
                                "conservation_score", "priority_score") if c in sel.columns]
            result = {
                "analysis_id": sid,
                "run_number": run_number,
                "constraint_hash": sess["constraint_hash"],
                "constraints": cons,
                "generated_at": utcnow(),
                "summary": {
                    "n_available": n_available,
                    "n_matched": matched,
                    "n_returned": int(len(sel)),
                    "n_truncated": matched > len(sel),
                    "zero_results": matched == 0,
                },
                "statistics": {
                    "by_class": self._value_counts(sel, "variant_class", fill="unknown", lower=True),
                    "by_domain": self._value_counts(sel, "domain_name", fill="No domain"),
                    "by_am_class": self._value_counts(sel, "am_pathogenicity_class", fill="unknown"),
                    "landmark_counts": self._value_counts(sel, "landmark_type", fill="none"),
                },
                "variants": sel[cols].to_dict(orient="records"),
                "top_variants": top[cols].to_dict(orient="records"),
                "warnings": self._warnings(cons, matched),
            }
            blob = json.dumps(result, ensure_ascii=False)
            with self._lock:
                self.conn.execute(
                    "INSERT INTO analysis_results (session_id, run_number,"
                    " constraint_hash, result_json, created_at) VALUES (?,?,?,?,?)"
                    " ON CONFLICT(session_id) DO UPDATE SET run_number=excluded.run_number,"
                    " constraint_hash=excluded.constraint_hash,"
                    " result_json=excluded.result_json, created_at=excluded.created_at",
                    (sid, run_number, sess["constraint_hash"], blob, utcnow()))
                self.conn.execute(
                    "UPDATE analysis_runs SET status='COMPLETED', stage='completed',"
                    " message=?, completed_at=? WHERE session_id=? AND run_number=?",
                    (f"{matched} variants matched", utcnow(), sid, run_number))
                self.conn.execute(
                    "UPDATE analysis_sessions SET status='COMPLETED', updated_at=?"
                    " WHERE id=?", (utcnow(), sid))
                # reports generated from older runs become OUTDATED
                self.conn.execute(
                    "UPDATE analysis_reports SET status='OUTDATED' WHERE session_id=?"
                    " AND constraint_hash != ?", (sid, sess["constraint_hash"]))
                self.conn.commit()
            log.info("analysis %s run %d completed: %d matched", sid, run_number, matched)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            self._fail(sid, run_number, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")

    @staticmethod
    def _value_counts(sel, col: str, fill: str = "unknown",
                      lower: bool = False) -> dict[str, int]:
        """Counter over a column with nulls made explicit (never the string
        'nan' from pandas astype(str)) — NaN becomes the provided category."""
        if col not in sel.columns or len(sel) == 0:
            return {}
        s = sel[col]
        s = s.where(s.notna(), fill).astype(str)
        if lower:
            s = s.str.lower()
        return dict(Counter(s))

    @staticmethod
    def _warnings(cons: dict, matched: int) -> list[str]:
        w: list[str] = []
        if 0 < matched < 10:
            w.append("Only %d variants match the selected criteria. "
                     "Statistical interpretation may be limited." % matched)
        if matched == 0:
            w.append("No variants matched the current analysis constraints. "
                     "Relax a filter to explore the dataset.")
        if cons.get("min_conservation", 0) >= 0.9:
            w.append("A conservation threshold of ≥ 0.9 is highly restrictive.")
        return w

    # ------------------------------------------------------------- results
    def get_results(self, sid: str) -> dict | None:
        row = self.conn.execute(
            "SELECT result_json FROM analysis_results WHERE session_id=?",
            (sid,)).fetchone()
        return json.loads(row[0]) if row else None
