# Data Leakage Auto-Supervisor Agent

**Automated validation pipeline for ML training data that detects and prevents PII leakage, enforces quality gates, and applies privacy-preserving transformations.**

---

## 🚀 Quick Start

### Installation

```bash
pip install -e ./leakage_agent
```

### Basic Usage

```python
from leakage_agent import LeakageValidator
import pandas as pd

validator = LeakageValidator()
result = validator.validate(df)

if result.is_accepted:
    result.cleaned_data.to_csv("approved_data.csv")
```

---

## ✅ Features

🔒 **Privacy Protection** - Detects and quarantines datasets containing secrets, API keys, or PII leakage  
🔄 **Automated Transformations** - Tokenization, bucketing, generalization, and field dropping  
📊 **Quality Gates** - Validates data against schema constraints, range limits, and enum values  
⚡ **Batch Processing** - Process multiple datasets in parallel with progress tracking  
🔍 **Lineage Tracking** - Full audit trail of data provenance and transformations  
🛡️ **Post-Check Validation** - Pattern-based scanning after transformations to catch residual leakage  
🎯 **Retry Orchestration** - Automated retry logic with actionable regeneration guidance  
📝 **Decision System** - Three-tier decisions: ACCEPT, REJECT, QUARANTINE

---

## 🏗️ Architecture

The system implements a **9-stage validation pipeline**:

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT: Raw Training Data DataFrame                        │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────▼──────────┐
        │ 1. CANONICALIZE   │  Map field aliases to standard names
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 2. FORBIDDEN SCAN │  Check for secrets/PII column names
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 3. NORMALIZE      │  Apply trim, lowercase, digits_only
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 3.5. DEDUPLICATE  │  Remove duplicate records
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 4. TRANSFORM      │  TOKENIZE_DET / BUCKET / GENERALIZE / DROP
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 5. POSTCHECK      │  Scan for leaked patterns (email, SSN, phone)
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 6. METRICS        │  Calculate missing rates, violations
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 7. DECISION       │  QUARANTINE > REJECT > ACCEPT
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 8. REPORTING      │  Generate JSON validation report
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │ 9. WRITE OUTPUTS  │  Save cleaned data + reports
        └────────┬──────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  OUTPUT: ValidationResult(decision, cleaned_data, report)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📖 Usage Examples

### Python API

#### 1. Single Dataset Validation

```python
from leakage_agent import LeakageValidator
import pandas as pd

df = pd.read_csv("training_data.csv")
validator = LeakageValidator(policy_dir="policy/versions/v1")
result = validator.validate(df, copy_id="batch_001")

print(f"Decision: {result.decision}")
print(f"Reason Codes: {result.reason_codes}")

if result.is_accepted:
    # Use cleaned data for training
    result.cleaned_data.to_csv("approved_data.csv", index=False)
elif result.is_rejected:
    # Fix quality issues
    print(f"Metrics: {result.metrics}")
elif result.is_quarantined:
    # Security review required
    print("⚠️ Dataset contains forbidden patterns")
```

#### 2. Batch Validation

```python
dataframes = {
    "batch_001": pd.read_csv("data_001.csv"),
    "batch_002": pd.read_csv("data_002.csv"),
    "batch_003": pd.read_csv("data_003.csv")
}

results = validator.validate_batch(dataframes, out_dir="outputs")

# Get summary statistics
summary = validator.get_summary(results)
print(f"Accepted: {summary['accepted']}/{summary['total']}")
print(f"Rejection rate: {summary['rejected']/summary['total']*100:.1f}%")
```

#### 3. Using Context Manager

```python
with LeakageValidator() as validator:
    result = validator.validate(df)
    if result.is_accepted:
        print(f"✅ Approved - {len(result.cleaned_data)} rows")
```

#### 4. Retry with Orchestrator

```python
from leakage_agent.orchestrator import DataOrchestrator

orchestrator = DataOrchestrator(max_retries=3)
result = orchestrator.process_with_retry(
    df=my_dataframe,
    copy_id="exp_001",
    regenerator=my_regeneration_function  # Optional
)

print(f"Final decision: {result.decision}")
print(f"Total attempts: {result.report.get('attempt_count', 1)}")
```

### CLI Usage

#### Single File Processing

```bash
# Basic validation
python -m leakage_agent.cli run --input data.csv

# Custom policy and output directory
python -m leakage_agent.cli run \
    --input data.csv \
    --policy policy/versions/v1 \
    --out outputs \
    --copy-id my_dataset_001
```

**Exit Codes:**
- `0` - ACCEPT (data passed validation)
- `1` - Runtime error
- `2` - REJECT (quality issues)
- `3` - QUARANTINE (security issues)

#### Batch Processing

```bash
# Process all CSV files in directory
python -m leakage_agent.cli batch \
    --input-dir data/candidates/ \
    --out outputs \
    --workers 4

# Custom file pattern
python -m leakage_agent.cli batch \
    --input-dir data/ \
    --pattern "train_*.csv" \
    --workers 8 \
    --quiet
```

**Output:**
```
==============================================================
BATCH PROCESSING SUMMARY
==============================================================
Total files:    100
✅ Accepted:    85 (85.0%)
❌ Rejected:    10 (10.0%)
⚠️  Quarantined: 5 (5.0%)
💥 Failed:      0
==============================================================
```

---

## ⚙️ Configuration Guide

The system uses four YAML configuration files located in `policy/versions/v1/`:

### 1. `policy.yaml` - Transformation Rules

Defines field aliases, transformation actions, and post-check patterns.

**Example:**
```yaml
field_name_aliases:
  user_id: [uid, id, user_guid, user_key]
  email: [email_address, mail]

actions:
  user_id:
    action: TOKENIZE_DET
    normalization: [trim]
  email:
    action: TOKENIZE_DET
    normalization: [trim, lowercase]
  dob:
    action: BUCKET
    output_field: "age_bucket"
    bucket_scheme: ["0-17", "18-25", "26-35", "36-45", "46-60", "60+"]
  name:
    action: DROP
```

### 2. `thresholds.yaml` - Quality Gates

Sets maximum allowable rates for missing values, duplicates, and violations.

**Example:**
```yaml
critical_fields:
  - label

missing_rate_limits:
  critical_max: 0      # 0% missing allowed for critical fields
  noncritical_max: 5   # 5% missing allowed for other fields

duplicate_rate_max: 1  # Max 1% duplicates

violation_limits:
  range_violations_max: 0
  enum_violations_max: 0
```

### 3. `column_dictionary.yaml` - Schema Constraints

Defines expected types, ranges, and allowed values for each field.

**Example:**
```yaml
columns:
  - name: amount
    expected_type: float
    range_min: 0
    range_max: 1000000
    nullable: false
    
  - name: gender
    expected_type: string
    allowed_values: [male, female, other, prefer_not_to_say]
    nullable: true
    
  - name: label
    expected_type: string
    critical: true
    nullable: false
```

### 4. `forbidden.yaml` - Security Patterns

Lists forbidden column names and value patterns that trigger immediate quarantine.

**Example:**
```yaml
forbidden_column_names:
  - password
  - api_key
  - secret_key
  - access_token

forbidden_value_patterns:
  - jwt_like
  - private_key_block
  - bearer_token

default_action: QUARANTINE
```

---

## 🔐 Decision Logic

The system applies a **hierarchical decision tree** (priorities from highest to lowest):

```
1. QUARANTINE  (Forbidden patterns detected)
   ├─ Forbidden column names present
   ├─ JWT/API key patterns in values
   └─ Sensitive patterns detected in postcheck
   
2. REJECT  (Quality gates failed)
   ├─ Critical fields have missing values
   ├─ Missing rate exceeds thresholds
   ├─ Duplicate rate exceeds threshold
   ├─ Range violations detected
   └─ Enum violations detected
   
3. ACCEPT  (All checks passed)
   └─ Data meets all quality and security requirements
```

**Key Rule**: If ANY quarantine condition is met, decision = QUARANTINE (regardless of other issues).

---

## 🔄 Privacy Transformations

### TOKENIZE_DET - Deterministic Tokenization

Replaces sensitive values with consistent hashes (same input = same token).

**Before:**
```
user_id
--------
john.doe@example.com
jane.smith@example.com
```

**After:**
```
user_id
--------
tok_a7f3b2c4d1e5f6g7
tok_c4e1b9d3a2f5e6b7
```

**Use Case**: Preserve relationships without exposing identifiable values (useful for user IDs, emails).

---

### BUCKET - Value Bucketing

Groups continuous values into discrete ranges.

**Before:**
```
dob
----------
1985-03-15
1992-07-22
2005-11-03
```

**After:**
```
age_bucket
----------
36-45
26-35
18-25
```

**Use Case**: Reduce granularity of quasi-identifiers (age, income ranges).

---

### GENERALIZE - Data Generalization

Extracts higher-level information from detailed values.

**Before:**
```
address
--------------------------------
123 Main St, San Francisco, CA
456 Oak Ave, New York, NY
```

**After:**
```
city_only
--------------
San Francisco
New York
```

**Example schemes:**
- `extract_city` - Extract city from full address
- `prefix_3` - Keep first 3 characters of zip code (94102 → 941)

**Use Case**: Retain utility while reducing specificity.

---

### DROP - Field Removal

Completely removes fields that cannot be safely transformed.

**Before:**
```
name           | email                | amount
---------------|----------------------|-------
John Doe       | john@example.com     | 150.00
Jane Smith     | jane@example.com     | 220.00
```

**After:**
```
email                | amount
---------------------|-------
john@example.com     | 150.00
jane@example.com     | 220.00
```

**Use Case**: Remove fields with no ML utility or high re-identification risk (full names, SSNs).

---

## 🛠️ Troubleshooting

### Issue: Data gets REJECTED with "MISSING_TOO_HIGH"

**Cause**: Missing value rate exceeds thresholds.

**Solution**:
1. Check metrics: `result.metrics['missing_rates_critical']`
2. Fix data generation to ensure critical fields (e.g., `label`) are never null
3. Adjust `thresholds.yaml` if business requirements allow higher missing rates

---

### Issue: Valid data gets QUARANTINED

**Cause**: Postcheck patterns detected in supposedly cleaned data.

**Solution**:
1. Check postcheck results: `result.report['postcheck_results']`
2. Verify transformations are actually applied (check `transform_summary`)
3. Update `policy.yaml` postceck patterns if false positive

---

### Issue: Transformations not applied

**Cause**: Field names don't match policy.

**Solution**:
1. Add aliases to `policy.yaml`:
   ```yaml
   field_name_aliases:
     email: [email_address, mail, e_mail, user_email]
   ```
2. Or rename columns before validation:
   ```python
   df = df.rename(columns={"e_mail": "email"})
   ```

---

## 🧪 Testing

### Run Unit Tests

```bash
cd leakage_agent
pytest tests/ -v
```

### Test Coverage

```bash
pytest tests/ --cov=leakage_agent --cov-report=html
```

### Run Specific Test Suite

```bash
# API tests
pytest tests/test_api.py -v

# Pipeline tests
pytest tests/test_pipeline.py -v

# End-to-end tests
pytest tests/test_end_to_end.py -v
```

---

## 📚 Additional Documentation

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Detailed error diagnosis and fixes
- [CONFIGURATION.md](CONFIGURATION.md) - Deep dive into policy configuration
- [API_REFERENCE.md](API_REFERENCE.md) - Complete API documentation

---

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd leakage_agent

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Style

- Follow PEP 8
- Use type hints for function signatures
- Add docstrings for all public methods
- Write unit tests for new features

### Submit Changes

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. Run tests: `pytest tests/ -v`
4. Commit: `git commit -m "Add my feature"`
5. Push and create pull request

---

## 📄 License

This project is licensed under the MIT License.

---

## 🔗 Links

- **Examples**: [examples/](examples/) - Runnable code examples
- **Policy Templates**: [policy/versions/v1/](policy/versions/v1/) - Configuration templates
- **Tests**: [tests/](tests/) - Unit and integration tests

---

## 💡 Design Philosophy

**Privacy by Default**: All PII fields must be explicitly marked as KEEP or they will be transformed/dropped.

**Fail Secure**: When in doubt, QUARANTINE. Better to manually review than leak sensitive data.

**Reproducibility**: Deterministic transformations ensure same input always produces same output.

**Transparency**: Full audit trails via lineage tracking and detailed reports.

**Composability**: Pipeline stages are independent and can be extended or replaced.

---

## ⚡ Performance Tips

1. **Batch Processing**: Use `validate_batch()` instead of multiple `validate()` calls
2. **Parallel Workers**: Increase `--workers` for large datasets
3. **Policy Caching**: Reuse same `LeakageValidator` instance for multiple validations
4. **Streaming**: For very large files, split into chunks before validation

---

## 🎯 Roadmap

- [ ] Support for more transformation schemes (k-anonymity, differential privacy)
- [ ] Real-time validation API endpoint
- [ ] Integration with synthetic data generators (SDV, CTGAN)
- [ ] Cloud storage backends (S3, GCS, Azure Blob)
- [ ] Web UI for policy management

---

**Need Help?** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or open an issue.
