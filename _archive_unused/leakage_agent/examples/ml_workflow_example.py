"""
ML Workflow Example - Complete Demonstration of Leakage Agent

This script demonstrates all key features of the Data Leakage Auto-Supervisor Agent:
1. Generating synthetic data
2. Basic validation with LeakageValidator
3. Inspecting results (decision, metrics, transformations)
4. Handling rejections
5. Using orchestrator with retry logic
6. Batch processing multiple datasets
7. Summary statistics from batch results

Run with: python examples/ml_workflow_example.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from leakage_agent import LeakageValidator
from leakage_agent.orchestrator import DataOrchestrator
from leakage_agent.lineage import LineageTracker


def generate_synthetic_data(n_rows=1000, include_issues=False, issue_type=None):
    """
    Generate synthetic training data for demonstration.
    
    Args:
        n_rows: Number of rows to generate
        include_issues: If True, introduce data quality issues
        issue_type: Type of issue to introduce ('missing', 'range', 'duplicates', 'secrets')
    
    Returns:
        DataFrame with synthetic user transaction data
    """
    np.random.seed(42)
    
    cities = ['San Francisco', 'New York', 'Los Angeles', 'Chicago', 'Boston', 'Seattle', 'Austin', 'Miami']
    countries = ['US', 'UK', 'CA', 'AU', 'DE', 'FR']
    genders = ['male', 'female', 'other', 'prefer_not_to_say']
    
    # Generate base data
    data = {
        'user_id': [f'user_{str(i).zfill(6)}' for i in range(n_rows)],
        'email': [f'user{i}@example.com' for i in range(n_rows)],
        'phone': [f'+1{np.random.randint(2000000000, 9999999999)}' for i in range(n_rows)],
        'name': [f'User {i}' for i in range(n_rows)],
        'dob': [(datetime(1950, 1, 1) + timedelta(days=np.random.randint(0, 25000))).strftime('%Y-%m-%d') 
                for _ in range(n_rows)],
        'address': [f'{np.random.randint(1, 9999)} {np.random.choice(["Main", "Oak", "Elm", "Pine"])} St, {np.random.choice(cities)}, CA' 
                    for _ in range(n_rows)],
        'zip_code': [f'{np.random.randint(10000, 99999)}' for _ in range(n_rows)],
        'city': [np.random.choice(cities) for _ in range(n_rows)],
        'country': [np.random.choice(countries) for _ in range(n_rows)],
        'gender': [np.random.choice(genders) for _ in range(n_rows)],
        'amount': np.random.uniform(10, 10000, n_rows).round(2),
        'timestamp': [(datetime.now() - timedelta(days=np.random.randint(0, 365))).isoformat() 
                      for _ in range(n_rows)],
        'label': [np.random.choice(['fraud', 'legitimate']) for _ in range(n_rows)]
    }
    
    df = pd.DataFrame(data)
    
    # Introduce issues if requested
    if include_issues:
        if issue_type == 'missing':
            # Introduce missing values in critical field
            df.loc[0:50, 'label'] = None
            print(f"  ⚠️  Introduced missing values in 'label' (51 rows)")
            
        elif issue_type == 'range':
            # Introduce range violations
            df.loc[0:10, 'amount'] = -500.0  # Negative amounts
            df.loc[11:20, 'amount'] = 2000000.0  # Exceeds max
            print(f"  ⚠️  Introduced range violations in 'amount' (21 rows)")
            
        elif issue_type == 'duplicates':
            # Introduce duplicates
            df = pd.concat([df, df.iloc[0:30]], ignore_index=True)
            print(f"  ⚠️  Introduced 30 duplicate rows")
            
        elif issue_type == 'secrets':
            # Introduce forbidden column (API key)
            df['api_key'] = [f'sk_live_{np.random.randint(1000000, 9999999)}' for _ in range(len(df))]
            print(f"  ⚠️  Introduced forbidden column 'api_key'")
    
    return df


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(result, show_metrics=True):
    """Print validation result details."""
    print(f"\n📋 Decision: {result.decision}")
    print(f"📝 Reason Codes: {', '.join(result.reason_codes) if result.reason_codes else 'None'}")
    
    if show_metrics and result.metrics:
        print(f"\n📊 Metrics:")
        print(f"  - Missing rates (critical): {result.metrics.get('missing_rates_critical', {})}")
        print(f"  - Missing rates (noncritical): {result.metrics.get('missing_rates_noncritical', {})}")
        print(f"  - Duplicate rate: {result.metrics.get('duplicate_rate', 0):.2f}%")
        print(f"  - Range violations: {result.metrics.get('range_violations', 0)}")
        print(f"  - Enum violations: {result.metrics.get('enum_violations', 0)}")
    
    if result.transform_summary:
        print(f"\n🔄 Transformations Applied:")
        ts = result.transform_summary
        print(f"  - Tokenized fields: {sum(ts.get('tokenized_fields_count', {}).values())}")
        print(f"  - Dropped columns: {len(ts.get('dropped_columns', []))}")
        print(f"  - Derived fields: {len(ts.get('derived_fields_created', []))}")
        print(f"  - Duplicates removed: {ts.get('duplicates_removed', 0)}")


# ==============================================================================
# EXAMPLE 1: Basic Validation with ACCEPT Decision
# ==============================================================================

def example_1_basic_validation():
    print_section("EXAMPLE 1: Basic Validation (Clean Data → ACCEPT)")
    
    # Generate clean synthetic data
    print("\n1️⃣  Generating synthetic data (1000 rows)...")
    df = generate_synthetic_data(n_rows=1000, include_issues=False)
    print(f"   Generated DataFrame with shape: {df.shape}")
    print(f"   Columns: {list(df.columns)[:5]}... (showing first 5)")
    
    # Initialize validator
    print("\n2️⃣  Initializing LeakageValidator...")
    validator = LeakageValidator(policy_dir="policy/versions/v1")
    
    # Validate data
    print("\n3️⃣  Running validation...")
    result = validator.validate(df, copy_id="example_001", out_dir="outputs")
    
    # Inspect results
    print_result(result)
    
    # Check decision and use cleaned data
    if result.is_accepted:
        print(f"\n✅ SUCCESS - Data approved for training!")
        print(f"   Cleaned data shape: {result.cleaned_data.shape}")
        print(f"   Sample cleaned columns: {list(result.cleaned_data.columns)[:8]}")
        
        # Show transformation example
        print(f"\n   Original user_id: {df['user_id'].iloc[0]}")
        print(f"   Tokenized user_id: {result.cleaned_data['user_id'].iloc[0] if 'user_id' in result.cleaned_data.columns else 'N/A'}")
    else:
        print(f"\n❌ FAILED - {result.decision}")


# ==============================================================================
# EXAMPLE 2: Handling Rejections (Quality Issues)
# ==============================================================================

def example_2_handling_rejections():
    print_section("EXAMPLE 2: Handling Rejections (Bad Data → REJECT)")
    
    # Test different types of rejections
    rejection_types = [
        ('missing', 'Missing values in critical field'),
        ('range', 'Range violations'),
        ('duplicates', 'Too many duplicates')
    ]
    
    validator = LeakageValidator(policy_dir="policy/versions/v1")
    
    for issue_type, description in rejection_types:
        print(f"\n\n🧪 Testing: {description}")
        print("-" * 60)
        
        df = generate_synthetic_data(n_rows=500, include_issues=True, issue_type=issue_type)
        result = validator.validate(df, copy_id=f"reject_{issue_type}", out_dir="outputs")
        
        print_result(result, show_metrics=True)
        
        if result.is_rejected:
            print(f"\n❌ Expected REJECT received")
            print(f"   Primary issue: {result.reason_codes[0] if result.reason_codes else 'Unknown'}")
        else:
            print(f"\n⚠️  Unexpected decision: {result.decision}")


# ==============================================================================
# EXAMPLE 3: Quarantine (Security Issues)
# ==============================================================================

def example_3_quarantine():
    print_section("EXAMPLE 3: Quarantine Decision (Secrets Detected)")
    
    print("\n🔒 Generating data with forbidden column (api_key)...")
    df = generate_synthetic_data(n_rows=200, include_issues=True, issue_type='secrets')
    
    validator = LeakageValidator(policy_dir="policy/versions/v1")
    result = validator.validate(df, copy_id="quarantine_001", out_dir="outputs")
    
    print_result(result, show_metrics=False)
    
    if result.is_quarantined:
        print(f"\n⚠️  QUARANTINE - Security review required")
        print(f"   This dataset contains forbidden patterns and must be manually reviewed")
        print(f"   Forbidden hits: {result.report.get('forbidden_info', {}).get('forbidden_hits_columns', [])}")
    else:
        print(f"\n⚠️  Unexpected decision: {result.decision}")


# ==============================================================================
# EXAMPLE 4: Batch Processing
# ==============================================================================

def example_4_batch_processing():
    print_section("EXAMPLE 4: Batch Processing Multiple Datasets")
    
    # Generate multiple datasets
    print("\n📦 Generating batch of datasets...")
    dataframes = {
        "batch_001": generate_synthetic_data(n_rows=300, include_issues=False),
        "batch_002": generate_synthetic_data(n_rows=300, include_issues=False),
        "batch_003": generate_synthetic_data(n_rows=300, include_issues=True, issue_type='missing'),
        "batch_004": generate_synthetic_data(n_rows=300, include_issues=True, issue_type='range'),
        "batch_005": generate_synthetic_data(n_rows=300, include_issues=False),
    }
    print(f"   Created {len(dataframes)} datasets")
    
    # Validate batch
    print("\n🔄 Validating batch...")
    validator = LeakageValidator(policy_dir="policy/versions/v1")
    results = validator.validate_batch(dataframes, out_dir="outputs")
    
    # Show individual results
    print("\n📊 Individual Results:")
    for copy_id, result in results.items():
        status_emoji = "✅" if result.is_accepted else ("❌" if result.is_rejected else "⚠️")
        print(f"   {status_emoji} {copy_id}: {result.decision} - {', '.join(result.reason_codes[:2]) if result.reason_codes else 'OK'}")
    
    # Get summary statistics
    summary = validator.get_summary(results)
    
    print("\n" + "=" * 60)
    print("  BATCH SUMMARY")
    print("=" * 60)
    print(f"  Total datasets:    {summary['total']}")
    print(f"  ✅ Accepted:       {summary['accepted']} ({summary['acceptance_rate']:.1f}%)")
    print(f"  ❌ Rejected:       {summary['rejected']}")
    print(f"  ⚠️  Quarantined:   {summary['quarantined']}")
    print("=" * 60)


# ==============================================================================
# EXAMPLE 5: Retry with Orchestrator
# ==============================================================================

def example_5_orchestrator_retry():
    print_section("EXAMPLE 5: Using Orchestrator with Retry Logic")
    
    # Simple regenerator function
    def simple_regenerator(df, guidance_dict):
        """Fix common issues based on retry guidance."""
        df_fixed = df.copy()
        guidance = guidance_dict.get('guidance', {})
        
        print(f"\n   🔧 Applying fixes based on guidance:")
        
        # Fix missing values
        if 'reduce_missing_rate' in guidance:
            for field in guidance['reduce_missing_rate']:
                if field in df_fixed.columns:
                    # Fill missing values with a default
                    if field == 'label':
                        df_fixed[field] = df_fixed[field].fillna('legitimate')
                        print(f"      - Filled missing values in '{field}'")
        
        # Fix range violations
        if 'fix_range_violations' in guidance:
            if 'amount' in df_fixed.columns:
                df_fixed['amount'] = df_fixed['amount'].clip(0, 1000000)
                print(f"      - Clipped 'amount' to valid range [0, 1000000]")
        
        return df_fixed
    
    # Generate bad data
    print("\n1️⃣  Generating data with quality issues (missing labels)...")
    df = generate_synthetic_data(n_rows=400, include_issues=True, issue_type='missing')
    
    # Use orchestrator with retry
    print("\n2️⃣  Processing with orchestrator (max 3 retries)...")
    orchestrator = DataOrchestrator(
        policy_dir="policy/versions/v1",
        max_retries=3
    )
    
    result = orchestrator.process_with_retry(
        df=df,
        copy_id="orchestrator_001",
        regenerator=simple_regenerator,
        out_dir="outputs"
    )
    
    print(f"\n3️⃣  Final Result:")
    print_result(result, show_metrics=True)
    
    if result.is_accepted:
        print(f"\n✅ SUCCESS after retry!")
        print(f"   Total attempts: {result.report.get('attempt_count', 'unknown')}")
    else:
        print(f"\n❌ Still failed after retries: {result.decision}")


# ==============================================================================
# EXAMPLE 6: Lineage Tracking
# ==============================================================================

def example_6_lineage_tracking():
    print_section("EXAMPLE 6: Data Lineage Tracking")
    
    # Create lineage tracker
    tracker = LineageTracker()
    
    # Record ingestion
    copy_id = "lineage_example_001"
    tracker.record_ingestion(copy_id, {
        "source_type": "synthetic",
        "generator": "numpy_random",
        "config": {"n_rows": 500, "seed": 42}
    })
    print(f"\n✅ Recorded data ingestion for {copy_id}")
    
    # Generate and validate data
    df = generate_synthetic_data(n_rows=500, include_issues=False)
    
    # Create pipeline with lineage tracking
    from leakage_agent.pipeline import Pipeline
    pipeline = Pipeline(policy_dir="policy/versions/v1", lineage_tracker=tracker)
    
    print(f"\n🔄 Running validation pipeline with lineage tracking...")
    cleaned_df, report = pipeline.run(df, out_dir="outputs", copy_id=copy_id)
    
    # Get lineage summary
    lineage_summary = tracker.get_lineage_summary(copy_id)
    
    print(f"\n📜 Lineage Summary:")
    print(f"   Copy ID: {lineage_summary['copy_id']}")
    print(f"   Source Type: {lineage_summary['source_type']}")
    print(f"   Created At: {lineage_summary['created_at']}")
    print(f"   Transformations: {lineage_summary['transformation_count']}")
    print(f"   Versions: {lineage_summary['version_count']}")
    
    # Get full lineage
    full_lineage = tracker.get_lineage(copy_id)
    print(f"\n📋 Transformation History:")
    for i, transform in enumerate(full_lineage['transformations'][:5], 1):
        print(f"   {i}. {transform['stage']}: {transform['details']}")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Run all examples."""
    print("\n" + "🚀" * 35)
    print("  ML WORKFLOW EXAMPLE - Data Leakage Auto-Supervisor Agent")
    print("🚀" * 35)
    
    try:
        # Run all examples
        example_1_basic_validation()
        example_2_handling_rejections()
        example_3_quarantine()
        example_4_batch_processing()
        example_5_orchestrator_retry()
        example_6_lineage_tracking()
        
        print("\n\n" + "🎉" * 35)
        print("  ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("🎉" * 35)
        print("\n📁 Check the 'outputs/' directory for validation reports and cleaned data.\n")
        
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
