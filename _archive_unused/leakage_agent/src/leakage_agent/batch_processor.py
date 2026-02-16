"""
Batch processing for multiple datasets.

Processes directories of CSV files with:
- Parallel processing
- Progress tracking
- Summary statistics
"""

from pathlib import Path
from typing import Dict, List
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
from .pipeline import Pipeline


def _get_default_policy_dir() -> str:
    """
    Get the default policy directory path, resolved relative to the project root.
    
    Returns:
        Absolute path to policy/versions/v1 directory
    """
    # Start from this file's location and navigate to project root
    # src/leakage_agent/batch_processor.py -> leakage_agent/ -> src/ -> leakage_agent/ -> project root
    this_file = Path(__file__).resolve()
    # Navigate: batch_processor.py -> leakage_agent -> src -> leakage_agent -> project root (outside-agent)
    project_root = this_file.parent.parent.parent.parent
    policy_dir = project_root / "policy" / "versions" / "v1"
    return str(policy_dir)


class BatchProcessor:
    """
    Process multiple datasets with parallel execution and progress tracking.
    
    Example:
        >>> processor = BatchProcessor(max_workers=4)
        >>> summary = processor.process_directory("data/candidates/")
        >>> print(f"Accepted: {summary['accepted']}/{summary['total']}")
    """
    
    def __init__(
        self, 
        pipeline: Pipeline = None,
        max_workers: int = 4,
        verbose: bool = True
    ):
        """
        Initialize batch processor.
        
        Args:
            pipeline: Pipeline instance (creates new one if None)
            max_workers: Number of parallel workers
            verbose: Show progress bar (requires tqdm)
        """
        self.pipeline = pipeline or Pipeline()
        self.max_workers = max_workers
        self.verbose = verbose and HAS_TQDM
    
    def process_directory(
        self, 
        input_dir: str, 
        out_dir: str = "outputs",
        pattern: str = "*.csv"
    ) -> dict:
        """
        Process all CSV files in a directory.
        
        Args:
            input_dir: Directory containing input CSV files
            out_dir: Output directory for results
            pattern: File pattern to match (default: "*.csv")
            
        Returns:
            Summary dict with counts by decision
        
        Example:
            >>> summary = processor.process_directory("data/")
            >>> print(summary)
            {
                "total": 100,
                "accepted": 85,
                "rejected": 10,
                "quarantined": 5,
                "failed": 0
            }
        """
        input_path = Path(input_dir)
        files = list(input_path.glob(pattern))
        
        if not files:
            return {
                "total": 0,
                "accepted": 0,
                "rejected": 0,
                "quarantined": 0,
                "failed": 0
            }
        
        results = self.process_parallel(files, out_dir)
        
        # Compile summary
        summary = {
            "total": len(results),
            "accepted": sum(1 for r in results if r.get("decision") == "ACCEPT"),
            "rejected": sum(1 for r in results if r.get("decision") == "REJECT"),
            "quarantined": sum(1 for r in results if r.get("decision") == "QUARANTINE"),
            "failed": sum(1 for r in results if r.get("error"))
        }
        
        return summary
    
    def process_parallel(
        self, 
        file_list: List[Path],
        out_dir: str = "outputs"
    ) -> List[dict]:
        """
        Process files in parallel using multiprocessing.
        
        Args:
            file_list: List of file paths
            out_dir: Output directory
            
        Returns:
            List of result dicts
        """
        results = []
        
        # Use ProcessPoolExecutor for CPU-bound pandas operations
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(
                    self._process_single_file, 
                    file_path, 
                    out_dir
                ): file_path
                for file_path in file_list
            }
            
            # Process completed tasks with progress bar
            if self.verbose:
                iterator = tqdm(
                    as_completed(future_to_file), 
                    total=len(file_list),
                    desc="Processing files"
                )
            else:
                iterator = as_completed(future_to_file)
            
            for future in iterator:
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "file": str(file_path),
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })
        
        return results
    
    @staticmethod
    def _process_single_file(file_path: Path, out_dir: str) -> dict:
        """
        Process a single file (static method for multiprocessing).
        
        Args:
            file_path: Path to CSV file
            out_dir: Output directory
            
        Returns:
            Result dict with decision and metadata
        """
        try:
            # Load data
            df = pd.read_csv(file_path)
            
            # Generate copy_id from filename
            copy_id = file_path.stem
            
            # Create pipeline and process
            pipeline = Pipeline(policy_dir=_get_default_policy_dir())
            _, report = pipeline.run(df, out_dir=out_dir, copy_id=copy_id)
            
            return {
                "file": str(file_path),
                "copy_id": copy_id,
                "decision": report["decision"],
                "reason_codes": report["reason_codes"],
                "rows": len(df),
                "error": None
            }
        
        except Exception as e:
            return {
                "file": str(file_path),
                "error": str(e),
                "traceback": traceback.format_exc()
            }
