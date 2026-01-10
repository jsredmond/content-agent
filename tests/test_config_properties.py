"""Property-based tests for configuration management.

Feature: content-agent
Tests Properties 23 and 24 from the design document.
"""

import os
from unittest.mock import patch

import pytest
from hypothesis import given, settings, strategies as st

from src.config.settings import (
    ConfigurationError,
    DEFAULT_KEYWORDS,
    Settings,
    load_settings,
)


# Feature: content-agent, Property 23: Configuration Defaults
# Validates: Requirements 10.3
class TestConfigurationDefaults:
    """Property tests for configuration defaults."""

    def test_default_settings_have_documented_values(self):
        """Verify that Settings uses documented default values."""
        settings_obj = Settings()

        # Verify all documented defaults
        assert settings_obj.google_drive_folder_id == ""
        assert settings_obj.max_articles_per_source == 50
        assert settings_obj.recency_window_days == 30
        assert settings_obj.target_selected == 10
        assert settings_obj.min_score_threshold == 0.0
        assert settings_obj.recency_weight == 0.4
        assert settings_obj.relevance_weight == 0.6
        assert settings_obj.request_delay_seconds == 1.0
        assert settings_obj.max_retries == 3
        assert settings_obj.keywords == DEFAULT_KEYWORDS

    @given(
        folder_id=st.text(min_size=0, max_size=100).filter(lambda x: x.isprintable() or x == "")
    )
    @settings(max_examples=100)
    def test_load_settings_uses_defaults_for_missing_env_vars(self, folder_id: str):
        """For any missing configuration value, Settings SHALL use documented defaults."""
        # Only set GOOGLE_DRIVE_FOLDER_ID, leave others unset
        env_vars = {"GOOGLE_DRIVE_FOLDER_ID": folder_id}

        with patch.dict(os.environ, env_vars, clear=True):
            # Disable dotenv loading by passing a non-existent path
            settings_obj = load_settings(env_path="/nonexistent/.env", validate=False)

            # The folder_id should be from env
            assert settings_obj.google_drive_folder_id == folder_id

            # All other values should be defaults
            assert settings_obj.max_articles_per_source == 50
            assert settings_obj.recency_window_days == 30
            assert settings_obj.target_selected == 10
            assert settings_obj.min_score_threshold == 0.0
            assert settings_obj.recency_weight == 0.4
            assert settings_obj.relevance_weight == 0.6
            assert settings_obj.request_delay_seconds == 1.0
            assert settings_obj.max_retries == 3

    @given(
        max_articles=st.integers(min_value=1, max_value=1000),
        recency_days=st.integers(min_value=1, max_value=365),
        target=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_load_settings_parses_valid_env_vars(
        self, max_articles: int, recency_days: int, target: int
    ):
        """For any valid env var values, load_settings SHALL parse them correctly."""
        env_vars = {
            "GOOGLE_DRIVE_FOLDER_ID": "test_folder",
            "MAX_ARTICLES_PER_SOURCE": str(max_articles),
            "RECENCY_WINDOW_DAYS": str(recency_days),
            "TARGET_SELECTED": str(target),
            "MIN_SCORE_THRESHOLD": "50.0",
            "RECENCY_WEIGHT": "0.3",
            "RELEVANCE_WEIGHT": "0.7",
            "REQUEST_DELAY_SECONDS": "2.0",
            "MAX_RETRIES": "5",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings_obj = load_settings(env_path="/nonexistent/.env", validate=True)

            assert settings_obj.max_articles_per_source == max_articles
            assert settings_obj.recency_window_days == recency_days
            assert settings_obj.target_selected == target
            assert settings_obj.min_score_threshold == 50.0
            assert settings_obj.recency_weight == 0.3
            assert settings_obj.relevance_weight == 0.7

    def test_load_settings_uses_defaults_for_invalid_env_vars(self):
        """For invalid env var values, load_settings SHALL use defaults."""
        env_vars = {
            "GOOGLE_DRIVE_FOLDER_ID": "test_folder",
            "MAX_ARTICLES_PER_SOURCE": "not_a_number",
            "RECENCY_WINDOW_DAYS": "invalid",
            "TARGET_SELECTED": "abc",
            "MIN_SCORE_THRESHOLD": "xyz",
            "RECENCY_WEIGHT": "0.4",
            "RELEVANCE_WEIGHT": "0.6",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings_obj = load_settings(env_path="/nonexistent/.env", validate=True)

            # Invalid values should fall back to defaults
            assert settings_obj.max_articles_per_source == 50
            assert settings_obj.recency_window_days == 30
            assert settings_obj.target_selected == 10
            assert settings_obj.min_score_threshold == 0.0


# Feature: content-agent, Property 24: Configuration Validation
# Validates: Requirements 10.4
class TestConfigurationValidation:
    """Property tests for configuration validation."""

    @given(
        max_articles=st.integers(max_value=0),
    )
    @settings(max_examples=100)
    def test_negative_or_zero_max_articles_raises_error(self, max_articles: int):
        """For any non-positive max_articles_per_source, validation SHALL raise error."""
        settings_obj = Settings(max_articles_per_source=max_articles)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "max_articles_per_source must be at least 1" in str(exc_info.value)

    @given(
        recency_days=st.integers(max_value=0),
    )
    @settings(max_examples=100)
    def test_negative_or_zero_recency_days_raises_error(self, recency_days: int):
        """For any non-positive recency_window_days, validation SHALL raise error."""
        settings_obj = Settings(recency_window_days=recency_days)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "recency_window_days must be at least 1" in str(exc_info.value)

    @given(
        target=st.integers(max_value=0),
    )
    @settings(max_examples=100)
    def test_negative_or_zero_target_raises_error(self, target: int):
        """For any non-positive target_selected, validation SHALL raise error."""
        settings_obj = Settings(target_selected=target)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "target_selected must be at least 1" in str(exc_info.value)

    @given(
        threshold=st.floats().filter(lambda x: x < 0.0 or x > 100.0),
    )
    @settings(max_examples=100)
    def test_invalid_score_threshold_raises_error(self, threshold: float):
        """For any threshold outside [0, 100], validation SHALL raise error."""
        settings_obj = Settings(min_score_threshold=threshold)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "min_score_threshold must be between 0.0 and 100.0" in str(exc_info.value)

    @given(
        recency_weight=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_weights_not_summing_to_one_raises_error(self, recency_weight: float):
        """For any weights not summing to 1.0, validation SHALL raise error."""
        # Set relevance_weight to something that doesn't sum to 1.0 with recency_weight
        bad_relevance_weight = 1.0 - recency_weight + 0.1  # Always off by 0.1

        settings_obj = Settings(
            recency_weight=recency_weight,
            relevance_weight=bad_relevance_weight,
        )
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "must equal 1.0" in str(exc_info.value)

    @given(
        recency_weight=st.floats().filter(lambda x: x < 0.0 or x > 1.0),
    )
    @settings(max_examples=100)
    def test_invalid_recency_weight_raises_error(self, recency_weight: float):
        """For any recency_weight outside [0, 1], validation SHALL raise error."""
        settings_obj = Settings(recency_weight=recency_weight, relevance_weight=0.5)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "recency_weight must be between 0.0 and 1.0" in str(exc_info.value)

    @given(
        relevance_weight=st.floats().filter(lambda x: x < 0.0 or x > 1.0),
    )
    @settings(max_examples=100)
    def test_invalid_relevance_weight_raises_error(self, relevance_weight: float):
        """For any relevance_weight outside [0, 1], validation SHALL raise error."""
        settings_obj = Settings(recency_weight=0.5, relevance_weight=relevance_weight)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "relevance_weight must be between 0.0 and 1.0" in str(exc_info.value)

    @given(
        delay=st.floats(max_value=-0.001),
    )
    @settings(max_examples=100)
    def test_negative_request_delay_raises_error(self, delay: float):
        """For any negative request_delay_seconds, validation SHALL raise error."""
        settings_obj = Settings(request_delay_seconds=delay)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "request_delay_seconds must be non-negative" in str(exc_info.value)

    @given(
        retries=st.integers(max_value=-1),
    )
    @settings(max_examples=100)
    def test_negative_max_retries_raises_error(self, retries: int):
        """For any negative max_retries, validation SHALL raise error."""
        settings_obj = Settings(max_retries=retries)
        with pytest.raises(ConfigurationError) as exc_info:
            settings_obj.validate()
        assert "max_retries must be non-negative" in str(exc_info.value)

    @given(
        recency_weight=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_valid_weights_summing_to_one_passes(self, recency_weight: float):
        """For any valid weights summing to 1.0, validation SHALL pass."""
        relevance_weight = 1.0 - recency_weight

        settings_obj = Settings(
            recency_weight=recency_weight,
            relevance_weight=relevance_weight,
        )
        # Should not raise
        settings_obj.validate()

    def test_load_settings_with_validate_raises_on_invalid(self):
        """load_settings with validate=True SHALL raise on invalid config."""
        env_vars = {
            "GOOGLE_DRIVE_FOLDER_ID": "test",
            "RECENCY_WEIGHT": "0.3",
            "RELEVANCE_WEIGHT": "0.3",  # Sum is 0.6, not 1.0
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError):
                load_settings(env_path="/nonexistent/.env", validate=True)

    def test_load_settings_without_validate_does_not_raise(self):
        """load_settings with validate=False SHALL not raise on invalid config."""
        env_vars = {
            "GOOGLE_DRIVE_FOLDER_ID": "test",
            "RECENCY_WEIGHT": "0.3",
            "RELEVANCE_WEIGHT": "0.3",  # Sum is 0.6, not 1.0
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # Should not raise
            settings_obj = load_settings(env_path="/nonexistent/.env", validate=False)
            assert settings_obj.recency_weight == 0.3
            assert settings_obj.relevance_weight == 0.3
