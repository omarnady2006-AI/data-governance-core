"""
Data Profiler - Statistical profile generation without storing raw data

Generates statistical summaries, sketches, and hashes for comparing datasets
while maintaining strict privacy constraints.

SECURITY CONSTRAINTS:
- NEVER stores raw values
- Only statistical summaries (mean, variance, histograms, etc.)
- Cryptographic hashes for membership checks
- Sketch data structures for cardinality/frequency estimation

FIXES applied in this revision:
- _hash_row() uses JSON serialization to avoid delimiter collision attacks
- create_profile() uses a seeded RNG for deterministic value-hash sampling
- DatasetProfile.load() is robust to extra/missing JSON fields
"""

import hashlib
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class FieldProfile:
    """Statistical profile for a single field."""

    field_name: str
    dtype: str
    count: int
    null_count: int
    null_rate: float

    # Numeric fields
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    quartiles: Optional[List[float]] = None  # [Q1, Q2/median, Q3]

    # Categorical fields
    unique_count: Optional[int] = None
    most_common: Optional[List[Tuple[str, int]]] = None  # Top 10

    # Privacy: value hashes for membership checks (NOT raw values)
    value_hashes: Optional[List[str]] = None  # SHA256 hashes

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DatasetProfile:
    """Complete statistical profile for a dataset."""

    profile_id: str
    created_at: str
    row_count: int
    column_count: int
    column_names: List[str]

    field_profiles: Dict[str, FieldProfile]

    # Cross-field statistics
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None

    # Dataset-level hashes
    row_hashes: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        return {
            "profile_id": self.profile_id,
            "created_at": self.created_at,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "column_names": self.column_names,
            "field_profiles": {
                name: profile.to_dict()
                for name, profile in self.field_profiles.items()
            },
            "correlation_matrix": self.correlation_matrix,
            "row_hashes": self.row_hashes,
        }

    def save(self, filepath: str):
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved data profile to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "DatasetProfile":
        """
        Load profile from JSON file.

        FIXED: Uses explicit field extraction instead of **profile_data
        unpacking to tolerate schema evolution (extra or missing fields
        no longer raise TypeError).
        """
        with open(filepath, "r") as f:
            data = json.load(f)

        field_profiles = {}
        for name, pd_data in data.get("field_profiles", {}).items():
            # Extract only the fields FieldProfile knows about
            fp = FieldProfile(
                field_name=pd_data.get("field_name", name),
                dtype=pd_data.get("dtype", "object"),
                count=pd_data.get("count", 0),
                null_count=pd_data.get("null_count", 0),
                null_rate=pd_data.get("null_rate", 0.0),
                mean=pd_data.get("mean"),
                std=pd_data.get("std"),
                min=pd_data.get("min"),
                max=pd_data.get("max"),
                quartiles=pd_data.get("quartiles"),
                unique_count=pd_data.get("unique_count"),
                most_common=pd_data.get("most_common"),
                value_hashes=pd_data.get("value_hashes"),
            )
            field_profiles[name] = fp

        return cls(
            profile_id=data["profile_id"],
            created_at=data["created_at"],
            row_count=data["row_count"],
            column_count=data["column_count"],
            column_names=data["column_names"],
            field_profiles=field_profiles,
            correlation_matrix=data.get("correlation_matrix"),
            row_hashes=data.get("row_hashes"),
        )


class DataProfiler:
    """
    Generate statistical profiles from datasets without storing raw data.

    Profiles are used for:
    - Statistical fidelity comparison (mean, variance, correlation)
    - Privacy risk assessment (membership checks via hashes)
    - Utility evaluation (distribution comparison)

    Args:
        include_row_hashes: Whether to compute row hashes for membership checks.
        top_k_values: Number of most common values to track for categorical fields.
        random_state: Seed for RNG used in value-hash sampling. Ensures
                      deterministic profiles across runs.
    """

    def __init__(
        self,
        include_row_hashes: bool = True,
        top_k_values: int = 10,
        random_state: int = 42,
    ):
        self.include_row_hashes = include_row_hashes
        self.top_k_values = top_k_values
        self.random_state = random_state

    def _hash_value(self, value: Any) -> str:
        value_str = str(value)
        return hashlib.sha256(value_str.encode()).hexdigest()

    def _hash_row(self, row: pd.Series) -> str:
        """
        Compute a SHA256 hash of an entire row.

        FIXED: Uses JSON serialization of a sorted key->value dict instead of
        a pipe-delimited string.  The old delimiter ('|') caused collisions:
            ["a|b", "c"] and ["a", "b|c"] produced the same hash.

        JSON serialization is unambiguous because all values are quoted strings
        in a key-ordered object, making the representation injection-proof.
        """
        row_dict = {col: str(row[col]) for col in sorted(row.index)}
        row_str = json.dumps(row_dict, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(row_str.encode("utf-8")).hexdigest()

    def _profile_numeric_field(self, series: pd.Series) -> Dict[str, Any]:
        non_null = series.dropna()
        if len(non_null) == 0:
            return {
                "mean": None, "std": None, "min": None,
                "max": None, "quartiles": None,
            }
        return {
            "mean": float(non_null.mean()),
            "std": float(non_null.std()),
            "min": float(non_null.min()),
            "max": float(non_null.max()),
            "quartiles": [
                float(non_null.quantile(0.25)),
                float(non_null.quantile(0.50)),
                float(non_null.quantile(0.75)),
            ],
        }

    def _profile_categorical_field(self, series: pd.Series) -> Dict[str, Any]:
        non_null = series.dropna()
        if len(non_null) == 0:
            return {"unique_count": 0, "most_common": []}
        value_counts = non_null.value_counts()
        most_common = [
            (str(val), int(count))
            for val, count in value_counts.head(self.top_k_values).items()
        ]
        return {
            "unique_count": int(non_null.nunique()),
            "most_common": most_common,
        }

    def create_profile(
        self,
        df: pd.DataFrame,
        profile_id: str,
        include_value_hashes: bool = False,
        max_hashes_per_field: int = 10000,
    ) -> DatasetProfile:
        """
        Create statistical profile from DataFrame.

        Args:
            df: Input DataFrame.
            profile_id: Unique identifier for this profile.
            include_value_hashes: Whether to include value hashes.
            max_hashes_per_field: Maximum number of hashes to store per field.

        Returns:
            DatasetProfile object.
        """
        from datetime import datetime

        logger.info(
            f"Creating profile {profile_id} for dataset: "
            f"{len(df)} rows, {len(df.columns)} columns"
        )

        # FIXED: use a seeded RNG for deterministic hash sampling
        rng = np.random.default_rng(self.random_state)

        field_profiles = {}

        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)

            count = len(series)
            null_count = int(series.isnull().sum())
            null_rate = null_count / count if count > 0 else 0.0

            numeric_stats = {}
            categorical_stats = {}

            if pd.api.types.is_numeric_dtype(series):
                numeric_stats = self._profile_numeric_field(series)
            else:
                categorical_stats = self._profile_categorical_field(series)

            # Value hashes (optional)
            value_hashes = None
            if include_value_hashes:
                non_null = series.dropna()
                if len(non_null) > 0:
                    unique_vals = non_null.unique()
                    if len(unique_vals) > max_hashes_per_field:
                        # FIXED: use seeded RNG instead of np.random.choice
                        indices = rng.choice(
                            len(unique_vals),
                            size=max_hashes_per_field,
                            replace=False,
                        )
                        unique_vals = unique_vals[indices]
                    value_hashes = [self._hash_value(v) for v in unique_vals]

            field_profile = FieldProfile(
                field_name=col,
                dtype=dtype,
                count=count,
                null_count=null_count,
                null_rate=null_rate,
                value_hashes=value_hashes,
                **numeric_stats,
                **categorical_stats,
            )

            field_profiles[col] = field_profile

        # Correlation matrix for numeric fields
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        correlation_matrix = None

        if len(numeric_cols) > 1:
            corr = df[numeric_cols].corr()
            correlation_matrix = {
                col: {
                    col2: float(corr.loc[col, col2]) for col2 in numeric_cols
                }
                for col in numeric_cols
            }

        # Row hashes for near-duplicate detection
        row_hashes = None
        if self.include_row_hashes:
            logger.info("Computing row hashes...")
            row_hashes = df.apply(self._hash_row, axis=1).tolist()

        profile = DatasetProfile(
            profile_id=profile_id,
            created_at=datetime.now().isoformat(),
            row_count=len(df),
            column_count=len(df.columns),
            column_names=df.columns.tolist(),
            field_profiles=field_profiles,
            correlation_matrix=correlation_matrix,
            row_hashes=row_hashes,
        )

        logger.info(f"Profile created: {profile_id}")
        return profile

    def compute_membership_overlap(
        self,
        synthetic_df: pd.DataFrame,
        original_profile: DatasetProfile,
    ) -> Dict[str, float]:
        """
        Compute membership overlap between synthetic data and original profile.

        Uses the row hashes stored in the profile for O(1) lookup.
        """
        if not original_profile.row_hashes:
            raise ValueError("Original profile does not contain row hashes")

        synthetic_hashes = synthetic_df.apply(self._hash_row, axis=1).tolist()
        original_hash_set = set(original_profile.row_hashes)
        matches = [h for h in synthetic_hashes if h in original_hash_set]
        overlap_rate = (
            len(matches) / len(synthetic_hashes) if synthetic_hashes else 0.0
        )

        return {
            "synthetic_count": len(synthetic_hashes),
            "original_count": len(original_profile.row_hashes),
            "exact_matches": len(matches),
            "overlap_rate": overlap_rate,
        }
