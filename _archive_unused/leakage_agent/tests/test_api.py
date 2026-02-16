import pytest
import pandas as pd
from leakage_agent.api import LeakageValidator, ValidationResult

@pytest.fixture
def validator():
    return LeakageValidator(policy_dir="policy/versions/v1")

def test_api_accepts_valid_data(validator):
    """Test that valid data is accepted via API."""
    data = {
        "email_address": ["test@example.com"],
        "amount": [100.0],
        "label": ["cat"]
    }
    df = pd.DataFrame(data)
    
    result = validator.validate(df)
    
    assert result.is_accepted
    assert not result.is_rejected
    assert not result.is_quarantined
    assert result.decision == "ACCEPT"
    assert len(result.reason_codes) == 0

def test_api_rejects_invalid_data(validator):
    """Test that data with missing label is rejected."""
    data = {
        "email_address": ["test@example.com"],
        "amount": [100.0],
        "label": [None]  # Missing critical field
    }
    df = pd.DataFrame(data)
    
    result = validator.validate(df)
    
    assert result.is_rejected
    assert not result.is_accepted
    assert "MISSING_TOO_HIGH" in result.reason_codes

def test_api_quarantines_secrets(validator):
    """Test that data with secrets is quarantined."""
    data = {
        "secret_key": ["my-secret-token"],
        "label": ["cat"]
    }
    df = pd.DataFrame(data)
    
    result = validator.validate(df)
    
    assert result.is_quarantined
    assert not result.is_accepted
    assert "SECRET_FOUND" in result.reason_codes

def test_api_auto_generates_copy_id(validator):
    """Test that copy_id is auto-generated if not provided."""
    data = {"label": ["cat"]}
    df = pd.DataFrame(data)
    
    result = validator.validate(df)
    
    assert "copy_id" in result.transform_summary
    assert result.transform_summary["copy_id"].startswith("auto_")

def test_api_uses_provided_copy_id(validator):
    """Test that provided copy_id is used."""
    data = {"label": ["cat"]}
    df = pd.DataFrame(data)
    
    result = validator.validate(df, copy_id="custom_123")
    
    assert result.transform_summary["copy_id"] == "custom_123"

def test_api_batch_validation(validator):
    """Test batch validation of multiple DataFrames."""
    dfs = {
        "batch_1": pd.DataFrame({"label": ["cat"]}),
        "batch_2": pd.DataFrame({"label": ["dog"]}),
    }
    
    results = validator.validate_batch(dfs)
    
    assert len(results) == 2
    assert "batch_1" in results
    assert "batch_2" in results
    assert all(isinstance(r, ValidationResult) for r in results.values())

def test_api_batch_summary(validator):
    """Test summary statistics from batch results."""
    dfs = {
        "accept": pd.DataFrame({"label": ["cat"]}),
        "reject": pd.DataFrame({"label": [None]}),
        "quarantine": pd.DataFrame({"secret_key": ["xxx"], "label": ["cat"]}),
    }
    
    results = validator.validate_batch(dfs)
    summary = validator.get_summary(results)
    
    assert summary["total"] == 3
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["quarantined"] == 1
    assert summary["acceptance_rate"] == pytest.approx(33.33, rel=0.1)

def test_validation_result_to_dict(validator):
    """Test ValidationResult serialization."""
    data = {"label": ["cat"]}
    df = pd.DataFrame(data)
    
    result = validator.validate(df)
    result_dict = result.to_dict()
    
    assert "decision" in result_dict
    assert "reason_codes" in result_dict
    assert "metrics" in result_dict
    assert "transform_summary" in result_dict

def test_api_context_manager(validator):
    """Test context manager usage."""
    data = {"label": ["cat"]}
    df = pd.DataFrame(data)
    
    with LeakageValidator() as v:
        result = v.validate(df)
        assert result.is_accepted

def test_api_handles_empty_dataframe(validator):
    """Test handling of empty DataFrame."""
    df = pd.DataFrame()
    
    result = validator.validate(df)
    
    # Should reject due to missing critical fields
    assert result.is_rejected or result.decision == "REJECT"

def test_api_cleaned_data_structure(validator):
    """Test that cleaned data has expected structure."""
    data = {
        "email_address": ["test@example.com"],
        "full_name": ["John Doe"],  # Should be dropped
        "amount": [100.0],
        "label": ["cat"]
    }
    df = pd.DataFrame(data)
    
    result = validator.validate(df)
    
    assert result.is_accepted
    assert "email" in result.cleaned_data.columns  # Tokenized
    assert "name" not in result.cleaned_data.columns  # Dropped
    assert "label" in result.cleaned_data.columns  # Kept
