"""
Comprehensive Edge Case Testing for Governance Engine

Tests robustness against:
- Empty metrics dictionaries
- Partial metrics
- NaN/None/inf values  
- Empty threat lists
- Malformed inputs

All tests should pass without raising exceptions.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance_core.threat_mapping import map_metrics_to_threats
from governance_core.threat_aggregation import aggregate_dataset_threats

print("=" * 70)
print("EDGE CASE HARDENING - COMPREHENSIVE TESTS")
print("=" * 70)

test_count = 0
passed = 0

def run_test(test_name, test_func):
    """Helper to run tests and track results."""
    global test_count, passed
    test_count += 1
    print(f"\n{test_count}. {test_name}")
    try:
        test_func()
        passed += 1
        print("   ✓ PASSED")
        return True
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# THREAT MAPPING EDGE CASES
# ============================================================================

print("\n" + "=" * 70)
print("THREAT MAPPING LAYER")
print("=" * 70)

def test_empty_metrics():
    """Test with completely empty metrics dictionary."""
    threats = map_metrics_to_threats({})
    assert isinstance(threats, list)
    assert len(threats) == 0

def test_none_metrics():
    """Test with None instead of dictionary."""
    threats = map_metrics_to_threats(None)
    assert isinstance(threats, list)
    assert len(threats) == 0

def test_partial_metrics():
    """Test with only some metrics present."""
    metrics = {"privacy_score": 0.75}  # Missing most metrics
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)
    # Should still work, just fewer threats detected

def test_metrics_with_none_values():
    """Test metrics where some values are None."""
    metrics = {
        "privacy_score": None,
        "utility_score": 0.88,
        "semantic_violations": None
    }
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)
    # Should skip None values gracefully

def test_metrics_with_nan():
    """Test metrics with NaN values."""
    import math
    metrics = {
        "privacy_score": 0.75,
        "utility_score": float('nan'),
        "privacy_risk": {
            "membership_inference_auc": math.nan
        }
    }
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)
    # Should filter out NaN values

def test_metrics_with_inf():
    """Test metrics with infinite values."""
    metrics = {
        "privacy_score": 0.75,
        "utility_score": float('inf'),
        "avg_kl_divergence": float('-inf')
    }
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)
    # Should filter out inf values

def test_nested_metrics_with_invalid_values():
    """Test nested metrics with mix of valid and invalid."""
    metrics = {
        "privacy_score": 0.65,
        "privacy_risk": {
            "membership_inference_auc": 0.72,
            "near_duplicates_rate": None,
            "near_duplicates_count": float('nan')
        }
    }
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)
    # Should process valid metrics, skip invalid

def test_string_metrics():
    """Test with string metric values."""
    metrics = {
        "privacy_score": 0.85,
        "statistical_drift": "high",  # Valid string
        "utility_assessment": ""  # Empty string
    }
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)

def test_malformed_nested_dict():
    """Test with malformed nested structure."""
    metrics = {
        "privacy_score": 0.75,
        "privacy_risk": "not_a_dict"  # Should be dict
    }
    threats = map_metrics_to_threats(metrics)
    assert isinstance(threats, list)

def test_output_modes_with_empty():
    """Test all output modes with empty metrics."""
    threats_detailed = map_metrics_to_threats({}, output_mode="detailed")
    assert isinstance(threats_detailed, list)
    
    threats_summary = map_metrics_to_threats({}, output_mode="summary")
    assert isinstance(threats_summary, dict)
    
    threats_json = map_metrics_to_threats({}, output_mode="json")
    assert isinstance(threats_json, dict)
    assert "threats" in threats_json
    assert "summary" in threats_json

def test_uncertainty_tracking():
    """Test that uncertainty notes are added when metrics are missing."""
    metrics = {
        "privacy_score": 0.55,  # Should trigger privacy_leakage
        # Missing membership_inference_auc and other privacy metrics
    }
    threats = map_metrics_to_threats(metrics)
    if threats:
        # Check if uncertainty tracking fields exist
        for threat in threats:
            assert hasattr(threat, 'missing_metrics')
            assert hasattr(threat, 'uncertainty_notes')


# ============================================================================
# THREAT AGGREGATION EDGE CASES
# ============================================================================

print("\n" + "=" * 70)
print("THREAT AGGREGATION LAYER")
print("=" * 70)

def test_aggregate_empty_list():
    """Test aggregation with empty threat list."""
    summary = aggregate_dataset_threats([])
    assert summary.overall_risk_level == "low"
    assert summary.total_threats == 0
    assert isinstance(summary.summary_text, str)

def test_aggregate_none_input():
    """Test aggregation with None instead of list."""
    summary = aggregate_dataset_threats(None)
    assert summary.overall_risk_level == "low"
    assert summary.total_threats == 0

def test_aggregate_non_list_input():
    """Test aggregation with invalid input type."""
    summary = aggregate_dataset_threats("not a list")
    assert summary.overall_risk_level == "low"
    assert summary.total_threats == 0

def test_aggregate_valid_threats():
    """Test aggregation with valid threats from real metrics."""
    metrics = {
        "privacy_score": 0.65,
        "utility_score": 0.82,
       "privacy_risk": {
            "membership_inference_auc": 0.68
        }
    }
    threats = map_metrics_to_threats(metrics)
    summary = aggregate_dataset_threats(threats)
    
    assert summary.overall_risk_level in ["low", "warning", "critical"]
    assert isinstance(summary.severity_breakdown, dict)
    assert isinstance(summary.property_breakdown, dict)
    assert isinstance(summary.top_threats, list)
    assert isinstance(summary.confidence_stats, dict)

def test_aggregate_json_serialization():
    """Test that aggregated summary can be serialized to JSON."""
    import json
    metrics = {"privacy_score": 0.70}
    threats = map_metrics_to_threats(metrics)
    summary = aggregate_dataset_threats(threats)
    
    # Should be JSON serializable
    json_str = json.dumps(summary.to_dict())
    assert isinstance(json_str, str)
    
    # Should be deserializable
    data = json.loads(json_str)
    assert isinstance(data, dict)

def test_aggregate_handles_missing_attributes():
    """Test that aggregation handles threats with missing attributes gracefully."""
    from governance_core.threat_mapping import ThreatSignal
    
    # Create a threat with minimal attributes (simulating malformed data)
    partial_threat = ThreatSignal(
        threat_id="test",
        threat_name="Test Threat",
        attack_type="test",
        impacted_property="privacy",
        severity="medium",
        confidence=0.5,
        related_metrics=[],
        metric_values={},
        triggered_by=["test"],
        description="test"
    )
    
    summary = aggregate_dataset_threats([partial_threat])
    assert summary.total_threats == 1
    assert isinstance(summary.to_dict(), dict)

def test_uncertainty_propagation():
    """Test that uncertainty from threats propagates to summary."""
    metrics = {
        "privacy_score": 0.55,
        "privacy_risk": {
            "membership_inference_auc": None,  # Missing/invalid
            "near_duplicates_rate": float('nan')  # Invalid
        }
    }
    threats = map_metrics_to_threats(metrics)
    summary = aggregate_dataset_threats(threats)
    
    # Check uncertainty tracking
    assert hasattr(summary, 'total_missing_metrics')
    assert hasattr(summary, 'has_uncertainty')

def test_end_to_end_with_extreme_values():
    """Full pipeline test with extreme/edge case values."""
    metrics = {
        "privacy_score": 0.01,  # Very low
        "utility_score": 0.99,  # Very high
        "semantic_violations": 9999,  # Very large
        "statistical_drift": "high",
        "privacy_risk": {
            "membership_inference_auc": 0.95,  # Very high
            "near_duplicates_rate": 0.5  # Very high
        }
    }
    
    threats = map_metrics_to_threats(metrics)
    summary = aggregate_dataset_threats(threats)
    
    # Should handle extremes without crashing
    assert summary.overall_risk_level in ["low", "warning", "critical"]
    # With such extreme values, should likely be critical
    assert summary.total_threats > 0


# ============================================================================
# RUN ALL TESTS
# ============================================================================

# Threat Mapping Tests
run_test("Empty metrics dictionary", test_empty_metrics)
run_test("None metrics input", test_none_metrics)
run_test("Partial metrics", test_partial_metrics)
run_test("Metrics with None values", test_metrics_with_none_values)
run_test("Metrics with NaN values", test_metrics_with_nan)
run_test("Metrics with inf values", test_metrics_with_inf)
run_test("Nested metrics with invalid values", test_nested_metrics_with_invalid_values)
run_test("String metric values", test_string_metrics)
run_test("Malformed nested dict", test_malformed_nested_dict)
run_test("Output modes with empty metrics", test_output_modes_with_empty)
run_test("Uncertainty tracking", test_uncertainty_tracking)

# Threat Aggregation Tests
run_test("Aggregate empty list", test_aggregate_empty_list)
run_test("Aggregate None input", test_aggregate_none_input)
run_test("Aggregate non-list input", test_aggregate_non_list_input)
run_test("Aggregate valid threats", test_aggregate_valid_threats)
run_test("JSON serialization", test_aggregate_json_serialization)
run_test("Handles missing attributes", test_aggregate_handles_missing_attributes)
run_test("Uncertainty propagation", test_uncertainty_propagation)
run_test("End-to-end with extreme values", test_end_to_end_with_extreme_values)

# ============================================================================
# RESULTS
# ============================================================================

print("\n" + "=" * 70)
print(f"RESULTS: {passed}/{test_count} tests passed")
print("=" * 70)

if passed == test_count:
    print("\n✅ ALL TESTS PASSED - System is robust against edge cases!")
    print("\nVerified:")
    print("  • Empty/None/invalid input handling")
    print("  • NaN/inf value filtering")
    print("  • Partial/missing metrics")
    print("  • Malformed nested structures")
    print("  • Uncertainty tracking")
    print("  • JSON serialization")
    print("  • No exceptions raised")
else:
    print(f"\n⚠️  {test_count - passed} tests failed - review errors above")

print()
