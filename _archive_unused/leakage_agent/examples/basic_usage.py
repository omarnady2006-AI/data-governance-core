"""
Basic Usage Examples - Simple Introduction to Leakage Agent

This file contains simple, beginner-friendly examples demonstrating
the most common use cases of the Data Leakage Auto-Supervisor Agent.

Each example is self-contained and heavily commented to explain what's happening.

Run with: python examples/basic_usage.py
"""

import pandas as pd
import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from leakage_agent import LeakageValidator


# ==============================================================================
# EXAMPLE 1: Single File Validation (Simplest Use Case)
# ==============================================================================

def example_1_single_file_validation():
    """
    Validate a single DataFrame in just 5 lines of code.
    This is the most basic use case - you have data, you validate it.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Single File Validation")
    print("=" * 70)
    
    # Step 1: Load your data (or create a sample)
    # In practice, you'd use: df = pd.read_csv("your_data.csv")
    df = pd.DataFrame({
        'user_id': ['user_001', 'user_002', 'user_003'],
        'email': ['alice@example.com', 'bob@example.com', 'charlie@example.com'],
        'amount': [100.0, 250.0, 75.0],
        'label': ['fraud', 'legitimate', 'legitimate']
    })
    print(f"\n✓ Loaded DataFrame with {len(df)} rows")
    
    # Step 2: Create validator
    validator = LeakageValidator()
    print(f"✓ Created LeakageValidator")
    
    # Step 3: Validate the data
    result = validator.validate(df, copy_id="example_001")
    print(f"✓ Validation complete")
    
    # Step 4: Check the decision
    print(f"\n📋 Decision: {result.decision}")
    print(f"📝 Reason: {', '.join(result.reason_codes) if result.reason_codes else 'All checks passed'}")
    
    # Step 5: Use the cleaned data if accepted
    if result.is_accepted:
        print(f"✅ Data approved! Clean data has {len(result.cleaned_data)} rows")
        # In practice: result.cleaned_data.to_csv("approved_data.csv", index=False)
    
    return result


# ==============================================================================
# EXAMPLE 2: Checking Decision with Conditional Logic
# ==============================================================================

def example_2_decision_handling():
    """
    Different actions based on validation decision.
    Use this pattern to handle ACCEPT, REJECT, and QUARANTINE differently.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Handling Different Decisions")
    print("=" * 70)
    
    # Create sample data
    df = pd.DataFrame({
        'user_id': [f'user_{i:03d}' for i in range(10)],
        'email': [f'user{i}@example.com' for i in range(10)],
        'amount': [50.0 + i * 10 for i in range(10)],
        'label': ['fraud' if i % 3 == 0 else 'legitimate' for i in range(10)]
    })
    
    # Validate
    validator = LeakageValidator()
    result = validator.validate(df, copy_id="example_002")
    
    # Handle different decisions
    print(f"\n📋 Decision: {result.decision}\n")
    
    if result.is_accepted:
        # Data passed all checks - proceed with training
        print("✅ ACCEPT: Data approved for ML training")
        print(f"   → Saving cleaned data to 'approved_data.csv'")
        print(f"   → {len(result.cleaned_data)} rows ready for training")
        # result.cleaned_data.to_csv("approved_data.csv", index=False)
        
    elif result.is_rejected:
        # Data has quality issues - fix and retry
        print("❌ REJECT: Data has quality issues")
        print(f"   → Reason: {', '.join(result.reason_codes)}")
        print(f"   → Action: Fix data quality issues and resubmit")
        print(f"   → Check metrics for details:")
        for key, value in result.metrics.items():
            print(f"      - {key}: {value}")
        
    elif result.is_quarantined:
        # Data has security issues - manual review required
        print("⚠️  QUARANTINE: Security review required")
        print(f"   → Reason: {', '.join(result.reason_codes)}")
        print(f"   → Action: Contact security team for manual review")
        print(f"   → DO NOT use this data for training")
    
    return result


# ==============================================================================
# EXAMPLE 3: Accessing Cleaned Data
# ==============================================================================

def example_3_accessing_cleaned_data():
    """
    Understanding what transformations were applied to your data.
    The cleaned_data contains transformed fields based on policy.yaml.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Accessing Cleaned Data")
    print("=" * 70)
    
    # Create sample data with PII
    df = pd.DataFrame({
        'user_id': ['alice@example.com', 'bob@example.com', 'charlie@example.com'],
        'email': ['alice@example.com', 'bob@example.com', 'charlie@example.com'],
        'name': ['Alice Johnson', 'Bob Smith', 'Charlie Davis'],
        'amount': [100.0, 250.0, 75.0],
        'city': ['San Francisco', 'New York', 'Chicago'],
        'label': ['fraud', 'legitimate', 'legitimate']
    })
    
    print("\n📥 Original data columns:")
    print(f"   {list(df.columns)}")
    print(f"\n   Sample original user_id: {df['user_id'].iloc[0]}")
    print(f"   Sample original name: {df['name'].iloc[0]}")
    
    # Validate
    validator = LeakageValidator()
    result = validator.validate(df, copy_id="example_003")
    
    if result.is_accepted:
        print("\n📤 Cleaned data columns:")
        print(f"   {list(result.cleaned_data.columns)}")
        
        # Show transformations
        print(f"\n🔄 Transformations applied:")
        ts = result.transform_summary
        
        # Tokenized fields (email, user_id)
        tok_count = sum(ts.get('tokenized_fields_count', {}).values())
        print(f"   ✓ Tokenized {tok_count} fields (user_id, email)")
        if 'user_id' in result.cleaned_data.columns:
            print(f"      Example: {df['user_id'].iloc[0]} → {result.cleaned_data['user_id'].iloc[0]}")
        
        # Dropped fields (name - full names are PII)
        dropped = ts.get('dropped_columns', [])
        if dropped:
            print(f"   ✓ Dropped {len(dropped)} column(s): {', '.join(dropped)}")
        
        # Derived fields
        derived = ts.get('derived_fields_created', [])
        if derived:
            print(f"   ✓ Created {len(derived)} derived field(s): {', '.join(derived)}")
        
        # Kept fields (city, amount, label)
        print(f"   ✓ Kept fields unchanged: city, amount, label")
        
        print(f"\n✅ Cleaned data ready for training!")
        print(f"   Shape: {result.cleaned_data.shape}")
    
    return result


# ==============================================================================
# EXAMPLE 4: Batch Validation
# ==============================================================================

def example_4_batch_validation():
    """
    Validate multiple datasets at once.
    More efficient than calling validate() multiple times.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Batch Validation")
    print("=" * 70)
    
    # Create multiple datasets (e.g., from different sources or time periods)
    datasets = {}
    
    for i in range(1, 6):
        datasets[f"dataset_{i}"] = pd.DataFrame({
            'user_id': [f'user_{i}_{j:03d}' for j in range(5)],
            'email': [f'user{i}_{j}@example.com' for j in range(5)],
            'amount': [50.0 + j * 20 for j in range(5)],
            'label': ['fraud' if j % 2 == 0 else 'legitimate' for j in range(5)]
        })
    
    print(f"\n✓ Created {len(datasets)} datasets to validate")
    
    # Validate all datasets in batch
    validator = LeakageValidator()
    results = validator.validate_batch(datasets, out_dir="outputs")
    
    print(f"✓ Batch validation complete")
    
    # Examine results for each dataset
    print(f"\n📊 Individual results:")
    for copy_id, result in results.items():
        emoji = "✅" if result.is_accepted else ("❌" if result.is_rejected else "⚠️")
        print(f"   {emoji} {copy_id}: {result.decision}")
    
    # Get aggregate statistics
    summary = validator.get_summary(results)
    
    print(f"\n📈 Summary statistics:")
    print(f"   Total datasets: {summary['total']}")
    print(f"   Accepted: {summary['accepted']} ({summary['acceptance_rate']:.1f}%)")
    print(f"   Rejected: {summary['rejected']}")
    print(f"   Quarantined: {summary['quarantined']}")
    
    return results


# ==============================================================================
# EXAMPLE 5: Using Context Manager
# ==============================================================================

def example_5_context_manager():
    """
    Using LeakageValidator as a context manager.
    This ensures proper cleanup of resources (useful for future extensions).
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Using Context Manager")
    print("=" * 70)
    
    # Create sample data
    df = pd.DataFrame({
        'user_id': ['user_001', 'user_002', 'user_003'],
        'email': ['test1@example.com', 'test2@example.com', 'test3@example.com'],
        'amount': [100.0, 200.0, 150.0],
        'label': ['fraud', 'legitimate', 'fraud']
    })
    
    # Use context manager (with statement)
    # This automatically handles resource cleanup
    with LeakageValidator() as validator:
        print("✓ Validator created (context manager)")
        
        result = validator.validate(df, copy_id="example_005")
        
        print(f"✓ Validation complete: {result.decision}")
        
        if result.is_accepted:
            print(f"✅ Clean data has {len(result.cleaned_data)} rows")
        
        # Validator will automatically clean up when exiting the 'with' block
    
    print("✓ Context manager exited, resources cleaned up")
    
    return result


# ==============================================================================
# EXAMPLE 6: Error Handling
# ==============================================================================

def example_6_error_handling():
    """
    Proper error handling for validation failures.
    Always wrap validation in try/except for production code.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Error Handling")
    print("=" * 70)
    
    # Simulate potential errors
    test_cases = [
        ("Valid data", pd.DataFrame({
            'user_id': ['user_001'],
            'email': ['test@example.com'],
            'amount': [100.0],
            'label': ['fraud']
        })),
        ("Empty DataFrame", pd.DataFrame()),
        ("Missing columns", pd.DataFrame({
            'random_col': [1, 2, 3]
        }))
    ]
    
    validator = LeakageValidator()
    
    for test_name, df in test_cases:
        print(f"\n🧪 Testing: {test_name}")
        
        try:
            # Attempt validation
            result = validator.validate(df, copy_id=f"error_test_{test_name.replace(' ', '_')}")
            
            # If successful
            print(f"   ✅ Success: {result.decision}")
            
        except ValueError as e:
            # Handle validation errors (e.g., empty DataFrame)
            print(f"   ❌ ValueError: {e}")
            print(f"   → Fix: Ensure DataFrame is not empty and has valid structure")
            
        except KeyError as e:
            # Handle missing column errors
            print(f"   ❌ KeyError: {e}")
            print(f"   → Fix: Ensure required columns are present")
            
        except Exception as e:
            # Handle any other errors
            print(f"   ❌ Unexpected error: {type(e).__name__}: {e}")
            print(f"   → Contact support or check logs")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Run all basic examples."""
    print("\n" + "🎓" * 35)
    print("  BASIC USAGE EXAMPLES - Data Leakage Auto-Supervisor Agent")
    print("🎓" * 35)
    print("\nThese examples demonstrate common usage patterns for beginners.")
    
    try:
        # Run all examples
        example_1_single_file_validation()
        example_2_decision_handling()
        example_3_accessing_cleaned_data()
        example_4_batch_validation()
        example_5_context_manager()
        example_6_error_handling()
        
        print("\n\n" + "✨" * 35)
        print("  ALL BASIC EXAMPLES COMPLETED!")
        print("✨" * 35)
        print("\n💡 Next steps:")
        print("   1. Check examples/ml_workflow_example.py for advanced features")
        print("   2. Review policy/versions/v1/ to customize transformations")
        print("   3. Read CONFIGURATION.md for policy customization guide")
        print()
        
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
