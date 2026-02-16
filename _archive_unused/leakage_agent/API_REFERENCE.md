# API Reference

Complete API documentation for the Data Leakage Auto-Supervisor Agent.

---

## Table of Contents

- [LeakageValidator](#leakagevalidator)
- [ValidationResult](#validationresult)
- [DataOrchestrator](#dataorchestrator)
- [LineageTracker](#lineagetracker)
- [BatchProcessor](#batchprocessor)
- [Pipeline](#pipeline)

---

## LeakageValidator

Main API class for validating training data against leakage policies.

### Constructor

```python
LeakageValidator(policy_dir="policy/versions/v1")
```

**Parameters:**
- `policy_dir` (str, optional): Path to policy directory containing YAML configuration files. Default: `"policy/versions/v1"`

**Returns:**
- `LeakageValidator` instance

**Raises:**
- `FileNotFoundError`: If policy directory or required YAML files don't exist
- `yaml.YAMLError`: If YAML files are malformed

**Example:**
```python
from leakage_agent import LeakageValidator

# Use default policy
validator = LeakageValidator()

# Use custom policy version
validator = LeakageValidator(policy_dir="policy/versions/v2")
```

---

### Methods

#### validate()

```python
validate(df, copy_id=None, out_dir="outputs")
```

Validate a single DataFrame against leakage policies.

**Parameters:**
- `df` (pd.DataFrame): Input DataFrame to validate
- `copy_id` (str, optional): Unique identifier for this dataset. Auto-generated if None. Format: `"auto_<8_hex_chars>"`
- `out_dir` (str, optional): Output directory for reports and cleaned data. Default: `"outputs"`

**Returns:**
- `ValidationResult`: Result object with decision, cleaned data, and metadata

**Raises:**
- `ValueError`: If DataFrame is empty or invalid
- `TypeError`: If df is not a pandas DataFrame

**Example:**
```python
import pandas as pd

df = pd.read_csv("training_data.csv")
result = validator.validate(df, copy_id="experiment_001", out_dir="outputs")

print(f"Decision: {result.decision}")
if result.is_accepted:
    result.cleaned_data.to_csv("approved_data.csv", index=False)
```

**Side Effects:**
- Creates output directory if it doesn't exist
- Writes validation report to `{out_dir}/{copy_id}/validation_report.json`
- Writes cleaned data to `{out_dir}/{copy_id}/cleaned_data.csv`
- Writes transform summary to `{out_dir}/{copy_id}/transform_summary.json`

---

#### validate_batch()

```python
validate_batch(dataframes, out_dir="outputs")
```

Validate multiple DataFrames in a batch operation.

**Parameters:**
- `dataframes` (Dict[str, pd.DataFrame]): Dictionary mapping copy_id → DataFrame
- `out_dir` (str, optional): Output directory for all results. Default: `"outputs"`

**Returns:**
- `Dict[str, ValidationResult]`: Dictionary mapping copy_id → ValidationResult

**Raises:**
- `ValueError`: If dataframes dict is empty
- `TypeError`: If any value is not a pandas DataFrame

**Example:**
```python
dataframes = {
    "batch_001": pd.read_csv("data_001.csv"),
    "batch_002": pd.read_csv("data_002.csv"),
    "batch_003": pd.read_csv("data_003.csv")
}

results = validator.validate_batch(dataframes, out_dir="batch_outputs")

for copy_id, result in results.items():
    print(f"{copy_id}: {result.decision}")
```

**Performance Note:** Sequential processing. For parallel batch processing, use `BatchProcessor` class.

---

#### get_summary()

```python
get_summary(results)
```

Get summary statistics from batch validation results.

**Parameters:**
- `results` (Dict[str, ValidationResult]): Results dictionary from `validate_batch()`

**Returns:**
- `dict`: Summary statistics with the following keys:
  - `total` (int): Total number of datasets
  - `accepted` (int): Number of ACCEPT decisions
  - `rejected` (int): Number of REJECT decisions
  - `quarantined` (int): Number of QUARANTINE decisions
  - `acceptance_rate` (float): Percentage of accepted datasets (0-100)

**Example:**
```python
results = validator.validate_batch(dataframes)
summary = validator.get_summary(results)

print(f"Total: {summary['total']}")
print(f"Accepted: {summary['accepted']} ({summary['acceptance_rate']:.1f}%)")
print(f"Rejected: {summary['rejected']}")
print(f"Quarantined: {summary['quarantined']}")
```

---

### Context Manager Support

`LeakageValidator` supports context manager protocol for resource cleanup.

**Example:**
```python
with LeakageValidator() as validator:
    result = validator.validate(df)
    if result.is_accepted:
        print("✅ Approved")
# Automatic cleanup on exit
```

---

## ValidationResult

Result object returned by `LeakageValidator.validate()`.

### Properties

#### is_accepted

```python
@property
def is_accepted(self) -> bool
```

Returns `True` if decision is "ACCEPT", `False` otherwise.

**Example:**
```python
if result.is_accepted:
    # Proceed with ML training
    model.fit(result.cleaned_data)
```

---

#### is_rejected

```python
@property
def is_rejected(self) -> bool
```

Returns `True` if decision is "REJECT", `False` otherwise.

**Example:**
```python
if result.is_rejected:
    print(f"Quality issues: {result.reason_codes}")
    # Fix data and retry
```

---

#### is_quarantined

```python
@property
def is_quarantined(self) -> bool
```

Returns `True` if decision is "QUARANTINE", `False` otherwise.

**Example:**
```python
if result.is_quarantined:
    print("⚠️ Security review required")
    # Do NOT use for training
```

---

#### decision

```python
result.decision -> str
```

Validation decision: `"ACCEPT"`, `"REJECT"`, or `"QUARANTINE"`.

**Example:**
```python
if result.decision == "ACCEPT":
    save_to_training_set(result.cleaned_data)
elif result.decision == "REJECT":
    log_quality_issues(result.reason_codes)
else:  # QUARANTINE
    alert_security_team(result.report)
```

---

#### cleaned_data

```python
result.cleaned_data -> pd.DataFrame
```

Transformed DataFrame after applying all policy transformations.

**Transformations applied:**
- Tokenization (TOKENIZE_DET)
- Bucketing (BUCKET)
- Generalization (GENERALIZE)
- Field removal (DROP)
- Deduplication

**Example:**
```python
print(f"Original columns: {list(df.columns)}")
print(f"Cleaned columns: {list(result.cleaned_data.columns)}")

# Save cleaned data
result.cleaned_data.to_csv("approved_data.csv", index=False)
```

**Note:** Available regardless of decision (ACCEPT/REJECT/QUARANTINE).

---

#### reason_codes

```python
result.reason_codes -> List[str]
```

List of reasons for the decision.

**Common reason codes:**
- `MISSING_TOO_HIGH` - Excessive missing values
- `DUPLICATE_RATE_TOO_HIGH` - Too many duplicate rows
- `RANGE_VIOLATIONS` - Values outside allowed ranges
- `ENUM_VIOLATIONS` - Invalid categorical values
- `POSTCHECK_FAIL` - Sensitive patterns remain after transformation
- `FORBIDDEN_FOUND` - Forbidden columns or patterns detected

**Example:**
```python
if result.is_rejected:
    for code in result.reason_codes:
        print(f"Issue: {code}")
        
        if code == "MISSING_TOO_HIGH":
            print(f"  Missing rates: {result.metrics['missing_rates_critical']}")
```

---

#### metrics

```python
@property
def metrics(self) -> dict
```

Validation metrics with detailed statistics.

**Keys:**
- `missing_rates_critical` (dict): Missing value percentages for critical fields
- `missing_rates_noncritical` (dict): Missing value percentages for non-critical fields
- `duplicate_rate` (float): Percentage of duplicate rows
- `range_violations` (int): Number of range constraint violations
- `enum_violations` (int): Number of enum constraint violations

**Example:**
```python
metrics = result.metrics

print(f"Duplicate rate: {metrics['duplicate_rate']:.2f}%")
print(f"Range violations: {metrics['range_violations']}")

# Check critical field missing rates
for field, rate in metrics['missing_rates_critical'].items():
    print(f"{field}: {rate:.2f}% missing")
```

---

#### transform_summary

```python
@property
def transform_summary(self) -> dict
```

Summary of transformations applied during validation.

**Keys:**
- `tokenized_fields_count` (dict): Count of tokenized values per field
- `dropped_columns` (list): Columns removed via DROP action
- `derived_fields_created` (list): New fields created (e.g., age_bucket)
- `duplicates_removed` (int): Number of duplicate rows removed
- `canonical_mapping_count` (int): Number of field name aliases resolved
- `normalization_changes_count` (int): Number of normalization operations
- `forbidden_found` (bool): Whether forbidden patterns were detected
- `forbidden_hits` (list): Specific forbidden column/pattern matches

**Example:**
```python
ts = result.transform_summary

print(f"Tokenized {sum(ts['tokenized_fields_count'].values())} fields")
print(f"Dropped columns: {ts['dropped_columns']}")
print(f"Derived fields: {ts['derived_fields_created']}")
print(f"Duplicates removed: {ts['duplicates_removed']}")
```

---

#### report

```python
result.report -> dict
```

Full validation report with all details. Contains all metrics, summaries, and intermediate results.

**Example:**
```python
import json

# Save full report
with open("validation_report.json", "w") as f:
    json.dump(result.report, f, indent=2)
```

---

### Methods

#### to_dict()

```python
to_dict() -> dict
```

Convert ValidationResult to dictionary for serialization.

**Returns:**
- `dict`: Dictionary with keys:
  - `decision` (str)
  - `reason_codes` (list)
  - `metrics` (dict)
  - `transform_summary` (dict)

**Example:**
```python
result_dict = result.to_dict()

import json
json.dump(result_dict, open("result.json", "w"), indent=2)
```

---

## DataOrchestrator

Orchestrates validation with automatic retry logic for handling REJECT decisions.

### Constructor

```python
DataOrchestrator(policy_dir="policy/versions/v1", max_retries=3)
```

**Parameters:**
- `policy_dir` (str, optional): Path to policy directory. Default: `"policy/versions/v1"`
- `max_retries` (int, optional): Maximum number of regeneration attempts. Default: 3

**Returns:**
- `DataOrchestrator` instance

**Example:**
```python
from leakage_agent.orchestrator import DataOrchestrator

orchestrator = DataOrchestrator(
    policy_dir="policy/versions/v1",
    max_retries=5  # Allow up to 5 retry attempts
)
```

---

### Methods

#### process_with_retry()

```python
process_with_retry(df, copy_id, regenerator=None, out_dir="outputs")
```

Process data with automatic retry on REJECT decisions.

**Parameters:**
- `df` (pd.DataFrame): Input DataFrame
- `copy_id` (str): Dataset identifier
- `regenerator` (Callable, optional): Function that takes `(df, guidance_dict)` and returns fixed DataFrame. If None, no retry on REJECT.
- `out_dir` (str, optional): Output directory. Default: `"outputs"`

**Returns:**
- `ValidationResult`: Final validation result after retries

**Raises:**
- `ValueError`: If DataFrame is empty
- `TypeError`: If regenerator is not callable

**Workflow:**
1. Validate data
2. If ACCEPT or QUARANTINE → return result
3. If REJECT and regenerator provided:
   - Get retry guidance based on reason codes
   - Call regenerator with guidance
   - Retry validation
   - Repeat up to `max_retries` times
4. Return final result

**Example:**
```python
def my_regenerator(df, guidance_dict):
    """Fix data based on retry guidance."""
    df_fixed = df.copy()
    guidance = guidance_dict.get('guidance', {})
    
    # Fix missing values
    if 'reduce_missing_rate' in guidance:
        for field in guidance['reduce_missing_rate']:
            df_fixed[field] = df_fixed[field].fillna('default')
    
    # Fix range violations
    if 'fix_range_violations' in guidance:
        df_fixed['amount'] = df_fixed['amount'].clip(0, 1000000)
    
    return df_fixed

result = orchestrator.process_with_retry(
    df=my_dataframe,
    copy_id="exp_001",
    regenerator=my_regenerator,
    out_dir="outputs"
)

print(f"Final decision: {result.decision}")
print(f"Attempts: {result.report.get('attempt_count', 1)}")
```

---

#### should_retry()

```python
should_retry(attempt, decision, reason_codes)
```

Determine if retry is warranted based on current attempt and decision.

**Parameters:**
- `attempt` (int): Current attempt number (0-indexed)
- `decision` (str): Validation decision
- `reason_codes` (list): Reason codes from validation

**Returns:**
- `bool`: True if should retry, False otherwise

**Retry Logic:**
- Never retry on ACCEPT or QUARANTINE (only REJECT is retriable)
- Only retry if attempt < max_retries
- Only retry for fixable issues (not schema failures)

**Example:**
```python
should_retry = orchestrator.should_retry(
    attempt=1,
    decision="REJECT",
    reason_codes=["MISSING_TOO_HIGH"]
)

if should_retry:
    print("Attempting regeneration...")
```

---

#### get_retry_guidance()

```python
get_retry_guidance(reason_codes)
```

Get actionable guidance for data regeneration based on rejection reasons.

**Parameters:**
- `reason_codes` (list): Reason codes from ValidationResult

**Returns:**
- `RetryGuidance`: Object with guidance dictionary

**Guidance keys:**
- `reduce_missing_rate` (list): Fields with high missing rates
- `fix_range_violations` (list): Fields with range violations
- `fix_enum_violations` (list): Fields with enum violations
- `remove_duplicates` (bool): Whether to deduplicate

**Example:**
```python
result = validator.validate(df)

if result.is_rejected:
    guidance = orchestrator.get_retry_guidance(result.reason_codes)
    print(f"Guidance: {guidance.to_dict()}")
    
    # Apply fixes based on guidance
    if 'reduce_missing_rate' in guidance.guidance:
        for field in guidance.guidance['reduce_missing_rate']:
            df[field] = df[field].fillna('default')
```

---

## LineageTracker

Track data lineage and provenance for audit purposes.

### Constructor

```python
LineageTracker(storage_backend=None)
```

**Parameters:**
- `storage_backend` (str, optional): Path to JSON file for persistent storage. If None, lineage is kept in-memory only.

**Returns:**
- `LineageTracker` instance

**Example:**
```python
from leakage_agent.lineage import LineageTracker

# In-memory tracking
tracker = LineageTracker()

# Persistent tracking
tracker = LineageTracker(storage_backend="lineage_db.json")
```

---

### Methods

#### record_ingestion()

```python
record_ingestion(copy_id, source_info)
```

Record where data came from (data provenance).

**Parameters:**
- `copy_id` (str): Dataset identifier
- `source_info` (dict): Source metadata with keys:
  - `source_type` (str): e.g., "synthetic", "real_data", "augmented"
  - `generator_model` (str, optional): Generator used
  - `parent_dataset` (str, optional): Parent dataset ID
  - Any additional custom fields

**Example:**
```python
tracker.record_ingestion("copy_001", {
    "source_type": "synthetic",
    "generator_model": "SDV_CTGAN",
    "parent_dataset": "real_data_v2",
    "generation_config": {"epochs": 100, "batch_size": 500}
})
```

---

#### record_transformation()

```python
record_transformation(copy_id, stage, details, data_hash=None)
```

Record a transformation stage in the pipeline.

**Parameters:**
- `copy_id` (str): Dataset identifier
- `stage` (str): Transformation stage name (e.g., "canonicalize", "tokenize")
- `details` (dict): Stage-specific details
- `data_hash` (str, optional): Hash of data after this transformation

**Example:**
```python
tracker.record_transformation("copy_001", "canonicalize", {
    "mappings_applied": 5,
    "collisions": 0
})

tracker.record_transformation("copy_001", "tokenize", {
    "fields_tokenized": ["user_id", "email"],
    "tokenization_method": "SHA256"
})
```

---

#### record_version()

```python
record_version(copy_id, df, stage, metadata=None)
```

Record a versioned snapshot of the data.

**Parameters:**
- `copy_id` (str): Dataset identifier
- `df` (pd.DataFrame): Current DataFrame state
- `stage` (str): Stage name for this version
- `metadata` (dict, optional): Additional version metadata

**Example:**
```python
# Record version after transformations
tracker.record_version(
    copy_id="copy_001",
    df=cleaned_df,
    stage="post_transform",
    metadata={"decision": "ACCEPT"}
)
```

---

#### compute_data_hash()

```python
compute_data_hash(df)
```

Compute deterministic SHA-256 hash of DataFrame for versioning.

**Parameters:**
- `df` (pd.DataFrame): DataFrame to hash

**Returns:**
- `str`: SHA-256 hash string

**Example:**
```python
hash1 = tracker.compute_data_hash(df1)
hash2 = tracker.compute_data_hash(df2)

if hash1 == hash2:
    print("Identical data")
```

**Note:** Same data content produces same hash, regardless of DataFrame creation method.

---

#### get_lineage()

```python
get_lineage(copy_id)
```

Retrieve full lineage history for a dataset.

**Parameters:**
- `copy_id` (str): Dataset identifier

**Returns:**
- `dict` or `None`: Lineage record with keys:
  - `copy_id`
  - `created_at`
  - `source_info`
  - `transformations` (list)
  - `versions` (list)

**Example:**
```python
lineage = tracker.get_lineage("copy_001")

print(f"Source: {lineage['source_info']}")
print(f"Transformations: {len(lineage['transformations'])}")

for transform in lineage['transformations']:
    print(f"  {transform['stage']}: {transform['details']}")
```

---

#### get_lineage_summary()

```python
get_lineage_summary(copy_id)
```

Get summarized lineage information.

**Parameters:**
- `copy_id` (str): Dataset identifier

**Returns:**
- `dict` or `None`: Summary with keys:
  - `copy_id`
  - `source_type`
  - `created_at`
  - `transformation_count`
  - `version_count`
  - `latest_version`

**Example:**
```python
summary = tracker.get_lineage_summary("copy_001")

print(f"Dataset: {summary['copy_id']}")
print(f"Source: {summary['source_type']}")
print(f"Transformations: {summary['transformation_count']}")
print(f"Versions: {summary['version_count']}")
```

---

## BatchProcessor

Process multiple datasets with parallel execution and progress tracking.

### Constructor

```python
BatchProcessor(pipeline=None, max_workers=4, verbose=True)
```

**Parameters:**
- `pipeline` (Pipeline, optional): Pipeline instance. Creates new one if None.
- `max_workers` (int, optional): Number of parallel workers. Default: 4
- `verbose` (bool, optional): Show progress bar (requires tqdm). Default: True

**Returns:**
- `BatchProcessor` instance

**Example:**
```python
from leakage_agent.batch_processor import BatchProcessor

processor = BatchProcessor(
    max_workers=8,      # Use 8 CPU cores
    verbose=True        # Show progress bar
)
```

---

### Methods

#### process_directory()

```python
process_directory(input_dir, out_dir="outputs", pattern="*.csv")
```

Process all matching files in a directory.

**Parameters:**
- `input_dir` (str): Directory containing input CSV files
- `out_dir` (str, optional): Output directory. Default: `"outputs"`
- `pattern` (str, optional): File glob pattern. Default: `"*.csv"`

**Returns:**
- `dict`: Summary with keys:
  - `total` (int): Total files processed
  - `accepted` (int): Files with ACCEPT decision
  - `rejected` (int): Files with REJECT decision
  - `quarantined` (int): Files with QUARANTINE decision
  - `failed` (int): Files with processing errors

**Example:**
```python
summary = processor.process_directory(
    input_dir="data/candidates/",
    out_dir="batch_outputs",
    pattern="train_*.csv"
)

print(f"Processed: {summary['total']}")
print(f"Accepted: {summary['accepted']} ({summary['accepted']/summary['total']*100:.1f}%)")
print(f"Rejected: {summary['rejected']}")
print(f"Quarantined: {summary['quarantined']}")
print(f"Failed: {summary['failed']}")
```

**Performance:** Uses `ProcessPoolExecutor` for true parallel processing (not GIL-limited).

---

## Pipeline

Low-level pipeline class for direct access to validation stages. Most users should use `LeakageValidator` instead.

### Constructor

```python
Pipeline(policy_dir="policy/versions/v1", lineage_tracker=None)
```

**Parameters:**
- `policy_dir` (str, optional): Path to policy directory. Default: `"policy/versions/v1"`
- `lineage_tracker` (LineageTracker, optional): Shared lineage tracker instance

**Example:**
```python
from leakage_agent.pipeline import Pipeline
from leakage_agent.lineage import LineageTracker

tracker = LineageTracker()
pipeline = Pipeline(
    policy_dir="policy/versions/v1",
    lineage_tracker=tracker
)
```

---

### Methods

#### run()

```python
run(df, out_dir="outputs", copy_id="default", source_info=None)
```

Run the 9-stage validation pipeline.

**Parameters:**
- `df` (pd.DataFrame): Input DataFrame
- `out_dir` (str, optional): Output directory. Default: `"outputs"`
- `copy_id` (str, optional): Dataset identifier. Default: `"default"`
- `source_info` (dict, optional): Source information for lineage tracking

**Returns:**
- `tuple`: `(cleaned_df, report)`
  - `cleaned_df` (pd.DataFrame): Transformed DataFrame
  - `report` (dict): Full validation report

**Example:**
```python
cleaned_df, report = pipeline.run(
    df=my_dataframe,
    out_dir="outputs",
    copy_id="pipeline_test",
    source_info={"source": "manual_upload"}
)

print(f"Decision: {report['decision']}")
print(f"Cleaned rows: {len(cleaned_df)}")
```

**Pipeline Stages (in order):**
1. Canonicalize - Map field aliases
2. Forbidden Scan - Check for secrets
3. Normalize - Apply normalization rules
4. Deduplicate - Remove exact duplicates
5. Transform - Apply TOKENIZE/BUCKET/GENERALIZE/DROP
6. Postcheck - Scan for leaked patterns
7. Metrics - Calculate validation metrics
8. Decision - Make ACCEPT/REJECT/QUARANTINE decision
9. Write Outputs - Save reports and cleaned data

---

## Error Handling

All API methods may raise standard Python exceptions:

**Common Exceptions:**
- `FileNotFoundError`: Policy files missing
- `yaml.YAMLError`: Malformed configuration
- `ValueError`: Invalid input (empty DataFrame, etc.)
- `TypeError`: Wrong argument type
- `KeyError`: Missing required configuration key

**Example:**
```python
try:
    validator = LeakageValidator(policy_dir="invalid/path")
except FileNotFoundError as e:
    print(f"Policy not found: {e}")
except yaml.YAMLError as e:
    print(f"Invalid YAML: {e}")

try:
    result = validator.validate(empty_df)
except ValueError as e:
    print(f"Validation error: {e}")
```

---

## Type Hints

All API methods include type hints for better IDE support:

```python
from typing import Dict, Optional
import pandas as pd

def validate(
    self,
    df: pd.DataFrame,
    copy_id: Optional[str] = None,
    out_dir: str = "outputs"
) -> ValidationResult:
    ...
```

Use type checkers like `mypy` for static type checking:
```bash
mypy your_script.py
```

---

## See Also

- [README.md](README.md) - Overview and quick start
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common errors and fixes
- [CONFIGURATION.md](CONFIGURATION.md) - Policy configuration guide
- [examples/](examples/) - Runnable code examples
