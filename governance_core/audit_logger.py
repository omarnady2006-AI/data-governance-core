"""
Audit Logger - Comprehensive audit trail system

Logs all governance decisions, LLM interactions, and metric computations
for full traceability and compliance.

Security properties:
- No PII stored in logs
- All LLM prompts/responses recorded
- Threshold changes tracked with justification
- Exportable for external audit systems
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """Single audit log entry."""
    
    timestamp: str
    entry_type: str  # "evaluation", "llm_call", "threshold_change", "transformation"
    evaluation_id: str
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


class AuditLogger:
    """
    Comprehensive audit logging system.
    
    Maintains complete audit trail of all governance operations:
    - Evaluation decisions
    - LLM interactions (prompts, responses, reasoning)
    - Metric computations
    - Threshold changes
    - Transformation operations
    
    Example:
        >>> logger = AuditLogger(output_dir="audit_logs")
        >>> logger.log_evaluation(
        ...     eval_id="eval_001",
        ...     metrics={"privacy_score": 0.85},
        ...     decision="acceptable",
        ...     reasoning="Privacy score exceeds threshold"
        ... )
    """
    
    def __init__(self, output_dir: str = "audit_logs", auto_flush: bool = True):
        """
        Initialize audit logger.
        
        Args:
            output_dir: Directory to store audit logs
            auto_flush: Whether to flush logs immediately (recommended)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.auto_flush = auto_flush
        
        # In-memory buffer for current session
        self.entries: List[AuditEntry] = []
        
        # Session log file
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.output_dir / f"audit_session_{session_id}.jsonl"
        
        logger.info(f"Audit logger initialized: {self.session_file}")
    
    def _create_entry(
        self,
        entry_type: str,
        evaluation_id: str,
        data: Dict[str, Any]
    ) -> AuditEntry:
        """Create an audit entry with timestamp."""
        return AuditEntry(
            timestamp=datetime.now().isoformat(),
            entry_type=entry_type,
            evaluation_id=evaluation_id,
            data=data
        )
    
    def _write_entry(self, entry: AuditEntry):
        """Write entry to log file."""
        self.entries.append(entry)
        
        if self.auto_flush:
            with open(self.session_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
    
    def log_evaluation(
        self,
        eval_id: str,
        metrics: Dict[str, Any],
        decision: str,
        reasoning: str,
        context: Optional[Dict] = None
    ):
        """
        Log a complete evaluation decision.
        
        Args:
            eval_id: Unique evaluation identifier
            metrics: All metric values computed
            decision: Final decision/recommendation
            reasoning: LLM-generated or rule-based reasoning
            context: Optional context (dataset info, thresholds, etc.)
        """
        entry = self._create_entry(
            entry_type="evaluation",
            evaluation_id=eval_id,
            data={
                "metrics": metrics,
                "decision": decision,
                "reasoning": reasoning,
                "context": context or {}
            }
        )
        self._write_entry(entry)
        logger.info(f"Logged evaluation: {eval_id} -> {decision}")
    
    def log_llm_interaction(
        self,
        eval_id: str,
        provider: str,
        prompt: str,
        system_prompt: Optional[str],
        response: str,
        metadata: Optional[Dict] = None
    ):
        """
        Log LLM API interaction.
        
        SECURITY: Ensure prompt/response contain NO PII.
        
        Args:
            eval_id: Associated evaluation ID
            provider: LLM provider name
            prompt: User prompt sent to LLM
            system_prompt: System prompt used
            response: LLM response
            metadata: Additional metadata (temperature, tokens, etc.)
        """
        # Hash the full prompt/response for verification
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        response_hash = hashlib.sha256(response.encode()).hexdigest()[:16]
        
        entry = self._create_entry(
            entry_type="llm_call",
            evaluation_id=eval_id,
            data={
                "provider": provider,
                "prompt": prompt,  # Stored for audit - must be sanitized!
                "system_prompt": system_prompt,
                "response": response,
                "prompt_hash": prompt_hash,
                "response_hash": response_hash,
                "metadata": metadata or {}
            }
        )
        self._write_entry(entry)
        logger.debug(f"Logged LLM interaction: {eval_id} via {provider}")
    
    def log_threshold_change(
        self,
        eval_id: str,
        field: str,
        old_value: Any,
        new_value: Any,
        justification: str,
        approver: Optional[str] = None,
        auto_applied: bool = False
    ):
        """
        Log threshold configuration change.
        
        Args:
            eval_id: Associated evaluation ID
            field: Threshold field name
            old_value: Previous value
            new_value: New value
            justification: Reason for change
            approver: Who approved the change (if manual)
            auto_applied: Whether applied automatically by agent
        """
        entry = self._create_entry(
            entry_type="threshold_change",
            evaluation_id=eval_id,
            data={
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "justification": justification,
                "approver": approver,
                "auto_applied": auto_applied
            }
        )
        self._write_entry(entry)
        logger.warning(
            f"Threshold changed: {field} {old_value} -> {new_value} "
            f"(auto={auto_applied})"
        )
    
    def log_transformation(
        self,
        eval_id: str,
        transformation_type: str,
        details: Dict[str, Any]
    ):
        """
        Log data transformation operation.
        
        Args:
            eval_id: Associated evaluation ID
            transformation_type: Type of transformation
            details: Transformation details (no raw data!)
        """
        entry = self._create_entry(
            entry_type="transformation",
            evaluation_id=eval_id,
            data={
                "transformation_type": transformation_type,
                "details": details
            }
        )
        self._write_entry(entry)
    
    def log_metric_computation(
        self,
        eval_id: str,
        metric_name: str,
        value: Any,
        computation_time_ms: Optional[float] = None
    ):
        """
        Log individual metric computation.
        
        Args:
            eval_id: Associated evaluation ID
            metric_name: Name of the metric
            value: Computed value
            computation_time_ms: Time taken to compute (milliseconds)
        """
        entry = self._create_entry(
            entry_type="metric_computation",
            evaluation_id=eval_id,
            data={
                "metric_name": metric_name,
                "value": value,
                "computation_time_ms": computation_time_ms
            }
        )
        self._write_entry(entry)
    
    def export_audit_trail(
        self,
        filepath: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = "json"
    ):
        """
        Export audit trail for external analysis.
        
        Args:
            filepath: Output file path
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            format: Output format ("json" or "jsonl")
        """
        filtered_entries = self.entries
        
        if start_date:
            filtered_entries = [
                e for e in filtered_entries
                if e.timestamp >= start_date
            ]
        
        if end_date:
            filtered_entries = [
                e for e in filtered_entries
                if e.timestamp <= end_date
            ]
        
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(output_path, "w") as f:
                json.dump(
                    [e.to_dict() for e in filtered_entries],
                    f,
                    indent=2
                )
        elif format == "jsonl":
            with open(output_path, "w") as f:
                for entry in filtered_entries:
                    f.write(json.dumps(entry.to_dict()) + "\n")
        else:
            raise ValueError(f"Unknown format: {format}")
        
        logger.info(
            f"Exported {len(filtered_entries)} audit entries to {filepath}"
        )
    
    def get_evaluation_history(self, eval_id: str) -> List[AuditEntry]:
        """
        Get all audit entries for a specific evaluation.
        
        Args:
            eval_id: Evaluation ID
            
        Returns:
            List of audit entries for this evaluation
        """
        return [e for e in self.entries if e.evaluation_id == eval_id]
    
    def get_llm_calls(self, eval_id: Optional[str] = None) -> List[AuditEntry]:
        """
        Get all LLM interaction logs.
        
        Args:
            eval_id: Optional evaluation ID filter
            
        Returns:
            List of LLM call audit entries
        """
        entries = [e for e in self.entries if e.entry_type == "llm_call"]
        if eval_id:
            entries = [e for e in entries if e.evaluation_id == eval_id]
        return entries
    
    def flush(self):
        """Flush all buffered entries to disk."""
        if not self.auto_flush:
            with open(self.session_file, "a") as f:
                for entry in self.entries:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            logger.info(f"Flushed {len(self.entries)} entries to {self.session_file}")


class NullAuditLogger:
    """
    No-op audit logger for embedded / library use.

    Used by default when the engine runs inside a host application
    (VS Code extension, web service, unit tests) where automatic
    filesystem writes are not acceptable.

    Satisfies the full AuditLogger method surface so it can be passed
    anywhere an AuditLogger is expected without any conditional checks
    in the call sites.

    Guarantees:
    - Creates no directories.
    - Writes no files.
    - Holds no in-memory buffer.
    - All calls are silent no-ops.
    """

    # Expose the same attribute names that call sites may inspect.
    session_file = None
    entries: list = []

    def log_metric_computation(self, *args, **kwargs) -> None:  # noqa: D401
        """No-op."""

    def log_evaluation(self, *args, **kwargs) -> None:
        """No-op."""

    def log_event(self, *args, **kwargs) -> None:
        """No-op."""

    def log_llm_interaction(self, *args, **kwargs) -> None:
        """No-op."""

    def log_threshold_change(self, *args, **kwargs) -> None:
        """No-op."""

    def log_transformation(self, *args, **kwargs) -> None:
        """No-op."""

    def export_audit_trail(self, *args, **kwargs) -> None:
        """No-op."""

    def get_evaluation_history(self, eval_id: str) -> list:
        """Returns empty list — no entries are ever stored."""
        return []

    def get_llm_calls(self, eval_id=None) -> list:
        """Returns empty list — no entries are ever stored."""
        return []

    def flush(self) -> None:
        """No-op."""
