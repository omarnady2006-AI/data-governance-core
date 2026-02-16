import pandas as pd

# Type mapping for schema validation
TYPE_MAPPING = {
    "string": ["object", "string", "str"],
    "float": ["float64", "float32", "float16", "float"],
    "integer": ["int64", "int32", "int16", "int8", "uint64", "uint32", "uint16", "uint8", "int"],
    "date": ["datetime64[ns]", "datetime64", "datetime"],
    "datetime": ["datetime64[ns]", "datetime64", "datetime"],
    "boolean": ["bool", "boolean"]
}


def validate_ranges(df: pd.DataFrame, config) -> dict:
    """
    Validate numeric fields against min/max bounds from column_dictionary.
    
    Returns:
        dict: Field name -> violation count
        Example: {"amount": 5, "age": 0}
    """
    violations = {}
    
    for col in df.columns:
        constraints = config.get_field_constraints(col)
        if not constraints:
            continue
        
        range_min = constraints.get("range_min")
        range_max = constraints.get("range_max")
        
        if range_min is None and range_max is None:
            continue
        
        # Skip non-numeric columns
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        
        # Count violations (excluding nulls)
        violation_count = 0
        non_null_values = df[col].dropna()
        
        if range_min is not None:
            violation_count += (non_null_values < range_min).sum()
        
        if range_max is not None:
            violation_count += (non_null_values > range_max).sum()
        
        if violation_count > 0:
            violations[col] = int(violation_count)
    
    return violations


def validate_enums(df: pd.DataFrame, config) -> dict:
    """
    Validate categorical fields against allowed values from column_dictionary.
    
    Returns:
        dict: Field name -> violation count
        Example: {"gender": 3, "status": 0}
    """
    violations = {}
    
    for col in df.columns:
        constraints = config.get_field_constraints(col)
        if not constraints:
            continue
        
        allowed_values = constraints.get("allowed_values")
        if not allowed_values:
            continue
        
        # Count values not in allowed list (excluding nulls)
        non_null_values = df[col].dropna()
        invalid_mask = ~non_null_values.isin(allowed_values)
        violation_count = invalid_mask.sum()
        
        if violation_count > 0:
            violations[col] = int(violation_count)
    
    return violations


def validate_schema(df: pd.DataFrame, config) -> bool:
    """
    Enhanced schema validation:
    1. Critical fields exist
    2. Field data types match column_dictionary
    3. Coercion check for numeric fields
    
    Returns:
        bool: True if schema is valid
    """
    # Check critical fields exist
    critical_fields = config.thresholds.get("critical_fields", [])
    if not all(f in df.columns for f in critical_fields):
        return False
    
    # Check data types match expectations
    for col in df.columns:
        constraints = config.get_field_constraints(col)
        if not constraints:
            continue  # Unknown columns are allowed
        
        expected_type = constraints.get("expected_type")
        if not expected_type:
            continue
        
        actual_dtype = str(df[col].dtype)
        allowed_dtypes = TYPE_MAPPING.get(expected_type, [])
        
        # Check if actual dtype matches any allowed dtype for this type
        dtype_matches = any(actual_dtype == allowed or actual_dtype.startswith(allowed) for allowed in allowed_dtypes)
        
        if not dtype_matches:
            # For numeric types, try coercion to verify data
            if expected_type in ("float", "integer"):
                try:
                    pd.to_numeric(df[col], errors='raise')
                except (ValueError, TypeError):
                    return False
            else:
                return False
        elif expected_type in ("float", "integer") and actual_dtype in ("object", "string", "str"):
             # Even if dtype matches "string" (which it shouldn't for float), 
             # if we are here it means dtype_matches was True.
             # But if expected is float/int and it is currently a string type, we should verify it's numeric.
             try:
                 pd.to_numeric(df[col], errors='raise')
             except (ValueError, TypeError):
                 return False
    
    return True


def calculate_metrics(df: pd.DataFrame, postcheck_results: dict, config):
    """
    Calculate all metrics including enhanced validation.
    """
    # Existing metrics
    missing_rates = (df.isnull().mean() * 100).to_dict()
    duplicates_rate = float(df.duplicated().mean() * 100)
    
    # Enhanced schema validation
    schema_ok = validate_schema(df, config)
    
    # NEW: Range and enum validation
    range_violations = validate_ranges(df, config)
    enum_violations = validate_enums(df, config)
    
    return {
        "schema_ok": schema_ok,
        "missing_rate_by_field": missing_rates,
        "duplicates_rate": duplicates_rate,
        "range_violations_count_by_field": range_violations,  # No longer empty!
        "enum_violations_count_by_field": enum_violations,    # No longer empty!
        "postcheck_ok": postcheck_results["postcheck_ok"],
        "patterns_remaining_count": postcheck_results["patterns_remaining_count"],
        "rate_unit": "percent"
    }
