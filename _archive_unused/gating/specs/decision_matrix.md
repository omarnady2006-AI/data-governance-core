# Decision Matrix

This document defines the logic for determining the final decision (ACCEPT, REJECT, or QUARANTINE) based on computed metrics, thresholds, and policy violations.

## Decision Rules

| Condition | Decision | Reason Code |
|-----------|----------|-------------|
| Secret detected or Postcheck pattern match (`postcheck_ok == false`) | **QUARANTINE** | `SECRET_FOUND` or `POSTCHECK_FAIL` |
| Missing label values found (`missing_rate_by_field["label"] > 0`) | **REJECT** | `MISSING_TOO_HIGH` |
| Duplicates rate exceeds limit (`duplicates_rate > duplicate_rate_max`) | **REJECT** | `DUPLICATES_TOO_HIGH` |
| Range violations exceed field-specific limits | **REJECT** | `RANGE_VIOLATION_LIMIT_EXCEEDED` |
| Enum violations exceed field-specific limits | **REJECT** | `ENUM_VIOLATION_LIMIT_EXCEEDED` |
| Schema validation fails (`schema_ok == false`) | **REJECT** | `SCHEMA_INVALID` |
| All checks pass within thresholds | **ACCEPT** | `PASS` |

## Rule Hierarchy and Logic

The gating engine evaluates rules in the following order of precedence:

1.  **QUARANTINE**: If any high-risk patterns or secrets are identified during the postcheck phase, the data is immediately moved to quarantine for manual review, regardless of other metrics.
2.  **REJECT**: If the quarantine conditions are not met, the engine checks against rejection thresholds defined in `thresholds.yaml`. Any single violation results in a REJECT decision.
3.  **ACCEPT**: Data is accepted only if it satisfies all validation criteria and falls within all safety and quality thresholds.

## Reason Code Mapping

Reason codes are retrieved from `reason_codes.yaml` to provide standardized error reporting in the `audit_report`.
