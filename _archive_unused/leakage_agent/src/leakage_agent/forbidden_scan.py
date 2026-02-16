import pandas as pd
import re

def forbidden_scan(df: pd.DataFrame, config):
    forbidden_cols = [c.lower() for c in config.forbidden.get("forbidden_column_names", [])]
    found_cols = [c for c in df.columns if c.lower() in forbidden_cols]
    
    pattern_map = {
        "jwt_like": r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",
        "private_key_block": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
        "bearer_token": r"Bearer [A-Za-z0-9\-._~+/]+=*"
    }
    
    found_pattern_names = []
    affected_cols_count = 0
    
    forbidden_patterns = config.forbidden.get("forbidden_value_patterns", [])
    for p_name in forbidden_patterns:
        regex_str = pattern_map.get(p_name)
        if not regex_str: continue
        regex = re.compile(regex_str)
        
        hit_in_pattern = False
        for col in df.select_dtypes(include=['object', 'string', 'str']):
            if df[col].apply(lambda x: bool(regex.search(str(x))) if pd.notnull(x) else False).any():
                hit_in_pattern = True
                affected_cols_count += 1
        
        if hit_in_pattern:
            found_pattern_names.append(p_name)

    forbidden_found = bool(found_cols or found_pattern_names)
    
    return {
        "forbidden_found": forbidden_found,
        "forbidden_hits_columns": found_cols,
        "forbidden_hits_value_patterns": found_pattern_names,
        "quarantine_recommended": forbidden_found # As per rules
    }
