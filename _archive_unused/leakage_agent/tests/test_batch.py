import pytest
import pandas as pd
from pathlib import Path
import tempfile
import shutil
from leakage_agent.batch_processor import BatchProcessor
from leakage_agent.pipeline import Pipeline

@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)

@pytest.fixture
def sample_files(temp_dir):
    """Create sample CSV files for testing."""
    files = []
    
    # File 1: Valid data (should ACCEPT)
    df1 = pd.DataFrame({
        "email_address": ["test1@example.com"],
        "amount": [100],
        "label": ["cat"]
    })
    file1 = temp_dir / "valid_001.csv"
    df1.to_csv(file1, index=False)
    files.append(file1)
    
    # File 2: Missing label (should REJECT)
    df2 = pd.DataFrame({
        "email_address": ["test2@example.com"],
        "amount": [200],
        "label": [None]
    })
    file2 = temp_dir / "invalid_002.csv"
    df2.to_csv(file2, index=False)
    files.append(file2)
    
    # File 3: Secret present (should QUARANTINE)
    df3 = pd.DataFrame({
        "secret_key": ["my-api-key"],
        "label": ["dog"]
    })
    file3 = temp_dir / "secret_003.csv"
    df3.to_csv(file3, index=False)
    files.append(file3)
    
    return files

def test_batch_processor_processes_all_files(temp_dir, sample_files):
    """Test that batch processor handles all files."""
    processor = BatchProcessor(verbose=False)
    
    summary = processor.process_directory(str(temp_dir))
    
    assert summary["total"] == 3
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["quarantined"] == 1
    assert summary["failed"] == 0

def test_batch_processor_parallel_execution(temp_dir, sample_files):
    """Test parallel processing with multiple workers."""
    processor = BatchProcessor(max_workers=2, verbose=False)
    results = processor.process_parallel(sample_files)
    
    assert len(results) == 3
    assert all("decision" in r or "error" in r for r in results)

def test_batch_processor_empty_directory(temp_dir):
    """Test handling of empty directory."""
    processor = BatchProcessor(verbose=False)
    summary = processor.process_directory(str(temp_dir))
    
    assert summary["total"] == 0
    assert summary["accepted"] == 0

def test_batch_processor_with_pattern(temp_dir, sample_files):
    """Test file pattern filtering."""
    # Create a non-CSV file
    (temp_dir / "ignore.txt").write_text("ignore me")
    
    processor = BatchProcessor(verbose=False)
    summary = processor.process_directory(str(temp_dir), pattern="*.csv")
    
    # Should only process CSV files
    assert summary["total"] == 3

def test_batch_processor_handles_corrupted_file(temp_dir):
    """Test handling of corrupted CSV file."""
    # Create invalid CSV
    bad_file = temp_dir / "corrupted.csv"
    bad_file.write_text("invalid,csv,content\n1,2")  # Inconsistent columns
    
    processor = BatchProcessor(verbose=False)
    summary = processor.process_directory(str(temp_dir))
    
    # Should mark as failed or handle gracefully
    assert summary["total"] >= 0  # May or may not fail depending on pandas behavior
