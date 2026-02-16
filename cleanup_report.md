# Cleanup Report

## Import Graph (Active Modules)

```
governance_core/__init__.py
├── rule_engine.py
│   ├── metrics/statistical_fidelity.py (→ 3 capabilities)
│   ├── metrics/privacy_risk.py        (→ 2 capabilities)
│   └── data_profiles.py
├── governance_agent.py → llm_provider.py
├── audit_logger.py
├── api.py → threat_mapping.py, threat_aggregation.py
└── cli.py
```

## Moved to `_archive_unused/`

| Item | Type | Reason |
|------|------|--------|
| `leakage_agent/` | directory | Legacy package — separate project not used by `governance_core/` |
| `gating/` | directory | Stub specs/interfaces — no executable code, not imported |
| `transform/` | directory | Stub specs/interfaces — not imported |
| `validation_experiments.py` | file | Uses obsolete API keys — crashes on run |
| `Testing_Without_LLM.py` | file | Tests legacy `leakage_agent`, not `governance_core/` |
| `Testing_LLM.py` | file | Dev utility — tests Ollama availability |
| `example_outputs/` | directory | Empty output directory stubs |
| `outputs/` | directory | Stale runtime outputs |
| `tmp_smoke/` | directory | Temp smoke test artifacts |
| `audit_logs/` | directory | Stale session logs |
| `audit_report.json` | file | Stale audit output |

## Deleted

| Item | Reason |
|------|--------|
| `__pycache__/` (all) | Python bytecode cache |
| `pytest-cache-files-*/` (3 dirs) | Stale pytest temp directories |

## Unused Functions in Active Files

None found — dead helpers `_to_rank` and `_energy_distance` were already removed in the previous distribution_shift rewrite.
