import pandas as pd
import hashlib
import hmac
from datetime import datetime
from dateutil import parser

INTERNAL_SECRET = "leakage_agent_v1_secret_key"

def tokenize_value(val):
    if pd.isnull(val): return val
    msg = str(val).encode()
    h = hmac.new(INTERNAL_SECRET.encode(), msg, hashlib.sha256).hexdigest()
    return f"tok_{h[:8]}"

def calculate_age(dob_val):
    if pd.isnull(dob_val): return "Unknown"
    try:
        birth_date = parser.parse(str(dob_val))
        today = datetime.now()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except:
        return None

def get_bucket(age, scheme):
    if age is None or age == "Unknown": return "Unknown"
    for b in scheme:
        if "-" in b:
            parts = b.split("-")
            low = parts[0]
            high = parts[1]
            if low == "": low = 0
            try:
                if high == "+":
                    if age >= int(low): return b
                elif int(low) <= age <= int(high):
                    return b
            except: pass
        elif b.endswith("+"):
            try:
                if age >= int(b[:-1]): return b
            except: pass
    return "Unknown"

def transform_engine(df: pd.DataFrame, config):
    df = df.copy()
    summary = {
        "tokenized_fields_count": {},
        "dropped_columns": [],
        "derived_fields_created": []
    }
    
    cols_to_process = list(df.columns)
    for col in cols_to_process:
        action_cfg = config.get_field_action(col)
        action = action_cfg.get("action")
        
        if action == "DROP":
            df.drop(columns=[col], inplace=True)
            summary["dropped_columns"].append(col)
            
        elif action == "TOKENIZE_DET":
            non_null_mask = df[col].notnull()
            df.loc[non_null_mask, col] = df.loc[non_null_mask, col].apply(tokenize_value)
            summary["tokenized_fields_count"][col] = int(non_null_mask.sum())
            
        elif action == "BUCKET":
            out = action_cfg.get("output_field", f"{col}_bucket")
            # FIXED: Use bucket_scheme (correct key) instead of buckets
            scheme = action_cfg.get("bucket_scheme", ["0-17", "18-25", "26-35", "36-45", "46-60", "60+"])
            ages = df[col].apply(calculate_age)
            df[out] = ages.apply(lambda a: get_bucket(a, scheme))
            summary["derived_fields_created"].append(out)
            # Privacy: Drop original column
            if col in df.columns:
                df.drop(columns=[col], inplace=True)
                summary["dropped_columns"].append(col)
                
        elif action == "GENERALIZE":
            scheme = action_cfg.get("generalize_scheme")
            out = action_cfg.get("output_field")
            
            if scheme == "prefix_3":
                out = out or f"{col}_prefix_3"
                # Apply only for non-null cells, keep nulls null
                df[out] = df[col].apply(lambda x: str(x)[:3] if pd.notnull(x) else x)
                summary["derived_fields_created"].append(out)
                # Privacy: Drop original column
                if col in df.columns:
                    df.drop(columns=[col], inplace=True)
                    summary["dropped_columns"].append(col)
                    
            elif scheme == "extract_city":
                out = out or "city_only"
                def extract_city(addr):
                    if pd.isnull(addr): return None
                    parts = str(addr).split(",")
                    if len(parts) > 1: return parts[-1].strip()
                    words = str(addr).split()
                    return words[-1] if words else None
                
                df[out] = df[col].apply(extract_city)
                
                # Check for total failure for fallback
                if df[out].isnull().all() and config.policy.get("generalization_fallbacks", {}).get(col) == "DROP":
                    # Fallback already handled by dropping original column below
                    pass
                else:
                    if out not in summary["derived_fields_created"]:
                        summary["derived_fields_created"].append(out)
                
                # Privacy: DROP original column regardless of success rate
                if col in df.columns:
                    df.drop(columns=[col], inplace=True)
                    summary["dropped_columns"].append(col)
            
    return df, summary