import pytest
import pandas as pd
from leakage_agent.pipeline import Pipeline
from leakage_agent.engine import validate_ranges, validate_enums, validate_schema

@pytest.fixture
def pipeline():
    return Pipeline(policy_dir="policy/versions/v1")

# Range validation tests
def test_range_violation_detected(pipeline):
    """Test that negative amounts are detected as range violations."""
    data = {
        "amount": [100, -50, 200],  # -50 violates range_min: 0
        "label": ["cat", "dog", "cat"]
    }
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    
    assert "amount" in report["metrics"]["range_violations_count_by_field"]
    assert report["metrics"]["range_violations_count_by_field"]["amount"] == 1
    assert report["decision"] == "REJECT"
    assert "OUT_OF_RANGE" in report["reason_codes"]

def test_range_exact_boundary_included(pipeline):
    """Test that exact boundary values (0 and 1000000) are valid."""
    data = {
        "amount": [0, 1000000, 500000],  # All valid
        "label": ["cat", "dog", "cat"]
    }
    df = pd.DataFrame(data)
    violations = validate_ranges(df, pipeline.config)
    
    assert "amount" not in violations  # No violations

def test_range_null_values_ignored(pipeline):
    """Test that null values don't count as range violations."""
    data = {
        "amount": [100, None, 200],  # None should be ignored
        "label": ["cat", "dog", "cat"]
    }
    df = pd.DataFrame(data)
    violations = validate_ranges(df, pipeline.config)
    
    assert "amount" not in violations

# Enum validation tests
def test_enum_violation_detected(pipeline):
    """Test that invalid gender values are detected."""
    data = {
        "gender": ["male", "alien", "female"],  # "alien" not in allowed_values
        "label": ["cat", "dog", "cat"]
    }
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    
    assert "gender" in report["metrics"]["enum_violations_count_by_field"]
    assert report["metrics"]["enum_violations_count_by_field"]["gender"] == 1
    assert report["decision"] == "REJECT"
    assert "ENUM_VIOLATION" in report["reason_codes"]

def test_enum_case_sensitive(pipeline):
    """Test that enum matching is case-sensitive."""
    data = {
        "gender": ["Male", "Female"],  # Should match lowercase allowed_values
        "label": ["cat", "dog"]
    }
    df = pd.DataFrame(data)
    violations = validate_enums(df, pipeline.config)
    
    # "Male" and "Female" are NOT in allowed_values (which are lowercase)
    assert "gender" in violations
    assert violations["gender"] == 2

def test_enum_null_values_ignored(pipeline):
    """Test that null values don't count as enum violations."""
    data = {
        "gender": ["male", None, "female"],  # None should be ignored
        "label": ["cat", "dog", "cat"]
    }
    df = pd.DataFrame(data)
    violations = validate_enums(df, pipeline.config)
    
    assert "gender" not in violations

# Schema validation tests
def test_schema_missing_critical_field(pipeline):
    """Test that missing critical field fails schema validation."""
    data = {
        "amount": [100, 200],
        # "label" is missing - critical field!
    }
    df = pd.DataFrame(data)
    schema_ok = validate_schema(df, pipeline.config)
    
    assert schema_ok == False

def test_schema_wrong_data_type(pipeline):
    """Test that wrong data type fails schema validation."""
    data = {
        "amount": ["not_a_number", "also_not_a_number"],  # Should be float!
        "label": ["cat", "dog"]
    }
    df = pd.DataFrame(data)
    schema_ok = validate_schema(df, pipeline.config)
    
    assert schema_ok == False

def test_schema_correct_types(pipeline):
    """Test that correct types pass schema validation."""
    data = {
        "amount": [100.5, 200.0],  # float
        "label": ["cat", "dog"]    # string
    }
    df = pd.DataFrame(data)
    schema_ok = validate_schema(df, pipeline.config)
    
    assert schema_ok == True
