import pandas as pd

def normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_")

def canonicalize(df: pd.DataFrame, config):
    df = df.copy()
    aliases = config.policy.get("field_name_aliases", {})
    
    # Create a reverse map for normalized input -> canonical
    # Also include the canonical names themselves in the map
    mapping_lookup = {}
    for canonical, synonyms in aliases.items():
        norm_canonical = normalize_key(canonical)
        mapping_lookup[norm_canonical] = canonical
        for syn in synonyms:
            mapping_lookup[normalize_key(syn)] = canonical
            
    final_mapping = {}
    mappings_info = []
    collisions = []
    seen_canonical = set()
    
    for col in df.columns:
        norm_col = normalize_key(col)
        if norm_col in mapping_lookup:
            target = mapping_lookup[norm_col]
            if target in seen_canonical:
                collisions.append(col)
            else:
                final_mapping[col] = target
                mappings_info.append({"raw": col, "canonical": target})
                seen_canonical.add(target)
                
    mapping_summary = {
        "mappings": mappings_info,
        "collisions": collisions,
        "canonical_mapping_count": len(mappings_info)
    }
    
    return df.rename(columns=final_mapping), mapping_summary
