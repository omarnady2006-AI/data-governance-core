from pathlib import Path
from .config_loader import ConfigLoader
from .canonicalize import canonicalize
from .forbidden_scan import forbidden_scan
from .normalize import normalize
from .transform_engine import transform_engine
from .postcheck import postcheck
from .engine import calculate_metrics
from .decision import make_decision
from .reporting import generate_report
from .io_utils import write_outputs
from .lineage import LineageTracker

def _get_default_policy_dir() -> str:
    """Get absolute path to default policy directory."""
    this_file = Path(__file__).resolve()
    # Path: src/leakage_agent/pipeline.py -> parent(leakage_agent) -> parent(src) -> parent(leakage_agent) -> parent(project_root)
    project_root = this_file.parent.parent.parent.parent
    return str(project_root / "policy" / "versions" / "v1")

class Pipeline:
    def __init__(self, policy_dir=None, lineage_tracker=None):
        self.policy_dir = policy_dir or _get_default_policy_dir()
        self.config = ConfigLoader(self.policy_dir)
        self.lineage = lineage_tracker or LineageTracker()  # Shared instance

    def run(self, df, out_dir="outputs", copy_id="default", source_info=None):
        # Record ingestion (if source_info provided)
        if source_info:
            self.lineage.record_ingestion(copy_id, source_info)
        
        # 1. Canonicalize
        df_can, mapping_info = canonicalize(df, self.config)
        self.lineage.record_transformation(copy_id, "canonicalize", {
            "mappings_applied": mapping_info["canonical_mapping_count"],
            "collisions": len(mapping_info.get("collisions", []))
        })
        
        # 2. Forbidden Scan
        forbidden_info = forbidden_scan(df_can, self.config)
        self.lineage.record_transformation(copy_id, "forbidden_scan", {
            "forbidden_found": forbidden_info["forbidden_found"],
            "hits_count": len(forbidden_info["forbidden_hits_columns"]) + 
                         len(forbidden_info["forbidden_hits_value_patterns"])
        })
        
        # 3. Normalization
        df_norm, norm_changes = normalize(df_can, self.config)
        self.lineage.record_transformation(copy_id, "normalize", {
            "changes_count": norm_changes
        })
        
        # 3.5. Remove duplicates (FIXED: was missing)
        df_deduplicated = df_norm.drop_duplicates()
        duplicates_removed = len(df_norm) - len(df_deduplicated)
        self.lineage.record_transformation(copy_id, "deduplicate", {
            "duplicates_removed": duplicates_removed
        })
        
        # 4. Transforms
        df_trans, trans_summary = transform_engine(df_deduplicated, self.config)
        self.lineage.record_transformation(copy_id, "transform", {
            "tokenized_count": sum(trans_summary.get("tokenized_fields_count", {}).values()),
            "dropped_columns": len(trans_summary.get("dropped_columns", [])),
            "derived_fields": len(trans_summary.get("derived_fields_created", []))
        })
        
        # Record version after transforms
        self.lineage.record_version(copy_id, df_trans, "post_transform")
        
        # Enrich transform_summary
        trans_summary.update({
            "copy_id": copy_id,  # FIXED: Added missing copy_id required by schema
            "canonical_mapping_count": mapping_info["canonical_mapping_count"],
            "normalization_changes_count": norm_changes,
            "forbidden_found": forbidden_info["forbidden_found"],
            "forbidden_hits": forbidden_info["forbidden_hits_columns"] + forbidden_info["forbidden_hits_value_patterns"],
            "duplicates_removed": duplicates_removed,  # FIXED: Use actual count instead of hardcoded 0
            "missing_label_count": int(df_trans["label"].isnull().sum()) if "label" in df_trans.columns else 0,
            "rows_dropped_missing": 0,
            "rows_dropped_invalid": 0
        })
        
        # 5. Postcheck
        pc_results = postcheck(df_trans, self.config)
        
        # 6. Metrics
        metrics = calculate_metrics(df_trans, pc_results, self.config)
        
        # 7. Decision
        decision, reason_codes = make_decision(metrics, forbidden_info, self.config)
        
        # 8. Reporting
        report = generate_report(copy_id, decision, reason_codes, metrics, pc_results, forbidden_info, trans_summary)
        
        # 9. Write Outputs
        write_outputs(df_trans, report, trans_summary, decision, out_dir, copy_id)
        
        # Record final version with decision
        self.lineage.record_version(copy_id, df_trans, "final", {
            "decision": decision,
            "reason_codes": reason_codes
        })
        
        return df_trans, report