# Configuration Guide

This guide provides a deep dive into the policy configuration system for the Data Leakage Auto-Supervisor Agent.

---

## Overview

The validation pipeline is controlled by **four YAML configuration files** located in `policy/versions/v1/`:

1. **policy.yaml** - Field aliases, transformation actions, and postcheck patterns
2. **thresholds.yaml** - Quality gates and limits
3. **column_dictionary.yaml** - Schema definitions with constraints
4. **forbidden.yaml** - Security patterns that trigger quarantine

All configurations are versioned to support policy evolution and reproducibility.

---

## policy.yaml

This file defines how each field should be transformed to prevent data leakage.

### Structure

```yaml
version: "v1"

field_name_aliases:
  # Maps alternative field names to canonical names
  
actions:
  # Transformation rules for each field
  
generalization_fallbacks:
  # What to do if generalization fails
  
default_action:
  # Default behavior for unmapped fields
  
postcheck:
  # Privacy audit patterns applied AFTER transformations
```

---

### Field Name Aliases

Maps alternative column names to canonical policy fields. The pipeline uses these aliases to recognize fields regardless of naming variations.

**Example:**
```yaml
field_name_aliases:
  user_id: [uid, id, user_guid, user_key, userId]
  email: [email_address, mail, e_mail, user_email]
  phone: [phone_number, mobile, tel, cell, telephone]
  name: [full_name, user_name, customer_name, display_name]
  national_id: [ssn, tax_id, govt_id, social_security]
  dob: [birth_date, date_of_birth, birthdate]
  address: [street_address, location, mailing_address, residence]
  zip_code: [postal_code, zip, postcode]
  timestamp: [created_at, ts, datetime, created_date]
```

**How it works:**
1. Input data has column `email_address`
2. Pipeline checks aliases and maps `email_address` → `email`
3. Applies transformation rules for `email`

**Adding new aliases:**
```yaml
# If your data uses 'user_contact' for email
field_name_aliases:
  email: [email_address, mail, user_contact]  # Add user_contact
```

---

### Actions

Defines transformation rules for each field. There are **four transformation types**:

#### 1. KEEP - Preserve field unchanged

```yaml
actions:
  city:
    action: KEEP
  
  country:
    action: KEEP
  
  amount:
    action: KEEP
  
  label:
    action: KEEP  # Always keep the target variable
```

**Use when:** Field has no PII risk and provides ML utility

---

#### 2. DROP - Remove field entirely

```yaml
actions:
  name:
    action: DROP
  
  national_id:
    action: DROP
  
  credit_card:
    action: DROP
```

**Use when:**
- Field is direct PII with high re-identification risk
- No ML utility
- Cannot be safely transformed

**Effect:** Column is completely removed from output

---

#### 3. TOKENIZE_DET - Deterministic tokenization

```yaml
actions:
  user_id:
    action: TOKENIZE_DET
    normalization: [trim]
  
  email:
    action: TOKENIZE_DET
    normalization: [trim, lowercase]
  
  phone:
    action: TOKENIZE_DET
    normalization: [trim, digits_only]
```

**How it works:**
- Applies normalization steps (optional)
- Hashes value with SHA-256
- Generates token: `tok_<hash_prefix>`
- **Same input always produces same token** (deterministic)

**Normalization options:**
- `trim` - Remove leading/trailing whitespace
- `lowercase` - Convert to lowercase
- `digits_only` - Keep only digits
- `date_iso` - Convert date to ISO format

**Example transformation:**
```
Input:  john.doe@example.com
Normalize: trim, lowercase → john.doe@example.com
Hash: sha256(...) → a7f3b2c4d1e5f6g7h8i9j0k1...
Output: tok_a7f3b2c4d1e5f6g7
```

**Use when:**
- Need to preserve entity relationships (same user across rows)
- Cannot use raw values due to PII concerns
- Examples: user IDs, email addresses, phone numbers

---

#### 4. BUCKET - Value bucketing

```yaml
actions:
  dob:
    action: BUCKET
    output_field: "age_bucket"
    bucket_scheme: ["0-17", "18-25", "26-35", "36-45", "46-60", "60+"]
  
  income:
    action: BUCKET
    output_field: "income_range"
    bucket_scheme: ["0-30k", "30k-60k", "60k-100k", "100k+"]
```

**How it works:**
- Parses date/numeric value
- Assigns to appropriate bucket
- Creates new derived column
- Original column is dropped

**Date bucketing (for dob):**
```
Input (dob):  1985-03-15  →  Age: 38  →  Bucket: 36-45
Input (dob):  2005-11-03  →  Age: 18  →  Bucket: 18-25
```

**Use when:**
- Reduce granularity of quasi-identifiers
- Preserve statistical utility while reducing re-identification risk
- Examples: age ranges, income brackets

---

#### 5. GENERALIZE - Data generalization

```yaml
actions:
  address:
    action: GENERALIZE
    output_field: "city_only"
    generalize_scheme: "extract_city"
  
  zip_code:
    action: GENERALIZE
    output_field: "zip_prefix_3"
    generalize_scheme: "prefix_3"
```

**Generalization schemes:**

| Scheme | Description | Example |
|--------|-------------|---------|
| `extract_city` | Extract city from full address | `123 Main St, SF, CA` → `SF` |
| `prefix_3` | Keep first 3 characters | `94102` → `941` |
| `prefix_N` | Keep first N characters | Configurable |

**How it works:**
- Extracts higher-level information from detailed values
- Creates new derived column
- Original column is dropped

**Use when:**
- Need geographic/hierarchical information without full detail
- Examples: city from address, state from city, prefix from zip code

---

### Generalization Fallbacks

What to do if generalization fails (e.g., cannot extract city from malformed address).

```yaml
generalization_fallbacks:
  address: DROP       # If city extraction fails, drop the address field
  zip_code: KEEP      # If prefix extraction fails, keep original
```

**Options:**
- `DROP` - Remove the field (safest)
- `KEEP` - Keep original value (use with caution)
- Future: `NULL` - Set to null/empty

---

### Default Action

Behavior for fields not explicitly listed in `actions`.

```yaml
default_action:
  action: KEEP
```

**Options:**
- `KEEP` - Allow unmapped fields (permissive)
- `DROP` - Remove unmapped fields (restrictive, safer)

**Recommendation:** Use `KEEP` during development, switch to `DROP` for production to enforce explicit policy.

---

### Postcheck Patterns

**Critical security feature:** After all transformations, scan data for leaked PII patterns.

```yaml
postcheck:
  apply_stage: post_fix
  prohibited_patterns:
    - pattern: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
      description: "Email address pattern"
    
    - pattern: '\b\d{10,15}\b'
      description: "Phone-like digit length 10-15"
    
    - pattern: '\d{3}-\d{2}-\d{4}'
      description: "Standard SSN pattern (xxx-xx-xxxx)"
    
    - pattern: '\b[A-Z]{2}\d{6,9}\b'
      description: "Passport-like pattern"
```

**How it works:**
1. All transformations applied
2. Scan every string field for patterns
3. If ANY pattern found → Decision = QUARANTINE

**Adding custom patterns:**
```yaml
prohibited_patterns:
  - pattern: 'sk_live_[a-zA-Z0-9]{24}'
    description: "Stripe API key"
  
  - pattern: 'AKIA[0-9A-Z]{16}'
    description: "AWS Access Key"
```

**Testing patterns:**
```python
import re
pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
test_value = "contact: john@example.com"
if re.search(pattern, test_value):
    print("Pattern matched!")
```

---

## thresholds.yaml

Defines quality gates that determine ACCEPT vs REJECT decisions.

### Structure

```yaml
version: "v1"

critical_fields:
  # Fields that must not have missing values
  
missing_rate_limits:
  # Maximum allowed missing value percentages
  
duplicate_rate_max:
  # Maximum allowed duplicate row percentage
  
violation_limits:
  # Maximum allowed constraint violations
  
postcheck_requirements:
  # Postcheck pattern tolerance
  
retry_strategy:
  # Retry/regeneration parameters
```

---

### Critical Fields

Fields essential for dataset utility. **0% missing values allowed** (strict).

```yaml
critical_fields:
  - label           # Target variable for ML - must always be present
  - user_id         # If user_id is required for your use case
  - transaction_id  # Add other critical fields
```

**Effect:**
- If ANY critical field has missing values → Decision = REJECT
- Reason code: `MISSING_TOO_HIGH`

---

### Missing Rate Limits

Maximum allowed percentage of missing values for different field types.

```yaml
missing_rate_limits:
  critical_max: 0      # 0% missing allowed for critical fields
  noncritical_max: 5   # 5% missing allowed for other fields
```

**How it calculates:**
```python
missing_rate = (null_count / total_rows) * 100
```

**Example:**
- 1000 rows, 30 have null `gender` (non-critical)
- Missing rate: (30/1000) * 100 = 3%
- Threshold: 5%
- **Result:** PASS ✅

**Adjusting thresholds:**
```yaml
missing_rate_limits:
  critical_max: 0      # Keep strict
  noncritical_max: 10  # Relax to 10% if acceptable for your use case
```

---

### Duplicate Rate Maximum

Maximum allowed percentage of duplicate rows.

```yaml
duplicate_rate_max: 1  # Max 1% duplicates allowed
```

**How it calculates:**
```python
duplicates = df.duplicated().sum()
duplicate_rate = (duplicates / total_rows) * 100
```

**Example:**
- 1000 rows, 8 are exact duplicates
- Duplicate rate: (8/1000) * 100 = 0.8%
- Threshold: 1%
- **Result:** PASS ✅

**Note:** Duplicates are **automatically removed** during stage 3.5 (deduplicate), but if the removal rate exceeds the threshold, validation fails.

---

### Violation Limits

Maximum allowed constraint violations from schema validation.

```yaml
violation_limits:
  range_violations_max: 0   # No range violations allowed
  enum_violations_max: 0    # No enum violations allowed
```

**Types of violations:**

1. **Range violations:** Values outside `[range_min, range_max]`
   ```yaml
   # column_dictionary.yaml
   - name: amount
     range_min: 0
     range_max: 1000000
   
   # If amount = -500 or 2000000 → RANGE_VIOLATION
   ```

2. **Enum violations:** Values not in `allowed_values` list
   ```yaml
   # column_dictionary.yaml
   - name: gender
     allowed_values: [male, female, other, prefer_not_to_say]
   
   # If gender = "unknown" → ENUM_VIOLATION
   ```

**Setting tolerances:**
```yaml
violation_limits:
  range_violations_max: 10   # Allow up to 10 range violations
  enum_violations_max: 5     # Allow up to 5 enum violations
```

**Recommendation:** Keep at 0 for production to ensure data quality.

---

### Postcheck Requirements

Tolerance for patterns detected in postcheck stage.

```yaml
postcheck_requirements:
  sensitive_patterns_remaining_max: 0  # Zero tolerance
```

**Effect:**
- If ANY sensitive pattern found after transformations → QUARANTINE
- No exceptions

**Why strict:** This catches transformation failures that could leak PII.

---

### Retry Strategy

Parameters for orchestrator retry logic.

```yaml
retry_strategy:
  max_regenerations_per_copy: 3      # Max 3 retry attempts
  max_total_attempts_factor: 5       # Safety limit for batch processing
```

**Used by:** `DataOrchestrator` class for automated retry workflows.

---

## column_dictionary.yaml

Defines the expected schema with detailed constraints for each field.

### Structure

```yaml
version: "v1"
columns:
  - name: field_name
    expected_type: type
    role: classification
    critical: boolean
    nullable: boolean
    range_min: number (optional)
    range_max: number (optional)
    allowed_values: list (optional)
    max_length: number (optional)
    notes: description
```

---

### Field Definitions

#### Basic Field

```yaml
- name: user_id
  expected_type: string
  role: identifier
  critical: false
  nullable: false
  notes: "Unique user identifier"
```

#### Numeric Field with Range

```yaml
- name: amount
  expected_type: float
  role: feature
  critical: false
  nullable: false
  range_min: 0
  range_max: 1000000
  notes: "Transaction amount (must be non-negative)"
```

#### Categorical Field with Enum

```yaml
- name: gender
  expected_type: string
  role: feature
  critical: false
  nullable: true
  allowed_values: [male, female, other, prefer_not_to_say]
  notes: "User gender"
```

#### Critical Field

```yaml
- name: label
  expected_type: string
  role: label
  critical: true      # Cannot have missing values
  nullable: false
  notes: "Target variable for ML (cannot be null)"
```

---

### Field Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ | Canonical field name |
| `expected_type` | string | ✅ | Data type: `string`, `float`, `int`, `datetime`, `date`, `bool` |
| `role` | string | ✅ | Field classification (see below) |
| `critical` | boolean | ✅ | Is this field critical for dataset utility? |
| `nullable` | boolean | ✅ | Can this field have null values? |
| `range_min` | number | ❌ | Minimum allowed value (numeric fields) |
| `range_max` | number | ❌ | Maximum allowed value (numeric fields) |
| `allowed_values` | list | ❌ | Valid values (categorical fields) |
| `max_length` | number | ❌ | Maximum string length |
| `notes` | string | ❌ | Human-readable description |

---

### Field Roles

| Role | Description | Examples |
|------|-------------|----------|
| `identifier` | Uniquely identifies entities | user_id, transaction_id |
| `pii` | Personal identifiable information | email, phone, name, national_id |
| `quasi_identifier` | Can contribute to re-identification | dob, zip_code, city |
| `feature` | ML feature with low PII risk | amount, gender, country |
| `metadata` | Timestamps, versioning | timestamp, created_at |
| `label` | Target variable for ML | label, target, outcome |
| `derived` | Created by transformations | age_bucket, zip_prefix_3 |

**Purpose:** Documentation and future policy extensions (e.g., k-anonymity checks).

---

### Adding New Fields

**Step 1:** Add to `column_dictionary.yaml`

```yaml
- name: subscription_tier
  expected_type: string
  role: feature
  critical: false
  nullable: true
  allowed_values: [free, basic, premium, enterprise]
  notes: "User subscription level"
```

**Step 2:** Define transformation in `policy.yaml`

```yaml
actions:
  subscription_tier:
    action: KEEP  # No PII risk, keep as-is
```

**Step 3:** (Optional) Add aliases if needed

```yaml
field_name_aliases:
  subscription_tier: [plan, tier, subscription_level]
```

---

### Constraints Usage

**Range constraints (numeric fields):**
```yaml
- name: age
  expected_type: int
  range_min: 0
  range_max: 120
```

**Enum constraints (categorical fields):**
```yaml
- name: country
  expected_type: string
  allowed_values: [US, UK, CA, AU, DE, FR, JP, CN, IN, BR]
```

**String length constraints:**
```yaml
- name: city
  expected_type: string
  max_length: 100
```

**Nullable constraints:**
```yaml
- name: label
  nullable: false  # Must not be null
```

---

## forbidden.yaml

Security configuration for detecting secrets and forbidden patterns.

### Structure

```yaml
version: "v1"

forbidden_column_names:
  # Column names that trigger immediate quarantine
  
forbidden_value_patterns:
  # Value patterns that trigger quarantine
  
default_action: QUARANTINE

description: >
  Security violation handling policy
```

---

### Forbidden Column Names

Column names that should never appear in training data.

```yaml
forbidden_column_names:
  - password
  - pwd
  - pass
  - passphrase
  - api_key
  - secret_key
  - access_token
  - refresh_token
  - bearer_token
  - private_key
  - jwt
  - session_id
  - auth_token
  - api_secret
  - client_secret
```

**Effect:**
- If ANY forbidden column exists → Decision = QUARANTINE
- Entire dataset flagged for manual review

**Adding custom patterns:**
```yaml
forbidden_column_names:
  - credit_card
  - cvv
  - ssn
  - tax_id
  - internal_id  # Your custom sensitive fields
```

---

### Forbidden Value Patterns

Patterns that should not exist in ANY field values.

```yaml
forbidden_value_patterns:
  - jwt_like           # JWT token pattern
  - private_key_block  # PEM private key block
  - bearer_token       # OAuth bearer tokens
```

**Pattern implementations** (defined in `forbidden_scan.py`):

```python
# JWT pattern
r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'

# Private key block
r'-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----'

# Bearer token
r'Bearer [a-zA-Z0-9_-]{20,}'
```

**Adding custom patterns:**
1. Add pattern name to `forbidden.yaml`
2. Implement regex in `forbidden_scan.py`

---

### Default Action

```yaml
default_action: QUARANTINE
```

**Fixed behavior:** Forbidden patterns ALWAYS trigger QUARANTINE (not configurable).

---

## Best Practices

### 1. Start with Restrictive Policies

```yaml
# policy.yaml
default_action:
  action: DROP  # Drop unmapped fields by default

# thresholds.yaml
missing_rate_limits:
  critical_max: 0
  noncritical_max: 5  # Start strict

violation_limits:
  range_violations_max: 0
  enum_violations_max: 0
```

**Why:** Easier to relax than tighten. Prevents accidental PII leakage.

---

### 2. Test on Sample Data First

```python
# Use small sample for policy testing
df_sample = df.head(100)
result = validator.validate(df_sample, copy_id="policy_test")

if result.is_rejected:
    print(f"Fix these issues: {result.reason_codes}")
```

---

### 3. Version Your Policies

```
policy/
  versions/
    v1/  (current production)
    v2/  (testing new rules)
    v3/  (future)
```

**Advantages:**
- Reproducibility (can revalidate with old policies)
- A/B testing of policy changes
- Rollback capability

---

### 4. Document Policy Changes

```yaml
# policy.yaml
version: "v2"
changelog:
  - date: "2024-01-15"
    changes: "Added credit_score field with bucketing"
  - date: "2024-01-20"
    changes: "Relaxed missing_rate for gender from 5% to 10%"
```

---

### 5. Regular Policy Audits

**Monthly checklist:**
- [ ] Review postcheck patterns for false positives
- [ ] Check if new PII types need coverage
- [ ] Validate range constraints still match business logic
- [ ] Review rejected datasets for policy improvement opportunities

---

## Configuration Validation

### Check Policy Files Are Valid

```bash
# Use Python to load and validate
python -c "
from leakage_agent.config_loader import ConfigLoader
try:
    config = ConfigLoader('policy/versions/v1')
    print('✅ Policy files are valid')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

### Lint YAML Files

```bash
# Install yamllint
pip install yamllint

# Check syntax
yamllint policy/versions/v1/*.yaml
```

---

## Example: Complete Custom Policy

```yaml
# policy.yaml
version: "custom_v1"

field_name_aliases:
  customer_id: [cust_id, customer_guid]
  purchase_amount: [amount, total, purchase_total]

actions:
  customer_id:
    action: TOKENIZE_DET
    normalization: [trim]
  
  purchase_amount:
    action: KEEP
  
  customer_email:
    action: DROP  # Remove email entirely
  
  age:
    action: BUCKET
    output_field: "age_group"
    bucket_scheme: ["18-30", "31-50", "51-70", "70+"]

default_action:
  action: DROP  # Restrictive default

postcheck:
  apply_stage: post_fix
  prohibited_patterns:
    - pattern: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
      description: "Email addresses"
```

See [API_REFERENCE.md](API_REFERENCE.md) for programmatic policy usage.
