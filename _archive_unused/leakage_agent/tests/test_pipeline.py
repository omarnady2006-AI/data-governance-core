import pytest
import pandas as pd
from leakage_agent.pipeline import Pipeline

@pytest.fixture
def pipeline():
    return Pipeline(policy_dir="policy/versions/v1")

def test_pii_tokenization_changes_email(pipeline):
    # email is in policy to be TOKENIZE_DET
    data = {"email": ["alice@example.com"], "label": ["cat"], "amount": [100]}
    df = pd.DataFrame(data)
    df_out, report = pipeline.run(df)
    assert report["decision"] == "ACCEPT"
    assert df_out["email"].iloc[0].startswith("tok_")
    assert df_out["email"].iloc[0] != "alice@example.com"

def test_secrets_to_quarantine(pipeline):
    # secret_key is in forbidden.yaml
    data = {"secret_key": ["my-secret-token"], "label": ["dog"]}
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    assert report["decision"] == "QUARANTINE"
    assert "SECRET_FOUND" in report["reason_codes"]

def test_missing_label_to_reject(pipeline):
    # label is critical field in thresholds.yaml
    data = {"email": ["test@test.com"], "label": [None]}
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    assert report["decision"] == "REJECT"
    assert "MISSING_TOO_HIGH" in report["reason_codes"]

def test_postcheck_fail_to_quarantine(pipeline):
    # Use a column name that is NOT an alias but contains an email
    # This simulates a leak where PII exists in an un-aliased column
    data = {"unknown_column": ["leak@example.com"], "label": ["cat"]}
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    # Since it's not aliased to 'email', it won't be transformed.
    # But postcheck regex will find it.
    assert report["decision"] == "QUARANTINE"
    assert "POSTCHECK_FAIL" in report["reason_codes"]

# NEW TEST: Verify duplicate removal works
def test_duplicate_removal(pipeline):
    data = {
        "email": ["alice@example.com", "alice@example.com", "bob@test.com"],
        "label": ["cat", "cat", "dog"],
        "amount": [100, 100, 200]
    }
    df = pd.DataFrame(data)
    df_out, report = pipeline.run(df)
    
    # Should have removed 1 duplicate
    assert report["transform_summary"]["duplicates_removed"] == 1
    # Output should have 2 rows
    assert len(df_out) == 2
    assert report["decision"] == "ACCEPT"

# NEW TEST: Verify copy_id is included in transform_summary
def test_copy_id_in_transform_summary(pipeline):
    data = {"email": ["test@test.com"], "label": ["cat"]}
    df = pd.DataFrame(data)
    _, report = pipeline.run(df, copy_id="test_12345")
    
    # copy_id should be in transform_summary
    assert "copy_id" in report["transform_summary"]
    assert report["transform_summary"]["copy_id"] == "test_12345"

# NEW TEST: Verify phone pattern doesn't flag non-phone numbers
def test_postcheck_phone_pattern_no_false_positives(pipeline):
    # ID numbers should NOT trigger phone pattern
    data = {
        "record_id": ["ID1234567890"],  # 10 digits but not a phone
        "account": ["ACC9876543210"],   # 10 digits but not a phone
        "label": ["cat"]
    }
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    
    # Should ACCEPT because these aren't phone patterns
    # The postcheck uses special logic for phones: strips non-digits first
    assert report["decision"] == "ACCEPT"
    assert report["postcheck_summary"]["postcheck_ok"] == True

# NEW TEST: Verify actual phone numbers ARE detected
def test_postcheck_detects_real_phones(pipeline):
    # Real phone number in unknown column should trigger quarantine
    data = {
        "contact_info": ["1234567890"],  # 10 digits, pure phone
        "label": ["cat"]
    }
    df = pd.DataFrame(data)
    _, report = pipeline.run(df)
    
    # Should QUARANTINE because phone pattern detected
    assert report["decision"] == "QUARANTINE"
    assert "POSTCHECK_FAIL" in report["reason_codes"]

# NEW TEST: Verify tokenized phone fields don't trigger postcheck
def test_tokenized_phone_passes_postcheck(pipeline):
    # Phone in aliased column gets tokenized, should pass postcheck
    data = {
        "mobile": ["1234567890"],  # This maps to 'phone' and gets tokenized
        "label": ["cat"]
    }
    df = pd.DataFrame(data)
    df_out, report = pipeline.run(df)
    
    # Should ACCEPT because phone was tokenized
    assert report["decision"] == "ACCEPT"
    assert df_out["phone"].iloc[0].startswith("tok_")
    assert report["postcheck_summary"]["postcheck_ok"] == True