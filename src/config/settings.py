"""Configuration settings for the Content Agent pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv


# Default keyword sets for relevance scoring themes
DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "cloud_security": [
        "cloud security",
        "security posture",
        "threat detection",
        "vulnerability",
        "security monitoring",
        "zero trust",
        "encryption",
        "security best practices",
    ],
    "identity_and_access": [
        "identity",
        "access management",
        "IAM",
        "authentication",
        "authorization",
        "SSO",
        "single sign-on",
        "MFA",
        "multi-factor",
        "privileged access",
        "role-based access",
        "RBAC",
    ],
    "governance_and_compliance": [
        "governance",
        "compliance",
        "regulatory",
        "audit",
        "policy",
        "GDPR",
        "HIPAA",
        "SOC 2",
        "PCI DSS",
        "FedRAMP",
        "risk management",
    ],
    "data_protection": [
        "data protection",
        "data security",
        "data governance",
        "DLP",
        "data loss prevention",
        "data classification",
        "sensitive data",
        "PII",
        "encryption at rest",
        "encryption in transit",
    ],
    "auditing_and_retention": [
        "auditing",
        "audit log",
        "retention",
        "data retention",
        "logging",
        "monitoring",
        "trail",
        "forensics",
    ],
    "devsecops": [
        "DevSecOps",
        "automation",
        "policy-as-code",
        "infrastructure as code",
        "IaC",
        "CI/CD security",
        "shift left",
        "security automation",
        "SAST",
        "DAST",
    ],
}


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


@dataclass
class Settings:
    """Configuration settings for the Content Agent pipeline.

    Attributes:
        google_drive_folder_id: Google Drive folder ID for uploads
        max_articles_per_source: Maximum articles to fetch per source
        recency_window_days: Number of days for recency scoring window
        target_selected: Number of top articles to select
        min_score_threshold: Minimum overall score for selection
        recency_weight: Weight for recency in overall score
        relevance_weight: Weight for relevance in overall score
        request_delay_seconds: Delay between HTTP requests
        max_retries: Maximum retry attempts for failed requests
        keywords: Dictionary mapping themes to keyword lists
    """

    google_drive_folder_id: str = ""
    max_articles_per_source: int = 50
    recency_window_days: int = 30
    target_selected: int = 10
    min_score_threshold: float = 0.0
    recency_weight: float = 0.4
    relevance_weight: float = 0.6
    request_delay_seconds: float = 1.0
    max_retries: int = 3
    keywords: dict[str, list[str]] = field(default_factory=lambda: DEFAULT_KEYWORDS.copy())

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ConfigurationError: If any configuration value is invalid.
        """
        errors: list[str] = []

        if self.max_articles_per_source < 1:
            errors.append("max_articles_per_source must be at least 1")

        if self.recency_window_days < 1:
            errors.append("recency_window_days must be at least 1")

        if self.target_selected < 1:
            errors.append("target_selected must be at least 1")

        if self.min_score_threshold < 0.0 or self.min_score_threshold > 100.0:
            errors.append("min_score_threshold must be between 0.0 and 100.0")

        if self.recency_weight < 0.0 or self.recency_weight > 1.0:
            errors.append("recency_weight must be between 0.0 and 1.0")

        if self.relevance_weight < 0.0 or self.relevance_weight > 1.0:
            errors.append("relevance_weight must be between 0.0 and 1.0")

        # Check that weights sum to 1.0 (with small tolerance for floating point)
        weight_sum = self.recency_weight + self.relevance_weight
        if abs(weight_sum - 1.0) > 0.001:
            errors.append(
                f"recency_weight + relevance_weight must equal 1.0, got {weight_sum}"
            )

        if self.request_delay_seconds < 0.0:
            errors.append("request_delay_seconds must be non-negative")

        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")

        if errors:
            raise ConfigurationError("; ".join(errors))


def _parse_float(value: str | None, default: float) -> float:
    """Parse a string to float, returning default if None or invalid."""
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_int(value: str | None, default: int) -> int:
    """Parse a string to int, returning default if None or invalid."""
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_settings(env_path: str | Path | None = None, validate: bool = True) -> Settings:
    """Load settings from environment variables and .env file.

    Args:
        env_path: Optional path to .env file. If None, searches for .env
                  in current directory and parent directories.
        validate: If True, validate settings after loading.

    Returns:
        Settings instance with loaded configuration.

    Raises:
        ConfigurationError: If validate=True and configuration is invalid.
    """
    # Load .env file if it exists
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    settings = Settings(
        google_drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
        max_articles_per_source=_parse_int(
            os.getenv("MAX_ARTICLES_PER_SOURCE"), 50
        ),
        recency_window_days=_parse_int(
            os.getenv("RECENCY_WINDOW_DAYS"), 30
        ),
        target_selected=_parse_int(
            os.getenv("TARGET_SELECTED"), 10
        ),
        min_score_threshold=_parse_float(
            os.getenv("MIN_SCORE_THRESHOLD"), 0.0
        ),
        recency_weight=_parse_float(
            os.getenv("RECENCY_WEIGHT"), 0.4
        ),
        relevance_weight=_parse_float(
            os.getenv("RELEVANCE_WEIGHT"), 0.6
        ),
        request_delay_seconds=_parse_float(
            os.getenv("REQUEST_DELAY_SECONDS"), 1.0
        ),
        max_retries=_parse_int(
            os.getenv("MAX_RETRIES"), 3
        ),
        keywords=DEFAULT_KEYWORDS.copy(),
    )

    if validate:
        settings.validate()

    return settings
