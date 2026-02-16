import yaml
from pathlib import Path

class ConfigLoader:
    def __init__(self, policy_dir: str = "policy/versions/v1"):
        self.policy_dir = Path(policy_dir)
        self.policy = self._load_yaml("policy.yaml")
        self.thresholds = self._load_yaml("thresholds.yaml")
        self.forbidden = self._load_yaml("forbidden.yaml")
        self.reason_codes = self._load_yaml("reason_codes.yaml")
        self.column_dictionary = self._load_yaml("column_dictionary.yaml")
        
        # Ensure rate_unit is set
        if "rate_unit" not in self.thresholds:
            self.thresholds["rate_unit"] = "percent"

    def _load_yaml(self, filename: str):
        path = self.policy_dir / filename
        if not path.exists():
            return {}
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def get_field_action(self, field_name):
        # This is used after canonicalization, so field_name should be canonical
        return self.policy.get("actions", {}).get(field_name, self.policy.get("default_action", {"action": "KEEP"}))
    
    def get_field_constraints(self, field_name: str) -> dict:
        """
        Get validation constraints for a field from column_dictionary.
        
        Args:
            field_name: Canonical field name
        
        Returns:
            dict with keys: range_min, range_max, allowed_values, expected_type, nullable
            Returns None if field not found
        """
        for col in self.column_dictionary.get("columns", []):
            if col.get("name") == field_name:
                return {
                    "range_min": col.get("range_min"),
                    "range_max": col.get("range_max"),
                    "allowed_values": col.get("allowed_values"),
                    "expected_type": col.get("expected_type"),
                    "nullable": col.get("nullable", True)  # Default: nullable
                }
        return None
