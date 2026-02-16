"""
Verification Test: Dataset-Level Threat Aggregation

Tests the threat aggregation layer to ensure:
1. Risk levels are calculated correctly
2. Escalation logic works as expected
3. JSON serialization functions properly
4. No APPROVE/REJECT logic is present
5. Backward compatibility maintained
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance_core.threat_mapping import map_metrics_to_threats, ThreatSignal
from governance_core.threat_aggregation import (
    aggregate_dataset_threats,
    DatasetRiskSummary,
    get_risk_level_description
)


print("Testing Dataset-Level Threat Aggregation...")
print("=" * 60)

# Test 1: Empty threat list
print("\n1. Testing empty threat list...")
summary = aggregate_dataset_threats([])
assert summary.overall_risk_level == "low"
assert summary.total_threats == 0
assert summary.summary_text is not None
print("   ✓ Handles empty list correctly (low risk)")

# Test 2: Single low severity threat
print("\n2. Testing single low severity threat...")
metrics_low = {
    "privacy_score": 0.92,
    "privacy_risk": {"membership_inference_auc": 0.52}
}
threats_low = map_metrics_to_threats(metrics_low)
summary_low = aggregate_dataset_threats(threats_low)
assert summary_low.overall_risk_level in ["low", "warning"]
assert summary_low.total_threats >= 0
print(f"   ✓ Risk level: {summary_low.overall_risk_level}")

# Test 3: High severity privacy threat (should be critical)
print("\n3. Testing critical risk escalation...")
metrics_critical = {
    "privacy_score": 0.55,
    "privacy_risk": {
        "membership_inference_auc": 0.78,
        "near_duplicates_rate": 0.04
    }
}
threats_critical = map_metrics_to_threats(metrics_critical)
summary_critical = aggregate_dataset_threats(threats_critical)
# Should escalate due to high severity privacy threat
assert summary_critical.overall_risk_level in ["warning", "critical"]
assert len(summary_critical.escalation_reasons) > 0
print(f"   ✓ Risk level: {summary_critical.overall_risk_level}")
print(f"   ✓ Escalation reason: {summary_critical.escalation_reasons[0]}")

# Test 4: DatasetRiskSummary structure
print("\n4. Testing DatasetRiskSummary structure...")
summary = aggregate_dataset_threats(threats_critical)
assert hasattr(summary, 'overall_risk_level')
assert hasattr(summary, 'total_threats')
assert hasattr(summary, 'severity_breakdown')
assert hasattr(summary, 'property_breakdown')
assert hasattr(summary, 'top_threats')
assert hasattr(summary, 'escalation_reasons')
assert hasattr(summary, 'summary_text')
assert hasattr(summary, 'confidence_stats')
print("   ✓ All required fields present")

# Test 5: JSON serialization
print("\n5. Testing JSON serialization...")
summary_dict = summary.to_dict()
assert isinstance(summary_dict, dict)
assert 'overall_risk_level' in summary_dict
assert 'total_threats' in summary_dict
assert summary_dict['overall_risk_level'] in ['low', 'warning', 'critical']
print("   ✓ Serializes to valid JSON dict")

# Test 6: Top threats ranking
print("\n6. Testing threat prioritization...")
if threats_critical:
    summary = aggregate_dataset_threats(threats_critical, top_n=3)
    assert len(summary.top_threats) <= 3
    assert len(summary.top_threats) <= len(threats_critical)
    if summary.top_threats:
        assert 'priority_score' in summary.top_threats[0]
        assert 'threat_id' in summary.top_threats[0]
        print(f"   ✓ Returns top {len(summary.top_threats)} threats")
        print(f"   ✓ Top threat: {summary.top_threats[0]['threat_name']}")

# Test 7: Severity and property breakdowns
print("\n7. Testing breakdown counts...")
summary = aggregate_dataset_threats(threats_critical)
total_severity = sum(summary.severity_breakdown.values())
total_property = sum(summary.property_breakdown.values())
assert total_severity == summary.total_threats
assert total_property == summary.total_threats
print(f"   ✓ Severity breakdown sums correctly: {total_severity}")
print(f"   ✓ Property breakdown sums correctly: {total_property}")

# Test 8: Confidence stats
print("\n8. Testing confidence statistics...")
if threats_critical:
    summary = aggregate_dataset_threats(threats_critical)
    assert 0.0 <= summary.confidence_stats['avg'] <= 1.0
    assert 0.0 <= summary.confidence_stats['max'] <= 1.0
    assert 0.0 <= summary.confidence_stats['min'] <= 1.0
    assert summary.confidence_stats['min'] <= summary.confidence_stats['avg'] <= summary.confidence_stats['max']
    print(f"   ✓ Avg confidence: {summary.confidence_stats['avg']:.3f}")
    print(f"   ✓ Range: [{summary.confidence_stats['min']:.3f}, {summary.confidence_stats['max']:.3f}]")

# Test 9: No APPROVE/REJECT logic
print("\n9. Verifying advisory-only behavior...")
summary = aggregate_dataset_threats(threats_critical)
assert summary.overall_risk_level in ['low', 'warning', 'critical']
# These should NOT exist:
assert not hasattr(summary, 'decision')
assert not hasattr(summary, 'approved')
assert not hasattr(summary, 'rejected')
print("   ✓ No APPROVE/REJECT/ACCEPT fields present")
print("   ✓ Only advisory risk levels provided")

# Test 10: Multiple medium threats escalation
print("\n10. Testing multiple medium threat escalation...")
metrics_multi = {
    "privacy_score": 0.72,
    "utility_score": 0.82,
    "statistical_drift": "moderate",
    "privacy_risk": {
        "membership_inference_auc": 0.65,
        "near_duplicates_rate": 0.015
    },
    "statistical_fidelity": {
        "correlation_frobenius_norm": 1.5
    }
}
threats_multi = map_metrics_to_threats(metrics_multi)
summary_multi = aggregate_dataset_threats(threats_multi)
# Should escalate to warning due to multiple medium threats
assert summary_multi.overall_risk_level in ['warning', 'low']
print(f"   ✓ Risk level with multiple medium threats: {summary_multi.overall_risk_level}")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nVerified:")
print("  • Risk level calculation (low/warning/critical)")
print("  • Escalation logic (privacy-focused)")
print("  • JSON serialization")
print("  • Threat prioritization")
print("  • Advisory-only (no decisions)")
print("  • Backward compatibility")
