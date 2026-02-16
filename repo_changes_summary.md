# Repo Changes Summary

## Step 1 — Requirement Verification

All 5 capabilities verified and mapped to source. `scripts/invariance_proofs.py` passes (ALL INVARIANT: true).

See: `requirements_checklist.md`

## Step 2 — Safe Dead Code Removal

Moved 11 items to `_archive_unused/`:
- `leakage_agent/` — legacy separate package
- `gating/`, `transform/` — stub specs
- `validation_experiments.py` — uses obsolete API
- `Testing_Without_LLM.py`, `Testing_LLM.py` — dev utilities
- `example_outputs/`, `outputs/`, `tmp_smoke/`, `audit_logs/`, `audit_report.json` — stale outputs

Deleted: `__pycache__/` (all), `pytest-cache-files-*/` (3 dirs)

No unused functions found in active files.

See: `cleanup_report.md`

## Step 3 — Project Structure Reorganization

| From | To |
|------|----|
| `invariance_proofs.py` | `scripts/invariance_proofs.py` |
| `adversarial_audit.py` | `scripts/adversarial_audit.py` |
| `domias_validation.py` | `scripts/domias_validation.py` |
| `governance_core/tests/test_evidence_metrics.py` | `tests/test_evidence_metrics.py` |
| `examples/test_*.py` (4 files) | `tests/test_*.py` |
| `LLM_TESTING_GUIDE.md` | `docs/LLM_TESTING_GUIDE.md` |
| `TEST_GUIDE.md` | `docs/TEST_GUIDE.md` |

Import paths updated in all moved files.

See: `tree_structure.txt`

## Step 4 — README Rewrite

Complete rewrite with: problem statement, mathematical guarantees (ECDF + CvM + invariance proof), quickstart (10 lines), signal table, honest limitations section, repo structure.

## Step 5 — Final Validation

| Test | Result |
|------|--------|
| `scripts/invariance_proofs.py` | ✅ ALL INVARIANT: true |
| Import smoke test | ✅ OK |
| `scripts/domias_validation.py` | ✅ OK |
| `scripts/adversarial_audit.py` | ⚠️ 4/5 PASS (pre-existing) |

The adversarial audit's distribution_shift section result is pre-existing and unrelated to structural changes. No regressions introduced.
