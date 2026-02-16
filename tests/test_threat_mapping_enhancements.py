"""
Quick verification test for threat mapping enhancements.

Tests:
1. Output modes (summary, detailed, json)
2. Stable threat IDs
3. Confidence scores
4. Triggered_by traceability
5. Backward compatibility
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance_core.threat_mapping import (
    map_metrics_to_threats,
    get_threat_summary,
    THREAT_MEMBERSHIP_INFERENCE,
    THREAT_PRIVACY_LEAKAGE,
)

# Test metrics
metrics = {
    "privacy_score": 0.70,
    "privacy_risk": {
        "membership_inference_auc": 0.65,
        "near_duplicates_rate": 0.005
    }
}

print("Testing Enhanced Threat Mapping...")
print("=" * 60)

# Test 1: Summary mode
print("\n1. Testing SUMMARY mode...")
summary = map_metrics_to_threats(metrics, output_mode="summary")
assert isinstance(summary, dict)
assert "total_threats" in summary
assert "severity_counts" in summary
print(f"   ✓ Returns dict with {summary['total_threats']} threats")

# Test 2: Detailed mode (default)
print("\n2. Testing DETAILED mode...")
threats = map_metrics_to_threats(metrics, output_mode="detailed")
assert isinstance(threats, list)
assert len(threats) > 0
assert hasattr(threats[0], 'confidence')
assert hasattr(threats[0], 'triggered_by')
print(f"   ✓ Returns list of {len(threats)} ThreatSignal objects")
print(f"   ✓ Confidence: {threats[0].confidence}")
print(f"   ✓ Triggered by: {threats[0].triggered_by[0] if threats[0].triggered_by else 'N/A'}")

# Test 3: JSON mode
print("\n3. Testing JSON mode...")
json_data = map_metrics_to_threats(metrics, output_mode="json")
assert isinstance(json_data, dict)
assert "threats" in json_data
assert "summary" in json_data
assert isinstance(json_data["threats"][0], dict)
print(f"   ✓ Returns serializable dict with {len(json_data['threats'])} threats")

# Test 4: Stable IDs
print("\n4. Testing stable threat IDs...")
threat_ids = [t.threat_id for t in threats]
assert THREAT_MEMBERSHIP_INFERENCE in threat_ids or THREAT_PRIVACY_LEAKAGE in threat_ids
print(f"   ✓ Using stable constants: {threat_ids[0]}")

# Test 5: Backward compatibility
print("\n5. Testing backward compatibility...")
threats_old_api = map_metrics_to_threats(metrics)  # No output_mode
assert isinstance(threats_old_api, list)
print("   ✓ Original API still works")

# Test 6: Confidence scores
print("\n6. Testing confidence scores...")
for threat in threats:
    assert 0.0 <= threat.confidence <= 1.0
    print(f"   ✓ {threat.threat_id}: confidence={threat.confidence:.3f} (valid range)")

# Test 7: Triggered by
print("\n7. Testing triggered_by traceability...")
for threat in threats:
    assert isinstance(threat.triggered_by, list)
    assert len(threat.triggered_by) > 0
    print(f"   ✓ {threat.threat_id}: {threat.triggered_by[0]}")


print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
