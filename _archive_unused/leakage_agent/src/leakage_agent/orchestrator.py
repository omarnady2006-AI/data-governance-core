"""
Orchestrator for handling retry logic and data regeneration workflows.

The orchestrator sits ABOVE the pipeline and coordinates:
1. Running validation via Pipeline
2. Deciding whether to retry on REJECT
3. Providing guidance for data regeneration
4. Tracking retry attempts

Pipeline = single validation
Orchestrator = validation + retry workflow
"""

from typing import Callable, Optional, Dict
import pandas as pd
from .pipeline import Pipeline
from .api import ValidationResult


class RetryGuidance:
    """
    Actionable guidance for data regeneration based on rejection reasons.
    """
    
    def __init__(self, reason_codes: list):
        self.reason_codes = reason_codes
        self.guidance = self._build_guidance()
    
    def _build_guidance(self) -> dict:
        """
        Convert reason codes into actionable regeneration parameters.
        
        Returns:
            dict with regeneration hints
        """
        guidance = {}
        
        if "MISSING_TOO_HIGH" in self.reason_codes:
            guidance["increase_completeness"] = True
            guidance["target_missing_rate"] = 0.0
        
        if "DUPLICATES_TOO_HIGH" in self.reason_codes:
            guidance["reduce_duplicates"] = True
            guidance["ensure_unique_records"] = True
        
        if "OUT_OF_RANGE" in self.reason_codes:
            guidance["enforce_range_constraints"] = True
            guidance["check_numeric_bounds"] = True
        
        if "ENUM_VIOLATION" in self.reason_codes:
            guidance["enforce_allowed_values"] = True
            guidance["validate_categorical_fields"] = True
        
        if "SCHEMA_FAIL" in self.reason_codes:
            guidance["fix_schema"] = True
            guidance["ensure_critical_fields"] = True
        
        if "POSTCHECK_FAIL" in self.reason_codes:
            guidance["pii_still_present"] = True
            guidance["review_transformation_logic"] = True
        
        return guidance
    
    def to_dict(self) -> dict:
        return self.guidance
    
    def __repr__(self) -> str:
        return f"RetryGuidance({list(self.guidance.keys())})"


class DataOrchestrator:
    """
    Orchestrates validation with retry logic.
    
    The orchestrator handles:
    - Multiple validation attempts
    - Retry decision logic
    - Regeneration guidance
    - Attempt tracking
    
    Example:
        >>> orchestrator = DataOrchestrator(max_retries=3)
        >>> result = orchestrator.process_with_retry(
        ...     df, 
        ...     copy_id="data_001",
        ...     regenerator=my_data_generator
        ... )
    """
    
    def __init__(
        self, 
        policy_dir: str = "policy/versions/v1",
        max_retries: int = 3
    ):
        """
        Initialize orchestrator.
        
        Args:
            policy_dir: Path to policy configuration
            max_retries: Maximum number of regeneration attempts
        """
        self.pipeline = Pipeline(policy_dir)
        self.max_retries = max_retries
    
    def should_retry(
        self, 
        attempt: int, 
        decision: str, 
        reason_codes: list
    ) -> bool:
        """
        Determine if retry is warranted.
        
        Args:
            attempt: Current attempt number (0-indexed)
            decision: Validation decision
            reason_codes: List of reason codes
            
        Returns:
            bool: True if should retry
        """
        # Don't retry if max attempts reached
        if attempt >= self.max_retries:
            return False
        
        # Never retry QUARANTINE (requires manual review)
        if decision == "QUARANTINE":
            return False
        
        # Retry REJECT decisions
        if decision == "REJECT":
            # Don't retry schema failures (unfixable by regeneration)
            if "SCHEMA_FAIL" in reason_codes:
                return False
            # Retry other rejection reasons
            return True
        
        # Don't retry ACCEPT
        return False
    
    def get_retry_guidance(self, reason_codes: list) -> RetryGuidance:
        """
        Get actionable guidance for data regeneration.
        
        Args:
            reason_codes: List of validation failure codes
            
        Returns:
            RetryGuidance object with regeneration hints
        """
        return RetryGuidance(reason_codes)
    
    def process_with_retry(
        self,
        df: pd.DataFrame,
        copy_id: str,
        regenerator: Optional[Callable] = None,
        out_dir: str = "outputs"
    ) -> tuple:
        """
        Process data with automatic retry on REJECT.
        
        Args:
            df: Input DataFrame
            copy_id: Dataset identifier
            regenerator: Optional function that takes (df, guidance) and returns new df
            out_dir: Output directory
            
        Returns:
            tuple: (final_df, final_report, attempts_made)
            
        Example:
            >>> def my_regenerator(df, guidance):
            ...     # Apply guidance to generate better data
            ...     if guidance.get("reduce_duplicates"):
            ...         df = df.drop_duplicates()
            ...     return df
            >>> 
            >>> result = orchestrator.process_with_retry(
            ...     df, "data_001", regenerator=my_regenerator
            ... )
        """
        current_df = df
        attempt = 0
        
        while attempt <= self.max_retries:
            # Run validation
            df_out, report = self.pipeline.run(
                current_df, 
                out_dir=out_dir, 
                copy_id=f"{copy_id}_attempt_{attempt}"
            )
            
            decision = report["decision"]
            reason_codes = report["reason_codes"]
            
            # If accepted or quarantined, we're done
            if decision in ["ACCEPT", "QUARANTINE"]:
                return df_out, report, attempt + 1
            
            # Check if we should retry
            if not self.should_retry(attempt, decision, reason_codes):
                # No more retries, return final result
                return df_out, report, attempt + 1
            
            # Get guidance for regeneration
            if regenerator is None:
                # No regenerator provided, can't retry
                return df_out, report, attempt + 1
            
            guidance = self.get_retry_guidance(reason_codes)
            
            # Regenerate data using provided function
            try:
                current_df = regenerator(current_df, guidance.to_dict())
            except Exception as e:
                # Regeneration failed, return current result
                print(f"Warning: Regeneration failed: {e}")
                return df_out, report, attempt + 1
            
            attempt += 1
        
        # Max retries exceeded
        return df_out, report, attempt


class SimpleRegenerator:
    """
    Simple example regenerator that applies basic fixes based on guidance.
    
    This is a demonstration - real regenerators would use sophisticated
    data generation techniques (SDV, CTGAN, etc.)
    """
    
    @staticmethod
    def regenerate(df: pd.DataFrame, guidance: dict) -> pd.DataFrame:
        """
        Apply simple fixes based on retry guidance.
        
        Args:
            df: Current DataFrame
            guidance: Retry guidance dict
            
        Returns:
            Fixed DataFrame
        """
        df = df.copy()
        
        if guidance.get("reduce_duplicates"):
            df = df.drop_duplicates()
        
        if guidance.get("increase_completeness"):
            # Drop rows with missing critical values
            # (In real scenario, regenerate them instead)
            df = df.dropna(subset=["label"] if "label" in df.columns else [])
        
        if guidance.get("enforce_range_constraints"):
            # Clip values to valid ranges
            if "amount" in df.columns:
                df["amount"] = df["amount"].clip(lower=0, upper=1000000)
        
        return df
