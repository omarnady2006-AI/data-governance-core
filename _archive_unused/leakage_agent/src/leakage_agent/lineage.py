"""
Data lineage and provenance tracking.

Tracks:
- Where data came from (source_info)
- What transformations were applied
- Version history via data hashing
- Full audit trail
"""

import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, List
import pandas as pd


class LineageTracker:
    """
    Track data lineage and versioning for audit purposes.
    
    Example:
        >>> tracker = LineageTracker()
        >>> tracker.record_ingestion("copy_001", {
        ...     "source": "synthetic_generator",
        ...     "model": "SDV_CTGAN"
        ... })
        >>> tracker.record_transformation("copy_001", "canonicalize", {...})
    """
    
    def __init__(self, storage_backend: Optional[str] = None):
        """
        Initialize lineage tracker.
        
        Args:
            storage_backend: Path to persistent storage (None = in-memory only)
        """
        self.lineage_db = {}  # In-memory storage: copy_id -> lineage record
        self.storage_backend = storage_backend
    
    def record_ingestion(self, copy_id: str, source_info: dict):
        """
        Record where data came from.
        
        Args:
            copy_id: Dataset identifier
            source_info: Dict with source metadata
                - source_type: "synthetic_generator", "real_data", "augmented", etc.
                - generator_model: Model name (e.g., "SDV_CTGAN")
                - parent_dataset: Parent dataset name/ID
                - timestamp: Ingestion timestamp
                - additional custom fields
        
        Example:
            >>> tracker.record_ingestion("copy_001", {
            ...     "source_type": "synthetic",
            ...     "generator_model": "SDV_CTGAN",
            ...     "parent_dataset": "real_data_v2",
            ...     "generation_config": {"epochs": 100}
            ... })
        """
        if copy_id not in self.lineage_db:
            self.lineage_db[copy_id] = {
                "copy_id": copy_id,
                "created_at": datetime.now().isoformat(),
                "source_info": {},
                "transformations": [],
                "versions": []
            }
        
        self.lineage_db[copy_id]["source_info"] = {
            **source_info,
            "ingested_at": datetime.now().isoformat()
        }
        
        self._persist()
    
    def record_transformation(
        self, 
        copy_id: str, 
        stage: str, 
        details: dict,
        data_hash: Optional[str] = None
    ):
        """
        Record a transformation stage.
        
        Args:
            copy_id: Dataset identifier
            stage: Transformation stage name
            details: Stage-specific details
            data_hash: Optional hash of data after this stage
        
        Example:
            >>> tracker.record_transformation("copy_001", "canonicalize", {
            ...     "mappings_applied": 5,
            ...     "collisions": 0
            ... })
        """
        if copy_id not in self.lineage_db:
            self.record_ingestion(copy_id, {})
        
        transform_record = {
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        if data_hash:
            transform_record["data_hash"] = data_hash
        
        self.lineage_db[copy_id]["transformations"].append(transform_record)
        self._persist()
    
    def compute_data_hash(self, df: pd.DataFrame) -> str:
        """
        Compute deterministic hash of DataFrame for versioning.
        
        Args:
            df: DataFrame to hash
            
        Returns:
            SHA-256 hash string
        
        Note:
            This creates a hash of the data content, not the DataFrame object.
            Same data = same hash, regardless of DataFrame creation method.
        """
        # Sort columns and rows for deterministic hashing
        df_sorted = df.sort_index(axis=1).sort_index(axis=0)
        
        # Convert to records and replace NaN with None for consistent serialization
        records = df_sorted.to_dict(orient='records')
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
        
        # Use json.dumps with sort_keys for deterministic output
        data_str = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        
        # Hash
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def record_version(
        self, 
        copy_id: str, 
        df: pd.DataFrame,
        stage: str,
        metadata: Optional[dict] = None
    ):
        """
        Record a versioned snapshot of the data.
        
        Args:
            copy_id: Dataset identifier
            df: Current DataFrame state
            stage: Stage name for this version
            metadata: Optional additional metadata
        """
        if copy_id not in self.lineage_db:
            self.record_ingestion(copy_id, {})
        
        data_hash = self.compute_data_hash(df)
        
        version_record = {
            "version_id": f"v{len(self.lineage_db[copy_id]['versions']) + 1}",
            "stage": stage,
            "data_hash": data_hash,
            "timestamp": datetime.now().isoformat(),
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "metadata": metadata or {}
        }
        
        self.lineage_db[copy_id]["versions"].append(version_record)
        self._persist()
    
    def get_lineage(self, copy_id: str) -> Optional[dict]:
        """
        Retrieve full lineage history for a dataset.
        
        Args:
            copy_id: Dataset identifier
            
        Returns:
            Lineage record dict or None if not found
        """
        return self.lineage_db.get(copy_id)
    
    def get_lineage_summary(self, copy_id: str) -> Optional[dict]:
        """
        Get summarized lineage information.
        
        Returns:
            Summary dict with key metrics
        """
        lineage = self.get_lineage(copy_id)
        if not lineage:
            return None
        
        return {
            "copy_id": copy_id,
            "source_type": lineage.get("source_info", {}).get("source_type"),
            "created_at": lineage.get("created_at"),
            "transformation_count": len(lineage.get("transformations", [])),
            "version_count": len(lineage.get("versions", [])),
            "latest_version": lineage.get("versions", [])[-1] if lineage.get("versions") else None
        }
    
    def _persist(self):
        """Persist lineage data to storage backend (if configured)."""
        if self.storage_backend:
            try:
                with open(self.storage_backend, 'w') as f:
                    json.dump(self.lineage_db, f, indent=2)
            except Exception as e:
                print(f"Warning: Failed to persist lineage: {e}")
    
    def load_from_storage(self):
        """Load lineage data from storage backend."""
        if self.storage_backend:
            try:
                with open(self.storage_backend, 'r') as f:
                    self.lineage_db = json.load(f)
            except FileNotFoundError:
                pass  # No existing storage file
            except Exception as e:
                print(f"Warning: Failed to load lineage: {e}")
