# Postcheck Specification

This document details the requirements and procedures for the post-transformation safety scan (Postcheck).

## Execution Timing
The Postcheck process **must** run after all data transformations, cleaning, and normalization steps have been completed. It operates on the `cleaned_copy` to ensure that no prohibited information remains or was inadvertently introduced during processing.

## Validation Rule
For a dataset to pass Postcheck, the `patterns_remaining_count` must be exactly **0**. Any detected matches result in a `postcheck_ok: false` status and typically trigger a **QUARANTINE** decision.

## Policy Application
The process utilizes the `prohibited_patterns` defined in `policy.yaml`. These patterns are evaluated as regular expressions against the transformed content.

## Avoiding False Positives
To maintain data utility while ensuring privacy, pattern matching must be precise. Special care is required for numeric sequences:

- **Numeric IDs vs. Sensitive Data**: Long numeric strings (such as internal database IDs or product serial numbers) should not be incorrectly flagged as sensitive data (e.g., phone numbers or credit cards).
- **Phone Number Rule**: Phone number patterns should be strictly defined by digit length and common separators. Avoid matching any generic sequence of 7 or more digits unless they conform to telephony standards.
- **Contextual Matching**: Where possible, use word boundaries (`\b`) and anchored expressions to ensure patterns match intended sensitive entities rather than substrings of harmless data.
