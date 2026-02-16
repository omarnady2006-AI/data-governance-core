# Transform Integration Contract

This document defines the strict contract for the data transformation pipeline interface.

---

## Input Specification

### Required Inputs

- **candidate_dataset_copy** — A full copy of the candidate dataset to be transformed
  - Must be a complete, unmodified clone of the source data
  - No in-place mutations allowed on the original dataset

- **policy_pack_references** — References to applicable policy configurations
  - Normalization rules
  - Privacy policies (PII handling, redaction rules)
  - Cleaning specifications
  - Forbidden value lists

---

## Output Specification

The transformation pipeline produces the following output objects:

### 1. `cleaned_copy` (Required)

The fully processed dataset after all transformation stages.

| Stage | Description |
|-------|-------------|
| **Normalization** | Field values standardized per policy rules (casing, whitespace, encoding) |
| **Privacy** | Sensitive/PII fields redacted, masked, or removed per privacy policy |
| **Cleaning** | Invalid entries removed, formats corrected, outliers handled |

**Contract:**
- Must be a new object; original `candidate_dataset_copy` remains untouched
- All rows must pass validation or be explicitly removed
- No raw sensitive values may remain unless policy explicitly permits

---

### 2. `transform_summary` (Required)

A metadata object summarizing all transformation operations performed.

| Field | Type | Description |
|-------|------|-------------|
| `tokenized_counts_by_field` | `dict[str, int]` | Count of tokenized values per field |
| `dropped_columns` | `list[str]` | Names of columns removed during cleaning |
| `derived_fields_created` | `list[str]` | Names of new fields generated during transformation |
| `duplicates_removed` | `int` | Count of duplicate rows removed |
| `missing_label_count` | `int` | Count of rows with missing target labels |
| `forbidden_found` | `bool` | Whether any forbidden values were detected |
| `forbidden_hits` | `int` | Total count of forbidden value occurrences |
| `normalization_changes_count` | `int` | Total number of normalization modifications applied |
| `canonicalization_mappings_count` | `int` | Count of distinct canonicalization mappings used |

---

### 3. `transform_events` (Optional)

A list of discrete transformation events for audit/debugging purposes.

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `str` | Category of transformation (`normalize`, `redact`, `drop`, `derive`, etc.) |
| `field_name` | `str` | Target field affected |
| `row_count` | `int` | Number of rows impacted |
| `timestamp` | `str` | ISO 8601 timestamp of operation |
| `policy_ref` | `str` | Reference to the policy rule applied |

---

## Security & Privacy Rules

> [!CAUTION]
> **No raw sensitive values in summaries or logs.**

- **Forbidden:** Logging, storing, or including actual PII, secrets, or forbidden values in `transform_summary` or `transform_events`
- **Required:** Use only counts, hashes, or anonymized identifiers when referencing sensitive data
- **Enforcement:** All outputs must pass a post-transform audit confirming zero sensitive value leakage

### Examples of Violations

- ❌ `"forbidden_value": "john.doe@email.com"`
- ❌ `"removed_ssn": "123-45-6789"`
- ❌ Logging raw field values that contain PII

### Examples of Compliance

- ✅ `"forbidden_hits": 3`
- ✅ `"redacted_field": "email"`
- ✅ `"pii_fields_processed": ["email", "phone", "ssn"]`

---

## Contract Enforcement

1. **Input Validation** — Reject transformations if `candidate_dataset_copy` or `policy_pack_references` are missing or malformed
2. **Output Validation** — All required fields in `cleaned_copy` and `transform_summary` must be present
3. **Immutability** — Original input dataset must remain unmodified after transformation
4. **Audit Trail** — If `transform_events` is generated, it must be complete and consistent with `transform_summary` counts
