# Metrics Specification

This document describes the computation methods for metrics used in the gating process.

## Metric Computations

### Missing Rates
- **Definition**: The percentage of missing values (null, empty strings, or undefined) for each field.
- **Formula**: `(Count of Missing Values / Total Record Count) * 100`
- **Unit**: Percent (%)

### Duplicates Rate
- **Definition**: The percentage of duplicate records within the dataset.
- **Formula**: `((Total Record Count - Unique Record Count) / Total Record Count) * 100`
- **Unit**: Percent (%)

### Range and Enum Violations
- **Range Violations**: The absolute count of records where a numerical field falls outside the specified minimum/maximum bounds in the schema.
- **Enum Violations**: The absolute count of records where a field value does not match any of the allowed values in the specified enumeration.
- **Reporting**: Reported as an object mapping field names to violation counts.

## Schema Status

### schema_ok
- **Definition**: A boolean indicator of whether the dataset structure conforms to the expected schema.
- **Logic**: Returns `true` only if:
    1. All required fields are present.
    2. Data types for all fields match the schema definitions.
    3. Structural integrity of the file (e.g., valid JSON/CSV formatting) is maintained.

## Postcheck Scanning

### Prohibited Patterns
- **Process**: Perform a scan of the `cleaned_copy` AFTER all cleaning and fixing transformations have been applied.
- **Policy**: Use the `prohibited_patterns` list defined in `policy.yaml`.
- **Logic**: Use regular expression matching to identify any remaining sensitive data or unauthorized content.

### postcheck_ok
- **Definition**: A boolean indicator of post-transformation compliance.
- **Logic**: Returns `true` only if `patterns_remaining_count` is 0.
