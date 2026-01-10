"""Observability and run metrics for the content agent pipeline.

This module provides data structures and functions for tracking pipeline
execution metrics, logging stage counts, and writing run logs.

Feature: content-agent
Implements Requirements 9.1, 9.2, 9.3, 9.4, 9.5
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class RunMetrics:
    """Metrics collected during a pipeline run.
    
    Attributes:
        fetched_count_by_source: Count of articles fetched per source
        normalized_count: Count of articles after normalization
        deduped_count: Count of articles after deduplication
        selected_count: Count of articles selected for output
        top_topics: Most common topics among selected articles
        average_score_overall: Average overall score of selected articles
        upload_status: Status of Google Drive upload ("success", "failed", "skipped")
        uploaded_file_id: Google Drive file ID if upload succeeded
        errors: List of error messages encountered during the run
        run_timestamp: Timestamp when the run started
    """
    fetched_count_by_source: dict[str, int] = field(default_factory=dict)
    normalized_count: int = 0
    deduped_count: int = 0
    selected_count: int = 0
    top_topics: list[str] = field(default_factory=list)
    average_score_overall: float = 0.0
    upload_status: str = "pending"
    uploaded_file_id: str | None = None
    errors: list[str] = field(default_factory=list)
    run_timestamp: datetime = field(default_factory=datetime.now)



def create_run_metrics(
    fetched_count_by_source: dict[str, int] | None = None,
    normalized_count: int = 0,
    deduped_count: int = 0,
    selected_count: int = 0,
    top_topics: list[str] | None = None,
    average_score_overall: float = 0.0,
    upload_status: str = "pending",
    uploaded_file_id: str | None = None,
    errors: list[str] | None = None,
    run_timestamp: datetime | None = None,
) -> RunMetrics:
    """Create a RunMetrics instance with aggregated counts from pipeline stages.
    
    This factory function provides a convenient way to create RunMetrics
    with proper defaults for optional fields.
    
    Args:
        fetched_count_by_source: Dict mapping source names to fetch counts
        normalized_count: Number of articles after normalization
        deduped_count: Number of articles after deduplication
        selected_count: Number of articles selected for output
        top_topics: List of most common topics
        average_score_overall: Average overall score of selected articles
        upload_status: Status of upload ("success", "failed", "skipped", "pending")
        uploaded_file_id: Google Drive file ID if upload succeeded
        errors: List of error messages
        run_timestamp: When the run started (defaults to now)
        
    Returns:
        RunMetrics instance with the provided values
        
    Example:
        >>> metrics = create_run_metrics(
        ...     fetched_count_by_source={"AWS News Blog": 25, "Microsoft Purview Blog": 20},
        ...     normalized_count=45,
        ...     deduped_count=40,
        ...     selected_count=10,
        ...     top_topics=["cloud security", "identity"],
        ...     average_score_overall=75.5,
        ...     upload_status="success",
        ...     uploaded_file_id="abc123",
        ... )
        >>> metrics.selected_count
        10
    """
    return RunMetrics(
        fetched_count_by_source=fetched_count_by_source or {},
        normalized_count=normalized_count,
        deduped_count=deduped_count,
        selected_count=selected_count,
        top_topics=top_topics or [],
        average_score_overall=average_score_overall,
        upload_status=upload_status,
        uploaded_file_id=uploaded_file_id,
        errors=errors or [],
        run_timestamp=run_timestamp or datetime.now(),
    )


def write_run_log(metrics: RunMetrics, output_dir: str = "src/output") -> str:
    """Write run metrics to a JSON log file.
    
    Creates a JSON file in the specified output directory with filename format:
    run_log_YYYYMMDD_HHMMSS.json
    
    The file contains all metrics in a human-readable JSON format.
    
    Args:
        metrics: RunMetrics instance to write
        output_dir: Directory path for output file (default: "src/output")
        
    Returns:
        The filepath of the written JSON file
        
    Raises:
        OSError: If the output directory cannot be created or file cannot be written
        
    Example:
        >>> metrics = create_run_metrics(selected_count=10)
        >>> filepath = write_run_log(metrics)
        >>> filepath
        'src/output/run_log_20240116_103045.json'
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filename
    timestamp = metrics.run_timestamp.strftime('%Y%m%d_%H%M%S')
    filename = f"run_log_{timestamp}.json"
    filepath = output_path / filename
    
    # Convert metrics to dict for JSON serialization
    metrics_dict = _metrics_to_dict(metrics)
    
    # Write JSON with pretty formatting
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metrics_dict, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Run log written to {filepath}")
    return str(filepath)


def _metrics_to_dict(metrics: RunMetrics) -> dict[str, Any]:
    """Convert RunMetrics to a JSON-serializable dictionary.
    
    Handles datetime serialization and ensures all fields are present.
    
    Args:
        metrics: RunMetrics instance to convert
        
    Returns:
        Dictionary suitable for JSON serialization
    """
    return {
        "fetched_count_by_source": metrics.fetched_count_by_source,
        "normalized_count": metrics.normalized_count,
        "deduped_count": metrics.deduped_count,
        "selected_count": metrics.selected_count,
        "top_topics": metrics.top_topics,
        "average_score_overall": metrics.average_score_overall,
        "upload_status": metrics.upload_status,
        "uploaded_file_id": metrics.uploaded_file_id,
        "errors": metrics.errors,
        "run_timestamp": metrics.run_timestamp.isoformat(),
    }


def log_stage_counts(stage: str, count: int) -> None:
    """Log the count for a pipeline stage.
    
    Provides consistent logging format for tracking article counts
    as they flow through the pipeline stages.
    
    Args:
        stage: Name of the pipeline stage (e.g., "fetched", "normalized", "deduped")
        count: Number of articles at this stage
        
    Example:
        >>> log_stage_counts("fetched", 45)
        # Logs: "Pipeline stage 'fetched': 45 articles"
        >>> log_stage_counts("selected", 10)
        # Logs: "Pipeline stage 'selected': 10 articles"
    """
    logger.info(f"Pipeline stage '{stage}': {count} articles")
