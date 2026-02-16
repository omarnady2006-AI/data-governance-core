import pandas as pd
import re

def postcheck(df: pd.DataFrame, config):
    patterns = config.policy.get("postcheck", {}).get("prohibited_patterns", [])
    total_hits = 0
    pattern_hits_summary = []
    
    for p_cfg in patterns:
        desc = p_cfg.get("description")
        pattern = p_cfg.get("pattern")
        
        hit_count = 0
        if "Phone" in desc:
            # Special logic for phone: digit-length 10-15 AFTER stripping non-digits
            for col in df.select_dtypes(include=['object', 'string', 'str']):
                def is_phone(x):
                    if pd.isnull(x): return False
                    s_val = str(x)
                    # Heuristic: if it contains letters, it's likely an ID, not a phone
                    if re.search(r'[a-zA-Z]', s_val): return False
                    digits = re.sub(r'\D', '', s_val)
                    return 10 <= len(digits) <= 15
                hit_count += df[col].apply(is_phone).sum()
        else:
            # For non-phone patterns (email, SSN, etc.), use standard regex matching
            regex = re.compile(pattern)
            for col in df.select_dtypes(include=['object', 'string', 'str']):
                hit_count += df[col].apply(lambda x: bool(regex.search(str(x))) if pd.notnull(x) else False).sum()
        
        if hit_count > 0:
            total_hits += hit_count
            pattern_hits_summary.append({"description": desc, "count": int(hit_count)})
            
    return {
        "postcheck_ok": (total_hits == 0),
        "patterns_remaining_count": int(total_hits),
        "pattern_hits": pattern_hits_summary
    }