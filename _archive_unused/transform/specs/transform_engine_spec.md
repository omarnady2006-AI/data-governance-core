# Transform Engine Specification

This document defines the step-by-step implementation requirements for the Transform Engine.

---

## Operation Order

The Transform Engine **MUST** execute operations in the following strict order:

```
1. Canonicalize
2. Forbidden Scan
3. Normalization
4. Privacy Transforms
5. Cleaning
6. Summary Generation
```

> [!IMPORTANT]
> Order is non-negotiable. Each stage depends on the outputs of previous stages.

---

## Stage 1: Canonicalize

**Purpose:** Establish consistent data representation before analysis.

- Apply canonicalization mappings from `policy.yaml`
- Standardize encodings (UTF-8)
- Normalize whitespace (trim, collapse multiple spaces)
- Standardize case where policy specifies
- Track `canonicalization_mappings_count` in summary

---

## Stage 2: Forbidden Scan

**Purpose:** Detect forbidden/secret content before further processing.

| Condition | Action |
|-----------|--------|
| Forbidden content found | Set `forbidden_found: true` |
| | Record affected field names in `forbidden_hits` |
| | Set **quarantine flag** on dataset copy |

> [!CAUTION]
> **Do NOT auto-fix or remove secrets.** Quarantine only. Human review required before proceeding.

- Scan all text fields against forbidden patterns list
- No raw forbidden values in logs or summaries

---

## Stage 3: Normalization

**Purpose:** Standardize field values per policy rules.

- Apply field-specific normalization rules from `policy.yaml`
- Track total modifications in `normalization_changes_count`
- Operations include:
  - Date format standardization
  - Numeric precision normalization
  - Categorical value mapping

---

## Stage 4: Privacy Transforms

**Purpose:** Apply privacy-preserving transformations per field action.

### Field Actions from `policy.yaml`

| Action | Behavior |
|--------|----------|
| `KEEP` | No transformation; retain original value |
| `DROP` | Remove field entirely from output |
| `TOKENIZE_DET` | Replace with deterministic token (see below) |
| `BUCKET` | Replace numeric value with bucket range |
| `GENERALIZE` | Extract/generalize to less specific form |

### Deterministic Tokenization (`TOKENIZE_DET`)

**Requirement:** Same input **MUST** produce same token across all runs.

```
token = HMAC-SHA256(field_value, secret_key) → truncate/encode
```

- Use consistent secret key per dataset/session
- Token length: configurable, default 16 characters
- Track tokenized counts per field in `tokenized_fields_count`

### Generalization Fallback

When `GENERALIZE` fails (e.g., address parsing error):

```
IF generalization_extraction_fails:
    action = DROP
    log_warning("Generalization failed for field X, applying DROP fallback")
```

> [!WARNING]
> Never expose partially parsed or malformed data. DROP is the safe fallback.

---

## Stage 5: Cleaning

**Purpose:** Remove invalid, duplicate, and incomplete records.

### Duplicate Handling

- Identify **exact duplicates** (all field values match)
- Remove duplicates, keeping first occurrence
- Record count in `duplicates_removed`

### Missing Label Handling

| Condition | Action |
|-----------|--------|
| Row has missing target label | Increment `missing_label_count` |
| | **Do NOT fabricate or impute labels** |
| | Retain row (unless policy specifies drop) |

> [!IMPORTANT]
> Labels are ground truth. Never synthesize missing labels.

### Row Dropping

| Reason | Counter |
|--------|---------|
| Missing required fields | `rows_dropped_missing` |
| Invalid/malformed data | `rows_dropped_invalid` |

- Track dropped columns in `dropped_columns`
- Track newly created fields in `derived_fields_created`

---

## Stage 6: Summary Generation

**Purpose:** Produce `transform_summary` object per schema.

Generate all required fields:

```json
{
  "copy_id": "<unique-identifier>",
  "forbidden_found": true|false,
  "forbidden_hits": ["field1", "field2"],
  "canonical_mapping_count": 42,
  "tokenized_fields_count": {"email": 1500, "phone": 1200},
  "dropped_columns": ["ssn", "credit_card"],
  "derived_fields_created": ["age_bucket", "region"],
  "normalization_changes_count": 3200,
  "duplicates_removed": 15,
  "missing_label_count": 8,
  "rows_dropped_missing": 12,
  "rows_dropped_invalid": 5
}
```

---

## Forbidden Content Response

When `forbidden_found == true`:

1. Set quarantine flag on `cleaned_copy`
2. Do **NOT** proceed to downstream consumers automatically
3. Generate summary with `forbidden_found: true` and `forbidden_hits` populated
4. Require manual review before release

```
[Transform Engine] → [Quarantine Queue] → [Human Review] → [Release/Reject]
```

---

## Error Handling

| Error Type | Response |
|------------|----------|
| Policy file missing/invalid | Abort with clear error message |
| Field type mismatch | Log warning, apply DROP to affected field |
| Tokenization key unavailable | Abort (cannot guarantee determinism) |
| Memory/resource exhaustion | Checkpoint progress, fail gracefully |

---

## Validation Checklist

Before marking transformation complete:

- [ ] All stages executed in order
- [ ] No raw sensitive values in summary
- [ ] `transform_summary` validates against schema
- [ ] Quarantine flag set if forbidden content found
- [ ] Deterministic tokenization verified (spot check)
- [ ] Original input dataset unchanged
