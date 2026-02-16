# Troubleshooting Guide

This guide helps you diagnose and fix common issues when using the Data Leakage Auto-Supervisor Agent.

---

## Common Errors

### Error: "SCHEMA_FAIL"

**Symptoms:**
- Decision: REJECT
- Reason code: `SCHEMA_FAIL`
- Error in validation logs

**Cause:**
The data violates schema constraints defined in `column_dictionary.yaml`. This can include:
- Wrong data types (e.g., string where integer expected)
- Missing required columns
- Invalid column names

**Solution:**

1. **Check which columns failed:**
   ```python
   result = validator.validate(df)
   print(result.metrics.get('schema_violations', {}))
   ```

2. **Compare with schema definition:**
   ```bash
   cat policy/versions/v1/column_dictionary.yaml
   ```

3. **Fix data types:**
   ```python
   # Example: Convert string to float
   df['amount'] = df['amount'].astype(float)
   
   # Example: Convert to datetime
   df['timestamp'] = pd.to_datetime(df['timestamp'])
   ```

4. **Add missing columns:**
   ```python
   # Add required column with default value
   if 'label' not in df.columns:
       df['label'] = 'legitimate'
   ```

**Example:**
```python
# Before (fails)
df = pd.DataFrame({
    'amount': ['100', '200', '300'],  # String instead of float
    'label': ['fraud', 'legit', 'fraud']
})

# After (passes)
df['amount'] = df['amount'].astype(float)
```

---

### Error: "POSTCHECK_FAIL"

**Symptoms:**
- Decision: QUARANTINE
- Reason code: `POSTCHECK_FAIL`
- Message about sensitive patterns remaining after transformations

**Cause:**
After applying all transformations, the postcheck stage detected patterns that look like:
- Email addresses
- Phone numbers
- SSN/tax IDs

This indicates transformations did not fully remove PII.

**Solution:**

1. **Check what patterns were detected:**
   ```python
   result = validator.validate(df)
   pc_results = result.report.get('postcheck_results', {})
   print(f"Patterns found: {pc_results.get('pattern', [])}")
   ```

2. **Verify transformations were applied:**
   ```python
   ts = result.transform_summary
   print(f"Tokenized fields: {ts.get('tokenized_fields_count', {})}")
   print(f"Dropped columns: {ts.get('dropped_columns', [])}")
   ```

3. **Common fixes:**

   **a) Field name not recognized:**
   ```yaml
   # Add alias to policy.yaml
   field_name_aliases:
     email: [email_address, mail, e_mail, user_email]
   ```

   **b) Pattern in unexpected column:**
   ```python
   # Check which column contains the pattern
   for col in df.columns:
       if df[col].dtype == 'object':
           matches = df[col].str.contains(r'@', na=False)
           if matches.any():
               print(f"Email-like pattern in column: {col}")
   ```

   **c) Update policy to handle the field:**
   ```yaml
   actions:
     suspicious_column:
       action: DROP  # or TOKENIZE_DET
   ```

**Example:**
```python
# If postcheck fails on 'contact_info' column:
# 1. Add alias
# policy.yaml:
field_name_aliases:
  email: [email_address, mail, contact_info]

# 2. Or explicitly drop it
actions:
  contact_info:
    action: DROP
```

---

### Error: "MISSING_TOO_HIGH"

**Symptoms:**
- Decision: REJECT
- Reason code: `MISSING_TOO_HIGH`
- High missing value rates in metrics

**Cause:**
One or more fields exceed the missing value rate thresholds defined in `thresholds.yaml`:
- Critical fields: 0% missing allowed (default)
- Non-critical fields: 5% missing allowed (default)

**Solution:**

1. **Identify which fields have too many missing values:**
   ```python
   result = validator.validate(df)
   critical_missing = result.metrics.get('missing_rates_critical', {})
   noncritical_missing = result.metrics.get('missing_rates_noncritical', {})
   
   print("Critical field missing rates:", critical_missing)
   print("Non-critical field missing rates:", noncritical_missing)
   ```

2. **For critical fields (e.g., `label`):**
   ```python
   # Option 1: Fill missing values
   df['label'] = df['label'].fillna('unknown')
   
   # Option 2: Remove rows with missing labels
   df = df.dropna(subset=['label'])
   
   # Option 3: Fix data generation to never create null labels
   ```

3. **For non-critical fields:**
   ```python
   # Fill with appropriate default
   df['gender'] = df['gender'].fillna('prefer_not_to_say')
   df['amount'] = df['amount'].fillna(0.0)
   ```

4. **Adjust thresholds if business requirements allow:**
   ```yaml
   # thresholds.yaml
   missing_rate_limits:
     critical_max: 0      # Keep strict for critical fields
     noncritical_max: 10  # Increase to 10% if acceptable
   ```

**Example Fix:**
```python
# Check missing rate
print(f"Label missing rate: {df['label'].isnull().mean() * 100:.2f}%")

# Fix: Remove rows with missing labels
df_clean = df.dropna(subset=['label'])

# Or: Fill with default
df['label'] = df['label'].fillna('legitimate')
```

---

### Error: "OUT_OF_RANGE"

**Symptoms:**
- Decision: REJECT
- Reason code: `RANGE_VIOLATIONS`
- Values outside expected min/max ranges

**Cause:**
Numeric fields contain values outside the range specified in `column_dictionary.yaml`.

**Solution:**

1. **Check range violations:**
   ```python
   result = validator.validate(df)
   print(f"Range violations: {result.metrics.get('range_violations', 0)}")
   ```

2. **Identify problematic values:**
   ```python
   # For 'amount' field with range [0, 1000000]
   out_of_range = df[(df['amount'] < 0) | (df['amount'] > 1000000)]
   print(f"Found {len(out_of_range)} out-of-range values")
   print(out_of_range[['amount']].describe())
   ```

3. **Fix the data:**
   ```python
   # Option 1: Clip to valid range
   df['amount'] = df['amount'].clip(0, 1000000)
   
   # Option 2: Remove invalid rows
   df = df[(df['amount'] >= 0) & (df['amount'] <= 1000000)]
   
   # Option 3: Fix data generation logic
   ```

4. **Adjust schema if ranges are incorrect:**
   ```yaml
   # column_dictionary.yaml
   - name: amount
     expected_type: float
     range_min: 0
     range_max: 10000000  # Increase max if needed
   ```

**Example:**
```python
# Detect and fix negative amounts
print(f"Negative amounts: {(df['amount'] < 0).sum()}")

# Clip to [0, 1000000]
df['amount'] = df['amount'].clip(0, 1000000)
```

---

### Error: "ENUM_VIOLATION"

**Symptoms:**
- Decision: REJECT
- Reason code: `ENUM_VIOLATIONS`
- Values not in allowed list

**Cause:**
Categorical fields contain values not in the `allowed_values` list in `column_dictionary.yaml`.

**Solution:**

1. **Check which values are invalid:**
   ```python
   result = validator.validate(df)
   print(f"Enum violations: {result.metrics.get('enum_violations', 0)}")
   
   # Manually check
   allowed_genders = ['male', 'female', 'other', 'prefer_not_to_say']
   invalid = df[~df['gender'].isin(allowed_genders)]
   print(f"Invalid gender values: {invalid['gender'].unique()}")
   ```

2. **Fix the data:**
   ```python
   # Option 1: Map invalid values to valid ones
   gender_mapping = {
       'M': 'male',
       'F': 'female',
       'Male': 'male',
       'Female': 'female',
       'unknown': 'prefer_not_to_say'
   }
   df['gender'] = df['gender'].replace(gender_mapping)
   
   # Option 2: Set invalid values to default
   allowed = ['male', 'female', 'other', 'prefer_not_to_say']
   df.loc[~df['gender'].isin(allowed), 'gender'] = 'prefer_not_to_say'
   ```

3. **Update schema if new values should be allowed:**
   ```yaml
   # column_dictionary.yaml
   - name: gender
     allowed_values: [male, female, other, prefer_not_to_say, non_binary]
   ```

**Example:**
```python
# Fix country codes
allowed_countries = ['US', 'UK', 'CA', 'AU', 'DE', 'FR', 'JP', 'CN', 'IN', 'BR']

# Map common variations
country_mapping = {
    'USA': 'US',
    'United States': 'US',
    'UK': 'UK',
    'Britain': 'UK'
}
df['country'] = df['country'].replace(country_mapping)

# Set invalid to default
df.loc[~df['country'].isin(allowed_countries), 'country'] = 'US'
```

---

### Error: "DUPLICATE_RATE_TOO_HIGH"

**Symptoms:**
- Decision: REJECT
- Reason code: `DUPLICATE_RATE_TOO_HIGH`
- Duplicate rate exceeds threshold (default 1%)

**Cause:**
Dataset contains too many duplicate rows.

**Solution:**

1. **Check duplicate rate:**
   ```python
   result = validator.validate(df)
   dup_rate = result.metrics.get('duplicate_rate', 0)
   print(f"Duplicate rate: {dup_rate:.2f}%")
   
   # Manually check
   duplicates = df.duplicated()
   print(f"Duplicate rows: {duplicates.sum()} ({duplicates.mean()*100:.2f}%)")
   ```

2. **Remove duplicates before validation:**
   ```python
   # Remove exact duplicates
   df_clean = df.drop_duplicates()
   
   # Remove duplicates based on specific columns
   df_clean = df.drop_duplicates(subset=['user_id', 'timestamp'])
   ```

3. **Fix data generation to avoid duplicates:**
   ```python
   # Example: Ensure unique user_ids
   df['user_id'] = [f'user_{i:06d}' for i in range(len(df))]
   ```

4. **Adjust threshold if duplicates are expected:**
   ```yaml
   # thresholds.yaml
   duplicate_rate_max: 5  # Allow up to 5% duplicates
   ```

**Example:**
```python
# Check and remove duplicates
print(f"Total rows: {len(df)}")
print(f"Unique rows: {df.drop_duplicates().shape[0]}")

# Remove duplicates
df = df.drop_duplicates()
print(f"After deduplication: {len(df)} rows")
```

---

## Configuration Issues

### Issue: Transformations not applied

**Diagnosis Steps:**

1. **Check if field is recognized:**
   ```python
   result = validator.validate(df)
   ts = result.transform_summary
   print(f"Canonical mapping count: {ts.get('canonical_mapping_count', 0)}")
   ```

2. **Verify field names match policy:**
   ```bash
   # Check your data
   >>> df.columns.tolist()
   ['email_address', 'user_guid', 'amount', 'label']
   
   # Check policy.yaml field_name_aliases
   email: [email_address, mail]
   user_id: [uid, id, user_guid, user_key]
   ```

3. **Add missing aliases:**
   ```yaml
   # policy.yaml
   field_name_aliases:
     email: [email_address, e_mail, mail, contact_email]
   ```

**Common Mistakes:**
- Column name has typo: `emial` vs `email`
- Case sensitivity: `Email` vs `email` (normalize first)
- Extra spaces: ` email ` (use `df.columns = df.columns.str.strip()`)

---

### Issue: Valid data gets rejected

**Diagnosis:**

1. **Check all reason codes:**
   ```python
   result = validator.validate(df)
   print(f"Decision: {result.decision}")
   print(f"All reason codes: {result.reason_codes}")
   ```

2. **Review each metric:**
   ```python
   for metric_name, metric_value in result.metrics.items():
       print(f"{metric_name}: {metric_value}")
   ```

3. **Check thresholds:**
   ```bash
   cat policy/versions/v1/thresholds.yaml
   ```

**Potential Fixes:**
- Relax thresholds if they're too strict for your use case
- Fix data to meet existing thresholds
- Review `column_dictionary.yaml` for incorrect constraints

---

## Performance Issues

### Issue: Slow processing

**Diagnosis:**

```python
import time

start = time.time()
result = validator.validate(df)
elapsed = time.time() - start

print(f"Validation took {elapsed:.2f} seconds for {len(df)} rows")
print(f"Rate: {len(df)/elapsed:.0f} rows/second")
```

**Solutions:**

1. **Use batch processing for multiple files:**
   ```bash
   # Instead of multiple individual runs
   python -m leakage_agent.cli batch \
       --input-dir data/ \
       --workers 8  # Use more CPU cores
   ```

2. **Optimize DataFrame operations:**
   ```python
   # Pre-filter before validation
   df = df[df['amount'] > 0]  # Remove obviously bad rows
   df = df.drop_duplicates()  # Remove duplicates first
   ```

3. **Process in chunks for large files:**
   ```python
   chunk_size = 10000
   for chunk in pd.read_csv('large_file.csv', chunksize=chunk_size):
       result = validator.validate(chunk)
       # Process result...
   ```

4. **Reduce I/O:**
   ```python
   # If you don't need report files, process in-memory only
   # (Not currently supported, but future enhancement)
   ```

---

## Debugging Tips

### 1. Enable Verbose Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)

validator = LeakageValidator()
result = validator.validate(df)
```

### 2. Check Intermediate Outputs

```bash
# After validation, check the outputs directory
ls -la outputs/

# View the validation report
cat outputs/example_001/validation_report.json | python -m json.tool
```

### 3. Validate Policy Files

```python
from leakage_agent.config_loader import ConfigLoader

try:
    config = ConfigLoader("policy/versions/v1")
    print("✓ Policy files are valid")
except Exception as e:
    print(f"✗ Policy error: {e}")
```

### 4. Test with Minimal Data

```python
# Create minimal test case
df_test = pd.DataFrame({
    'user_id': ['test_001'],
    'email': ['test@example.com'],
    'amount': [100.0],
    'label': ['fraud']
})

result = validator.validate(df_test, copy_id="debug_test")
print(f"Minimal test: {result.decision}")
```

### 5. Compare Before/After

```python
print("BEFORE transformation:")
print(df[['user_id', 'email', 'name']].head())

result = validator.validate(df)

if result.is_accepted:
    print("\nAFTER transformation:")
    print(result.cleaned_data.head())
    
    print("\nDropped columns:")
    dropped = set(df.columns) - set(result.cleaned_data.columns)
    print(dropped)
```

---

## Getting More Help

### Check Documentation
- [README.md](README.md) - Overview and quick start
- [CONFIGURATION.md](CONFIGURATION.md) - Policy configuration details
- [API_REFERENCE.md](API_REFERENCE.md) - Complete API documentation

### Run Tests
```bash
# Run tests to verify system is working
pytest tests/ -v

# Run specific test
pytest tests/test_api.py::test_basic_validation -v
```

### Enable Debug Mode
```python
# Get full validation report
result = validator.validate(df)
import json
print(json.dumps(result.report, indent=2))
```

### Community Support
- Open an issue on GitHub with:
  - Error message
  - Sample data (anonymized)
  - Policy configuration
  - Expected vs actual behavior

---

## Quick Reference: Exit Codes

When using the CLI, these exit codes indicate different outcomes:

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | ACCEPT | Data approved, proceed with training |
| 1 | Runtime error | Fix code/config issue |
| 2 | REJECT | Fix data quality issues |
| 3 | QUARANTINE | Security review required |

**Example bash script:**
```bash
python -m leakage_agent.cli run --input data.csv

case $? in
  0) echo "✅ Approved" ;;
  2) echo "❌ Quality issues - check metrics" ;;
  3) echo "⚠️  Security review needed" ;;
  *) echo "💥 Runtime error" ;;
esac
```
