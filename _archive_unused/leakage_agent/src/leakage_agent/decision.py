def make_decision(metrics, forbidden_info, config):
    reason_codes = []
    
    # 1. SECRET_FOUND -> QUARANTINE (Highest precedence)
    if forbidden_info["forbidden_found"]:
        reason_codes.append("SECRET_FOUND")
        return "QUARANTINE", reason_codes
    
    # 2. POSTCHECK_FAIL -> QUARANTINE
    if not metrics["postcheck_ok"]:
        reason_codes.append("POSTCHECK_FAIL")
        return "QUARANTINE", reason_codes
        
    # 3. SCHEMA_FAIL -> REJECT
    if not metrics["schema_ok"]:
        reason_codes.append("SCHEMA_FAIL")
        return "REJECT", reason_codes
        
    thresholds = config.thresholds
    
    # 4. MISSING_TOO_HIGH -> REJECT
    critical_fields = thresholds.get("critical_fields", [])
    missing_rates = metrics["missing_rate_by_field"]
    missing_limits = thresholds.get("missing_rate_limits", {})
    
    for field in critical_fields:
        if missing_rates.get(field, 0) > missing_limits.get("critical_max", 0):
            if "MISSING_TOO_HIGH" not in reason_codes:
                reason_codes.append("MISSING_TOO_HIGH")
            break
            
    # Non-critical missing
    if "MISSING_TOO_HIGH" not in reason_codes:
        for field, rate in missing_rates.items():
            if field not in critical_fields:
                if rate > missing_limits.get("noncritical_max", 5):
                    reason_codes.append("MISSING_TOO_HIGH")
                    break

    # 5. DUPLICATES_TOO_HIGH -> REJECT
    if metrics["duplicates_rate"] > thresholds.get("duplicate_rate_max", 1):
        if "DUPLICATES_TOO_HIGH" not in reason_codes:
            reason_codes.append("DUPLICATES_TOO_HIGH")

    # 6. Violation limits support
    violation_limits = thresholds.get("violation_limits", {})
    
    # Range violations
    range_violations = sum(metrics.get("range_violations_count_by_field", {}).values())
    if range_violations > violation_limits.get("range_violations_max", 0):
        if "OUT_OF_RANGE" not in reason_codes:
            reason_codes.append("OUT_OF_RANGE")
            
    # Enum violations
    enum_violations = sum(metrics.get("enum_violations_count_by_field", {}).values())
    if enum_violations > violation_limits.get("enum_violations_max", 0):
        if "ENUM_VIOLATION" not in reason_codes:
            reason_codes.append("ENUM_VIOLATION")
            
    if reason_codes:
        return "REJECT", reason_codes
        
    return "ACCEPT", []
