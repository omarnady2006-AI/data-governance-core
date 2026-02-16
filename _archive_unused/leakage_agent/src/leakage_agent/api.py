"""
Python API for ML engineers to validate training data.

Usage:
    from leakage_agent import LeakageValidator
    
    validator = LeakageValidator()
    result = validator.validate(df)
    
    if result.is_accepted:
        df_clean = result.cleaned_data
        df_clean.to_csv("training_data.csv")
"""

from typing import Dict, Optional, Union
import pandas as pd
from pathlib import Path
import uuid
from .pipeline import Pipeline


class ValidationResult:
    """
    Result object returned by LeakageValidator.
    
    Attributes:
        decision: "ACCEPT", "REJECT", or "QUARANTINE"
        cleaned_data: Transformed DataFrame (if accepted)
        report: Full validation report with metrics
        reason_codes: List of reason codes for decision
    """
    
    def __init__(self, decision: str, cleaned_data: pd.DataFrame, report: dict):
        self.decision = decision
        self.cleaned_data = cleaned_data
        self.report = report
        self.reason_codes = report.get("reason_codes", [])
    
    @property
    def is_accepted(self) -> bool:
        """True if data passed all validation checks."""
        return self.decision == "ACCEPT"
    
    @property
    def is_rejected(self) -> bool:
        """True if data failed quality checks."""
        return self.decision == "REJECT"
    
    @property
    def is_quarantined(self) -> bool:
        """True if data contains secrets or PII leakage."""
        return self.decision == "QUARANTINE"
    
    @property
    def metrics(self) -> dict:
        """Validation metrics (missing rates, duplicates, etc.)."""
        return self.report.get("metrics", {})
    
    @property
    def transform_summary(self) -> dict:
        """Summary of transformations applied."""
        return self.report.get("transform_summary", {})
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "metrics": self.metrics,
            "transform_summary": self.transform_summary
        }
    
    def __repr__(self) -> str:
        return f"ValidationResult(decision={self.decision}, reason_codes={self.reason_codes})"


def _get_default_policy_dir() -> str:
    """Get absolute path to default policy directory."""
    this_file = Path(__file__).resolve()
    # Path: src/leakage_agent/api.py -> parent(leakage_agent) -> parent(src) -> parent(leakage_agent) -> parent(project_root)
    project_root = this_file.parent.parent.parent.parent
    return str(project_root / "policy" / "versions" / "v1")

class LeakageValidator:
    """
    Simple API for ML engineers to validate training data against leakage policies.
    
    Example:
        >>> validator = LeakageValidator()
        >>> result = validator.validate(df)
        >>> if result.is_accepted:
        ...     result.cleaned_data.to_csv("approved_data.csv")
    """
    
    def __init__(self, policy_dir: Optional[str] = None):
        """
        Initialize validator with policy configuration.
        
        Args:
            policy_dir: Path to policy directory containing YAML configs
        """
        p_dir = policy_dir or _get_default_policy_dir()
        self.pipeline = Pipeline(p_dir)
        self.policy_dir = p_dir
    
    def validate(
        self, 
        df: pd.DataFrame, 
        copy_id: Optional[str] = None,
        out_dir: str = "outputs"
    ) -> ValidationResult:
        """
        Validate a DataFrame against leakage policies.
        
        Args:
            df: Input DataFrame to validate
            copy_id: Optional identifier for this dataset (auto-generated if None)
            out_dir: Output directory for reports and cleaned data
            
        Returns:
            ValidationResult object with decision, cleaned data, and metadata
            
        Example:
            >>> result = validator.validate(my_dataframe)
            >>> print(f"Decision: {result.decision}")
            >>> if result.is_accepted:
            ...     print(f"Cleaned data has {len(result.cleaned_data)} rows")
        """
        # Generate copy_id if not provided
        if copy_id is None:
            copy_id = f"auto_{uuid.uuid4().hex[:8]}"
        
        # Run pipeline
        cleaned_df, report = self.pipeline.run(df, out_dir=out_dir, copy_id=copy_id)
        
        # Return result object
        return ValidationResult(
            decision=report["decision"],
            cleaned_data=cleaned_df,
            report=report
        )
    
    def validate_batch(
        self, 
        dataframes: Dict[str, pd.DataFrame],
        out_dir: str = "outputs"
    ) -> Dict[str, ValidationResult]:
        """
        Validate multiple DataFrames in batch.
        
        Args:
            dataframes: Dict mapping copy_id -> DataFrame
            out_dir: Output directory for reports and cleaned data
            
        Returns:
            Dict mapping copy_id -> ValidationResult
            
        Example:
            >>> dfs = {"batch_1": df1, "batch_2": df2}
            >>> results = validator.validate_batch(dfs)
            >>> for copy_id, result in results.items():
            ...     print(f"{copy_id}: {result.decision}")
        """
        results = {}
        
        for copy_id, df in dataframes.items():
            result = self.validate(df, copy_id=copy_id, out_dir=out_dir)
            results[copy_id] = result
        
        return results
    
    def get_summary(self, results: Dict[str, ValidationResult]) -> dict:
        """
        Get summary statistics from batch validation results.
        
        Args:
            results: Dict of ValidationResult objects from validate_batch
            
        Returns:
            Summary dict with counts by decision
            
        Example:
            >>> results = validator.validate_batch(dataframes)
            >>> summary = validator.get_summary(results)
            >>> print(f"Accepted: {summary['accepted']}/{summary['total']}")
        """
        total = len(results)
        accepted = sum(1 for r in results.values() if r.is_accepted)
        rejected = sum(1 for r in results.values() if r.is_rejected)
        quarantined = sum(1 for r in results.values() if r.is_quarantined)
        
        return {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "quarantined": quarantined,
            "acceptance_rate": (accepted / total * 100) if total > 0 else 0
        }
    
    def __enter__(self):
        """Context manager support for resource cleanup."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup resources (for future extensions)."""
        pass
