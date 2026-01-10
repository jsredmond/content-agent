"""Property-based tests for observability and run metrics.

Feature: content-agent
Tests Property 22 from the design document.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from src.engines.observability import (
    RunMetrics,
    create_run_metrics,
    write_run_log,
    log_stage_counts,
    _metrics_to_dict,
)


# Strategies for generating test data
source_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), whitelist_characters=' '),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip())

topic_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters=' -_'),
    min_size=1,
    max_size=30
).filter(lambda x: x.strip())

error_message_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), whitelist_characters=' '),
    min_size=1,
    max_size=200
).filter(lambda x: x.strip())


# Feature: content-agent, Property 22: Metrics Completeness
# Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
class TestMetricsCompleteness:
    """Property tests for metrics completeness."""

    @given(
        source_counts=st.dictionaries(
            keys=source_name_strategy,
            values=st.integers(min_value=0, max_value=1000),
            min_size=0,
            max_size=5
        ),
        normalized_count=st.integers(min_value=0, max_value=1000),
        deduped_count=st.integers(min_value=0, max_value=1000),
        selected_count=st.integers(min_value=0, max_value=100),
        topics=st.lists(topic_strategy, min_size=0, max_size=10),
        avg_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        upload_status=st.sampled_from(["success", "failed", "skipped", "pending"]),
        file_id=st.one_of(st.none(), st.text(min_size=1, max_size=50).filter(lambda x: x.strip())),
        errors=st.lists(error_message_strategy, min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_run_metrics_contains_all_required_fields(
        self,
        source_counts: dict[str, int],
        normalized_count: int,
        deduped_count: int,
        selected_count: int,
        topics: list[str],
        avg_score: float,
        upload_status: str,
        file_id: str | None,
        errors: list[str],
    ):
        """For any pipeline run, RunMetrics SHALL contain all required fields."""
        metrics = create_run_metrics(
            fetched_count_by_source=source_counts,
            normalized_count=normalized_count,
            deduped_count=deduped_count,
            selected_count=selected_count,
            top_topics=topics,
            average_score_overall=avg_score,
            upload_status=upload_status,
            uploaded_file_id=file_id,
            errors=errors,
        )

        # Verify fetched_count_by_source is a dict with counts per source
        assert isinstance(metrics.fetched_count_by_source, dict)
        assert metrics.fetched_count_by_source == source_counts

        # Verify normalized_count, deduped_count, selected_count are integers
        assert isinstance(metrics.normalized_count, int)
        assert metrics.normalized_count == normalized_count

        assert isinstance(metrics.deduped_count, int)
        assert metrics.deduped_count == deduped_count

        assert isinstance(metrics.selected_count, int)
        assert metrics.selected_count == selected_count

        # Verify top_topics is a list
        assert isinstance(metrics.top_topics, list)
        assert metrics.top_topics == topics

        # Verify upload_status is a string
        assert isinstance(metrics.upload_status, str)
        assert metrics.upload_status == upload_status

        # Verify errors is a list
        assert isinstance(metrics.errors, list)
        assert metrics.errors == errors

        # Verify run_timestamp is present
        assert isinstance(metrics.run_timestamp, datetime)

    @given(
        source_counts=st.dictionaries(
            keys=source_name_strategy,
            values=st.integers(min_value=0, max_value=1000),
            min_size=0,
            max_size=5
        ),
        normalized_count=st.integers(min_value=0, max_value=1000),
        deduped_count=st.integers(min_value=0, max_value=1000),
        selected_count=st.integers(min_value=0, max_value=100),
        topics=st.lists(topic_strategy, min_size=0, max_size=10),
        upload_status=st.sampled_from(["success", "failed", "skipped", "pending"]),
        errors=st.lists(error_message_strategy, min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_write_run_log_produces_valid_json(
        self,
        source_counts: dict[str, int],
        normalized_count: int,
        deduped_count: int,
        selected_count: int,
        topics: list[str],
        upload_status: str,
        errors: list[str],
    ):
        """For any RunMetrics, write_run_log SHALL produce valid JSON with all fields."""
        metrics = create_run_metrics(
            fetched_count_by_source=source_counts,
            normalized_count=normalized_count,
            deduped_count=deduped_count,
            selected_count=selected_count,
            top_topics=topics,
            upload_status=upload_status,
            errors=errors,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = write_run_log(metrics, output_dir=tmpdir)

            # Verify file was created
            assert os.path.exists(filepath)

            # Verify filename format: run_log_YYYYMMDD_HHMMSS.json
            filename = os.path.basename(filepath)
            assert filename.startswith("run_log_")
            assert filename.endswith(".json")

            # Verify file contains valid JSON
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Verify all required fields are present in JSON
            assert "fetched_count_by_source" in data
            assert data["fetched_count_by_source"] == source_counts

            assert "normalized_count" in data
            assert data["normalized_count"] == normalized_count

            assert "deduped_count" in data
            assert data["deduped_count"] == deduped_count

            assert "selected_count" in data
            assert data["selected_count"] == selected_count

            assert "top_topics" in data
            assert data["top_topics"] == topics

            assert "upload_status" in data
            assert data["upload_status"] == upload_status

            assert "errors" in data
            assert data["errors"] == errors

            assert "run_timestamp" in data
            # Verify timestamp is ISO format
            datetime.fromisoformat(data["run_timestamp"])

    def test_default_run_metrics_has_all_fields(self):
        """Default RunMetrics SHALL have all required fields with sensible defaults."""
        metrics = RunMetrics()

        # All required fields should be present
        assert hasattr(metrics, 'fetched_count_by_source')
        assert hasattr(metrics, 'normalized_count')
        assert hasattr(metrics, 'deduped_count')
        assert hasattr(metrics, 'selected_count')
        assert hasattr(metrics, 'top_topics')
        assert hasattr(metrics, 'average_score_overall')
        assert hasattr(metrics, 'upload_status')
        assert hasattr(metrics, 'uploaded_file_id')
        assert hasattr(metrics, 'errors')
        assert hasattr(metrics, 'run_timestamp')

        # Verify default types
        assert isinstance(metrics.fetched_count_by_source, dict)
        assert isinstance(metrics.normalized_count, int)
        assert isinstance(metrics.deduped_count, int)
        assert isinstance(metrics.selected_count, int)
        assert isinstance(metrics.top_topics, list)
        assert isinstance(metrics.average_score_overall, float)
        assert isinstance(metrics.upload_status, str)
        assert isinstance(metrics.errors, list)
        assert isinstance(metrics.run_timestamp, datetime)

    def test_create_run_metrics_with_none_uses_defaults(self):
        """create_run_metrics with None values SHALL use empty defaults."""
        metrics = create_run_metrics(
            fetched_count_by_source=None,
            top_topics=None,
            errors=None,
            run_timestamp=None,
        )

        assert metrics.fetched_count_by_source == {}
        assert metrics.top_topics == []
        assert metrics.errors == []
        assert isinstance(metrics.run_timestamp, datetime)

    @given(
        stage=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
        count=st.integers(min_value=0, max_value=10000),
    )
    @settings(max_examples=100)
    def test_log_stage_counts_accepts_any_stage_and_count(self, stage: str, count: int):
        """log_stage_counts SHALL accept any stage name and count without error."""
        # Should not raise any exception
        log_stage_counts(stage, count)

    def test_metrics_to_dict_serializes_all_fields(self):
        """_metrics_to_dict SHALL serialize all fields including datetime."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        metrics = create_run_metrics(
            fetched_count_by_source={"AWS News Blog": 25},
            normalized_count=25,
            deduped_count=20,
            selected_count=10,
            top_topics=["cloud security"],
            average_score_overall=75.5,
            upload_status="success",
            uploaded_file_id="abc123",
            errors=["test error"],
            run_timestamp=timestamp,
        )

        result = _metrics_to_dict(metrics)

        assert result["fetched_count_by_source"] == {"AWS News Blog": 25}
        assert result["normalized_count"] == 25
        assert result["deduped_count"] == 20
        assert result["selected_count"] == 10
        assert result["top_topics"] == ["cloud security"]
        assert result["average_score_overall"] == 75.5
        assert result["upload_status"] == "success"
        assert result["uploaded_file_id"] == "abc123"
        assert result["errors"] == ["test error"]
        assert result["run_timestamp"] == "2024-01-15T10:30:45"
