import pandas as pd
from dateutil import parser
import re

def normalize(df: pd.DataFrame, config):
    df = df.copy()
    total_changes = 0
    for col in df.columns:
        action_cfg = config.get_field_action(col)
        norms = action_cfg.get("normalization", [])
        if not norms: continue
        
        orig_col = df[col].copy()
        for norm in norms:
            if norm == "trim" and df[col].dtype == "object":
                df[col] = df[col].str.strip()
            elif norm == "lowercase" and df[col].dtype == "object":
                df[col] = df[col].str.lower()
            elif norm == "digits_only" and df[col].dtype == "object":
                df[col] = df[col].astype(str).str.replace(r'\D', '', regex=True)
            elif norm == "date_iso" and df[col].dtype == "object":
                def parse_date(x):
                    if pd.isnull(x): return x
                    try: return parser.parse(str(x)).isoformat()
                    except: return x
                df[col] = df[col].apply(parse_date)
        
        # Count changed cells in this column
        # Fillna for comparison
        changed_mask = (df[col].astype(str) != orig_col.astype(str)) & (df[col].notnull() | orig_col.notnull())
        total_changes += changed_mask.sum()
        
    return df, int(total_changes)
