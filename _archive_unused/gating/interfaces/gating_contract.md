# Gating Contract

This document defines the interface for the gating module, specifying required inputs, outputs, and decision logic.

## Inputs

The following inputs are required for the gating process:

- **cleaned_copy**: The processed and normalized content.
- **transform_summary**: A summary of transformations applied during the cleaning phase.
- **thresholds.yaml**: Configuration file defining numerical limits for acceptance.
- **reason_codes.yaml**: Mapping of validation failures to specific reason codes.
- **policy.yaml**: Postcheck policy definitions and rules.

## Outputs

The gating process produces the following outputs:

- **metrics**: Quantitative data collected during validation.
- **decision**: The final result of the gating process (ACCEPT, REJECT, or QUARANTINE).
- **reason_codes**: A list of codes indicating specific reasons for the decision.
- **audit_report**: A detailed log of the evaluation for compliance and debugging.

## Decision Conditions

### ACCEPT
- All mandatory validation checks pass.
- Metrics are within the limits defined in `thresholds.yaml`.
- No policy violations detected in `policy.yaml`.

### REJECT
- Critical validation failures occur.
- Metrics exceed maximum allowable thresholds for rejection.
- Explicit policy violations that mandate immediate refusal.

### QUARANTINE
- Results are ambiguous or fall within "gray area" thresholds.
- Non-critical validation errors that require manual review.
- Transformation anomalies detected in `transform_summary` that warrant inspection.
