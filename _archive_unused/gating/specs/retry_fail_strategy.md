# Retry and Failure Strategy

This document explains the interaction between gating decisions and the system's retry and regeneration mechanisms.

## Gating Feedback Loop

Gating acts as the final validation step before data acceptance. When a dataset fails gating, it triggers upstream recovery processes based on the specific decision.

### REJECT
- **Action**: Triggers immediate regeneration of the specific data unit.
- **Mechanism**: The rejection signal is sent back to the generation/transformation engine with associated reason codes to guide the correction.
- **Goal**: To obtain a compliant version of the record that meets all quality thresholds.

### QUARANTINE
- **Action**: Isolates the data unit for manual review and **simultaneously** triggers a regeneration attempt.
- **Mechanism**: Data is moved to a secure quarantine storage. A new attempt is initiated upstream to produce a clean version while the flagged version awaits human inspection.
- **Goal**: To ensure the pipeline continues with fresh data while preserving the suspicious data for forensic analysis.

## Operational Constraints

Regeneration is bounded by global safety limits to prevent infinite loops and resource exhaustion:

- **max_regenerations_per_copy**: Defines the maximum number of times a single record can be regenerated following a REJECT or QUARANTINE decision.
- **max_total_attempts_factor**: A global multiplier that limits the total number of attempts across the entire batch (e.g., `total_records * factor`).

If these bounds are exceeded, the system will fail the entire batch and log a fatal error.
