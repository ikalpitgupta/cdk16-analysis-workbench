import pytest
from api.analysis_engine import (
    AnalysisEngine,
    validate_constraints,
    constraint_hash,
    default_constraints,
    VALID_VARIANT_TYPES,
    VALID_AM_CLASSES,
    VALID_LANDMARKS,
)

def test_default_constraints():
    c = default_constraints()
    clean, errors = validate_constraints(c)
    assert errors == []
    assert clean["variant_type"] == ["missense"]
    assert clean["limit"] == 5000

def test_validate_constraints_valid():
    c = {
        "variant_type": ["missense", "nonsense"],
        "domain": ["kinase"],
        "min_conservation": 0.5,
        "am_class": ["pathogenic"],
        "min_am_score": 0.4,
        "landmark": ["active_site"],
        "max_frequency": 0.01,
        "min_priority": 30.0,
        "limit": 1000,
    }
    clean, errors = validate_constraints(c)
    assert errors == []
    assert clean["min_conservation"] == 0.5
    assert clean["limit"] == 1000

def test_validate_constraints_invalid():
    # Unknown key
    clean, errors = validate_constraints({"unknown_filter": 123})
    assert any("Unknown constraint" in e for e in errors)

    # Bad list type
    clean, errors = validate_constraints({"variant_type": "not_a_list"})
    assert any("must be a list of strings" in e for e in errors)

    # Bad numeric type
    clean, errors = validate_constraints({"min_conservation": "high"})
    assert any("must be a number" in e for e in errors)

    # Out of range values
    clean, errors = validate_constraints({"min_conservation": 1.5})
    assert any("min_conservation must be within [0, 1]" in e for e in errors)

    clean, errors = validate_constraints({"min_am_score": -0.1})
    assert any("min_am_score must be within [0, 1]" in e for e in errors)

    clean, errors = validate_constraints({"limit": 0})
    assert any("limit must be within [1, 20000]" in e for e in errors)

    clean, errors = validate_constraints({"limit": 50000})
    assert any("limit must be within [1, 20000]" in e for e in errors)

    clean, errors = validate_constraints({"variant_type": ["invalid_type"]})
    assert any("Unknown variant types" in e for e in errors)

    clean, errors = validate_constraints({"am_class": ["super_pathogenic"]})
    assert any("Unknown AM classes" in e for e in errors)

    clean, errors = validate_constraints({"landmark": ["unknown_site"]})
    assert any("Unknown landmarks" in e for e in errors)

def test_constraint_hash():
    c1 = {"variant_type": ["missense"], "min_conservation": 0.5}
    c2 = {"min_conservation": 0.5, "variant_type": ["missense"]}
    c3 = {"variant_type": ["synonymous"]}
    assert constraint_hash(c1) == constraint_hash(c2)
    assert constraint_hash(c1) != constraint_hash(c3)

def test_engine_warnings():
    w_few = AnalysisEngine._warnings({"min_conservation": 0.5}, 5)
    assert any("Only 5 variants match" in w for w in w_few)

    w_zero = AnalysisEngine._warnings({}, 0)
    assert any("No variants matched" in w for w in w_zero)

    w_restrictive = AnalysisEngine._warnings({"min_conservation": 0.95}, 20)
    assert any("restrictive" in w for w in w_restrictive)

def test_engine_value_counts():
    import pandas as pd
    df = pd.DataFrame({
        "cat": ["A", "B", "A", None, "nan"],
        "empty_col": [None, None, None, None, None]
    })
    counts = AnalysisEngine._value_counts(df, "cat", fill="missing", lower=True)
    assert counts["a"] == 2
    assert counts["b"] == 1
    assert counts["missing"] == 1

    assert AnalysisEngine._value_counts(df, "nonexistent") == {}
    assert AnalysisEngine._value_counts(pd.DataFrame(), "cat") == {}
