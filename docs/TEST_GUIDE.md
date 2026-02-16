# Comprehensive Testing Guide

Run the following commands in order and report results:

---

## 1️⃣ Environment Check

```bash
python verify_env.py
```

**Expected**: Message "deps ok" and library versions

---

## 2️⃣ Unit Tests

```bash
python run_unit_tests.py
```

**Expected**: "Tests passed." + report in `outputs/test_report_unit.txt`

---

## 3️⃣ Smoke Tests

### API Smoke Test
```bash
python run_api_smoke.py
```

### CLI Smoke Test
```bash
python run_cli_smoke.py
```

### Batch Processing Test
```bash
python run_batch_smoke.py
```

**Expected**: Each test completes without errors

---

## 4️⃣ Governance Core Examples

### Public API Example
```bash
python examples/public_api_example.py
```

### Threat Mapping Example
```bash
python examples/threat_mapping_example.py
```

### Threat Aggregation Example
```bash
python examples/threat_aggregation_example.py
```

### End-to-End Example
```bash
python examples/end_to_end_example.py
```

**Expected**: Each example displays results successfully

---

## 5️⃣ Security and Edge Case Tests

```bash
python examples/test_edge_cases.py
```

```bash
python examples/test_jailbreak_prevention.py
```

```bash
python examples/test_threat_aggregation.py
```

```bash
python examples/test_threat_mapping_enhancements.py
```

**Expected**: All tests pass successfully

---

## Notes

- If any test fails, send the complete error message
- If it succeeds, just write "✅ Passed" or copy the last two lines of output
- Make sure you're in the project folder before running commands:
  ```bash
  cd C:\Users\Admin\Downloads\Compressed\outside-agent-main
  ```

---

## Quick Run (All Commands At Once)

You can copy and paste this into PowerShell:

```powershell
cd C:\Users\Admin\Downloads\Compressed\outside-agent-main

Write-Host "`n=== 1. فحص البيئة ===" -ForegroundColor Cyan
python verify_env.py

Write-Host "`n=== 2. اختبارات الوحدات ===" -ForegroundColor Cyan
python run_unit_tests.py

Write-Host "`n=== 3. API Smoke ===" -ForegroundColor Cyan
python run_api_smoke.py

Write-Host "`n=== 4. CLI Smoke ===" -ForegroundColor Cyan
python run_cli_smoke.py

Write-Host "`n=== 5. Batch Smoke ===" -ForegroundColor Cyan
python run_batch_smoke.py

Write-Host "`n=== 6. Public API Example ===" -ForegroundColor Cyan
python examples/public_api_example.py

Write-Host "`n=== 7. Threat Mapping Example ===" -ForegroundColor Cyan
python examples/threat_mapping_example.py

Write-Host "`n=== 8. Threat Aggregation Example ===" -ForegroundColor Cyan
python examples/threat_aggregation_example.py

Write-Host "`n=== 9. End-to-End Example ===" -ForegroundColor Cyan
python examples/end_to_end_example.py

Write-Host "`n=== 10. Edge Cases Test ===" -ForegroundColor Cyan
python examples/test_edge_cases.py

Write-Host "`n=== 11. Jailbreak Prevention Test ===" -ForegroundColor Cyan
python examples/test_jailbreak_prevention.py

Write-Host "`n=== 12. Threat Aggregation Test ===" -ForegroundColor Cyan
python examples/test_threat_aggregation.py

Write-Host "`n=== 13. Threat Mapping Enhancements Test ===" -ForegroundColor Cyan
python examples/test_threat_mapping_enhancements.py

Write-Host "`n=== ✅ اكتملت جميع الاختبارات ===" -ForegroundColor Green
```
