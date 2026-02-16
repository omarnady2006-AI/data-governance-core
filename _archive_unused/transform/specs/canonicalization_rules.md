# Canonicalization Rules

This document specifies how to map raw dataset column names to canonical names using `policy.yaml.field_name_aliases`.

---

## Policy Configuration

Aliases are defined in `policy.yaml` under `field_name_aliases`:

```yaml
field_name_aliases:
  email:
    - "email_address"
    - "e-mail"
    - "Email"
    - "user_email"
  phone:
    - "phone_number"
    - "telephone"
    - "Phone"
    - "mobile"
  first_name:
    - "firstName"
    - "first name"
    - "fname"
```

---

## Matching Strategy

Column matching follows this precedence order:

### Step 1: Normalize Column Name

```
normalize(column_name):
    1. Trim leading/trailing whitespace
    2. Replace underscores with spaces
    3. Collapse multiple spaces to single space
    4. Convert to lowercase
```

### Step 2: Match Against Aliases

| Priority | Method | Example |
|----------|--------|---------|
| 1 | Exact alias match (after normalization) | `"e-mail"` → `email` |
| 2 | Case-insensitive match | `"EMAIL"` → `email` |
| 3 | Underscore/space equivalence | `"phone_number"` ≡ `"phone number"` |

### Matching Algorithm

```
FOR each raw_column in dataset:
    normalized = normalize(raw_column)
    
    FOR each canonical_name, aliases in field_name_aliases:
        FOR each alias in aliases:
            IF normalize(alias) == normalized:
                RETURN canonical_name
    
    # No match found
    RETURN raw_column (unchanged)
```

---

## Collision Rules

When two or more raw columns map to the same canonical name:

### Resolution Order

| Priority | Rule | Action |
|----------|------|--------|
| 1 | First non-null wins | Keep first column with non-null values |
| 2 | Column position | If both null or both have values, keep leftmost column |
| 3 | Log collision | Record in `transform_summary.canonicalization_collisions` |

### Collision Handling

```
IF collision_detected:
    kept_column     = select_by_priority(colliding_columns)
    dropped_columns = colliding_columns - kept_column
    
    log_warning(
        "Collision: columns {dropped} mapped to '{canonical}', kept '{kept}'"
    )
    
    ADD dropped_columns to transform_summary.dropped_columns
```

> [!WARNING]
> Collisions indicate upstream data quality issues. Flag for review.

---

## Unknown Column Handling

Columns with no matching alias:

| Condition | Action |
|-----------|--------|
| Column not in forbidden list | **KEEP** with original name |
| Column in forbidden list | **DROP** immediately |
| Unknown column kept | Add to `transform_summary.unknown_columns_kept` |

### Unknown Column Tracking

```yaml
# In transform_summary
unknown_columns_kept:
  - "legacy_field_1"
  - "temp_data"
  - "misc_notes"
```

> [!NOTE]
> Unknown columns are preserved to prevent data loss. Review periodically to update aliases.

---

## Output Mapping Table Format

The canonicalization stage produces a mapping table:

### Format: `canonicalization_map`

| Field | Type | Description |
|-------|------|-------------|
| `raw_name` | string | Original column name from source |
| `canonical_name` | string | Mapped canonical name (or original if unknown) |
| `match_type` | enum | `exact`, `case_insensitive`, `normalized`, `none` |
| `was_collision` | boolean | True if this column was involved in a collision |

### Example Output

```json
{
  "canonicalization_map": [
    {
      "raw_name": "Email_Address",
      "canonical_name": "email",
      "match_type": "normalized",
      "was_collision": false
    },
    {
      "raw_name": "phone_number",
      "canonical_name": "phone",
      "match_type": "exact",
      "was_collision": false
    },
    {
      "raw_name": "Phone",
      "canonical_name": "phone",
      "match_type": "case_insensitive",
      "was_collision": true
    },
    {
      "raw_name": "legacy_field_1",
      "canonical_name": "legacy_field_1",
      "match_type": "none",
      "was_collision": false
    }
  ]
}
```

---

## Summary Integration

After canonicalization, update `transform_summary`:

```json
{
  "canonical_mapping_count": 45,
  "canonicalization_collisions": 2,
  "unknown_columns_kept": ["legacy_field_1", "temp_data"]
}
```

---

## Validation Checklist

- [ ] All policy aliases normalized before matching
- [ ] Collisions logged with affected column names
- [ ] Unknown columns preserved unless forbidden
- [ ] Mapping table generated for audit trail
- [ ] No data loss from unintended drops
