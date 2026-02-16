# Minimum Safe Cleaning v1

## Overview

The **Minimum Safe Cleaning v1** specification defines a lightweight, policy‑driven data cleaning pipeline that operates safely on tabular datasets. It focuses on four core concerns – format normalization, missing value handling, duplicate removal, and validity checking – while staying within the constraints of the existing **Policy Pack**. No new policies are introduced beyond what is already defined.

---

## 1. Format Normalization

- **Trim whitespace** – Leading and trailing spaces are removed from all string fields.
- **Casing** – String values are converted to lower‑case unless a column is explicitly marked as case‑sensitive in the Policy Pack.
- **Date conversion** – All date‑like columns are parsed and converted to ISO‑8601 (`YYYY‑MM‑DD`) format. Invalid dates are left unchanged and later counted as validity violations.

---

## 2. Missing Handling

- **Critical missing label** – The presence of a missing label (e.g., `"?"`, `"NA"`, `"null"`) is considered a **critical** issue. The pipeline counts occurrences in `missing_label_count`.
- **Policy‑driven drop** – If the Policy Pack specifies a threshold for missing labels (e.g., `max_missing_label_fraction`), rows exceeding that threshold are **optionally dropped**. The decision to drop is controlled by the `drop_missing_rows` flag in the cleaning configuration.

---

## 3. Duplicates

- **Exact duplicate rows** – Rows that are identical across **all columns** are identified as duplicates.
- **Removal** – Duplicate rows are removed, keeping the first occurrence.
- **Metric** – The number of rows removed is reported as `duplicates_removed`.

---

## 4. Validity Checks

- **Numeric semantics** – The pipeline does **not** auto‑correct numeric anomalies (e.g., negative amounts where only positives are allowed). Instead, it counts such violations in `numeric_violation_count`.
- **Gating** – If the Policy Pack defines gating thresholds (e.g., `max_negative_amount_fraction`), the cleaning step can abort or flag the dataset when the count exceeds the threshold.
- **No implicit fixes** – All validity issues are reported; corrective actions must be explicitly configured.

---

## 5. Reporting

The cleaning step produces a concise report containing:

- `missing_label_count`
- `duplicates_removed`
- `numeric_violation_count`
- Any policy‑driven actions taken (e.g., rows dropped).

All counts are available for downstream gating logic.

---

*This specification adheres strictly to the existing Policy Pack and does not introduce new policies.*
