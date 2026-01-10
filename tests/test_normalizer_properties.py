"""Property-based tests for article normalization.

Feature: content-agent
Tests Properties 4, 5, and 6 from the design document.
"""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from hypothesis import given, settings, strategies as st, assume

from src.engines.article_normalizer import (
    TRACKING_PARAMS,
    normalize_url,
)


# Strategy for generating valid URLs with tracking parameters
def url_with_tracking_params():
    """Generate URLs that may contain tracking parameters."""
    base_domains = st.sampled_from([
        "example.com",
        "aws.amazon.com",
        "techcommunity.microsoft.com",
        "blog.example.org",
    ])
    
    paths = st.sampled_from([
        "/article",
        "/blog/post",
        "/news/2024/01/update",
        "/whats-new/security",
        "",
    ])
    
    # Generate tracking params
    tracking_keys = st.sampled_from(list(TRACKING_PARAMS)[:10])  # Use subset for speed
    tracking_values = st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
        min_size=1,
        max_size=20
    )
    
    # Generate non-tracking params
    non_tracking_keys = st.sampled_from(['id', 'page', 'category', 'lang', 'version'])
    non_tracking_values = st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N')),
        min_size=1,
        max_size=10
    )
    
    @st.composite
    def build_url(draw):
        domain = draw(base_domains)
        path = draw(paths)
        
        # Build query params
        params = []
        
        # Add 0-3 tracking params
        num_tracking = draw(st.integers(min_value=0, max_value=3))
        for _ in range(num_tracking):
            key = draw(tracking_keys)
            value = draw(tracking_values)
            params.append(f"{key}={value}")
        
        # Add 0-2 non-tracking params
        num_non_tracking = draw(st.integers(min_value=0, max_value=2))
        for _ in range(num_non_tracking):
            key = draw(non_tracking_keys)
            value = draw(non_tracking_values)
            params.append(f"{key}={value}")
        
        query = "&".join(params) if params else ""
        
        if query:
            return f"https://{domain}{path}?{query}"
        return f"https://{domain}{path}"
    
    return build_url()


# Feature: content-agent, Property 4: URL Canonicalization
# Validates: Requirements 2.2
class TestURLCanonicalization:
    """Property tests for URL canonicalization."""

    @given(url=url_with_tracking_params())
    @settings(max_examples=100)
    def test_canonical_url_has_no_tracking_params(self, url: str):
        """For any URL containing tracking parameters, the canonical URL SHALL not contain those parameters."""
        canonical = normalize_url(url)
        
        # Parse the canonical URL
        parsed = urlparse(canonical)
        query_params = parse_qs(parsed.query)
        
        # Check that no tracking params remain
        for param_key in query_params.keys():
            assert param_key.lower() not in TRACKING_PARAMS, (
                f"Tracking param '{param_key}' found in canonical URL: {canonical}"
            )
            assert not param_key.lower().startswith('utm_'), (
                f"UTM param '{param_key}' found in canonical URL: {canonical}"
            )

    @given(
        domain=st.sampled_from(["example.com", "aws.amazon.com", "blog.test.org"]),
        path=st.sampled_from(["/article", "/blog/post", "/news", ""]),
        tracking_param=st.sampled_from(list(TRACKING_PARAMS)[:15]),
        tracking_value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=1,
            max_size=10
        ),
    )
    @settings(max_examples=100)
    def test_specific_tracking_params_removed(
        self, domain: str, path: str, tracking_param: str, tracking_value: str
    ):
        """For any specific tracking parameter, it SHALL be removed from the URL."""
        url = f"https://{domain}{path}?{tracking_param}={tracking_value}"
        canonical = normalize_url(url)
        
        # The tracking param should not be in the canonical URL
        assert tracking_param not in canonical or f"{tracking_param}=" not in canonical

    @given(
        domain=st.sampled_from(["example.com", "aws.amazon.com"]),
        path=st.sampled_from(["/article", "/blog"]),
        non_tracking_key=st.sampled_from(['id', 'page', 'category', 'lang']),
        non_tracking_value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=1,
            max_size=10
        ),
    )
    @settings(max_examples=100)
    def test_non_tracking_params_preserved(
        self, domain: str, path: str, non_tracking_key: str, non_tracking_value: str
    ):
        """For any non-tracking parameter, it SHALL be preserved in the canonical URL."""
        url = f"https://{domain}{path}?{non_tracking_key}={non_tracking_value}"
        canonical = normalize_url(url)
        
        # Parse and check the param is preserved
        parsed = urlparse(canonical)
        query_params = parse_qs(parsed.query)
        
        assert non_tracking_key in query_params, (
            f"Non-tracking param '{non_tracking_key}' was removed from URL"
        )
        assert non_tracking_value in query_params[non_tracking_key], (
            f"Non-tracking param value '{non_tracking_value}' was changed"
        )

    def test_empty_url_returns_empty(self):
        """Empty URL should return empty string."""
        assert normalize_url("") == ""

    def test_url_without_params_unchanged(self):
        """URL without query params should remain essentially unchanged."""
        url = "https://example.com/article"
        canonical = normalize_url(url)
        assert canonical == url

    def test_utm_variants_removed(self):
        """All utm_ prefixed params should be removed."""
        url = "https://example.com/article?utm_custom=test&utm_foo=bar&id=123"
        canonical = normalize_url(url)
        
        assert "utm_custom" not in canonical
        assert "utm_foo" not in canonical
        assert "id=123" in canonical



# Feature: content-agent, Property 5: Date Parsing Round-Trip
# Validates: Requirements 2.3
class TestDateParsingRoundTrip:
    """Property tests for date parsing round-trip consistency."""

    @given(
        dt=st.datetimes(
            min_value=datetime(1970, 1, 1),
            max_value=datetime(2100, 12, 31),
        )
    )
    @settings(max_examples=100)
    def test_iso_format_round_trip(self, dt: datetime):
        """For any datetime, formatting to ISO and parsing back SHALL produce equivalent datetime."""
        from src.engines.article_normalizer import parse_date
        
        # Format to ISO string
        iso_str = dt.isoformat()
        
        # Parse back
        parsed = parse_date(iso_str)
        
        assert parsed is not None, f"Failed to parse ISO date: {iso_str}"
        
        # Compare year, month, day, hour, minute, second (ignore microseconds for simplicity)
        assert parsed.year == dt.year
        assert parsed.month == dt.month
        assert parsed.day == dt.day
        assert parsed.hour == dt.hour
        assert parsed.minute == dt.minute
        assert parsed.second == dt.second

    @given(
        dt=st.datetimes(
            min_value=datetime(1970, 1, 1),
            max_value=datetime(2100, 12, 31),
        )
    )
    @settings(max_examples=100)
    def test_standard_format_round_trip(self, dt: datetime):
        """For any datetime, formatting to standard string and parsing back SHALL produce equivalent datetime."""
        from src.engines.article_normalizer import parse_date
        
        # Format to standard string (YYYY-MM-DD HH:MM:SS)
        std_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Parse back
        parsed = parse_date(std_str)
        
        assert parsed is not None, f"Failed to parse standard date: {std_str}"
        
        # Compare components
        assert parsed.year == dt.year
        assert parsed.month == dt.month
        assert parsed.day == dt.day
        assert parsed.hour == dt.hour
        assert parsed.minute == dt.minute
        assert parsed.second == dt.second

    def test_none_input_returns_none(self):
        """None input should return None."""
        from src.engines.article_normalizer import parse_date
        
        assert parse_date(None) is None

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        from src.engines.article_normalizer import parse_date
        
        assert parse_date("") is None
        assert parse_date("   ") is None

    def test_invalid_date_returns_none(self):
        """Invalid date string should return None."""
        from src.engines.article_normalizer import parse_date
        
        assert parse_date("not a date") is None
        assert parse_date("abc123") is None

    def test_common_date_formats(self):
        """Common date formats should parse correctly."""
        from src.engines.article_normalizer import parse_date
        
        # ISO format
        result = parse_date("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        
        # Human readable
        result = parse_date("January 15, 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        
        # RFC 2822 (common in RSS feeds)
        result = parse_date("Mon, 15 Jan 2024 10:30:00 GMT")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15



# Feature: content-agent, Property 6: Text Normalization
# Validates: Requirements 2.5
class TestTextNormalization:
    """Property tests for text normalization."""

    @given(
        text=st.text(min_size=0, max_size=200)
    )
    @settings(max_examples=100)
    def test_normalized_text_has_no_leading_trailing_whitespace(self, text: str):
        """For any string, normalizing it SHALL produce a string without leading or trailing whitespace."""
        from src.engines.article_normalizer import normalize_text
        
        result = normalize_text(text)
        
        if result is not None and len(result) > 0:
            assert result == result.strip(), (
                f"Normalized text has leading/trailing whitespace: '{result}'"
            )

    @given(
        core_text=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P')),
            min_size=1,
            max_size=50
        ),
        leading_ws=st.text(
            alphabet=st.sampled_from([' ', '\t', '\n', '\r']),
            min_size=0,
            max_size=5
        ),
        trailing_ws=st.text(
            alphabet=st.sampled_from([' ', '\t', '\n', '\r']),
            min_size=0,
            max_size=5
        ),
    )
    @settings(max_examples=100)
    def test_whitespace_stripped(self, core_text: str, leading_ws: str, trailing_ws: str):
        """For any text with leading/trailing whitespace, normalization SHALL strip it."""
        from src.engines.article_normalizer import normalize_text
        
        text_with_ws = leading_ws + core_text + trailing_ws
        result = normalize_text(text_with_ws)
        
        assert result is not None
        assert not result.startswith((' ', '\t', '\n', '\r'))
        assert not result.endswith((' ', '\t', '\n', '\r'))

    @given(
        words=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=('L', 'N')),
                min_size=1,
                max_size=10
            ),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_multiple_whitespace_collapsed(self, words: list[str]):
        """For any text with multiple consecutive whitespace, normalization SHALL collapse to single space."""
        from src.engines.article_normalizer import normalize_text
        
        # Join words with multiple spaces
        text_with_multiple_spaces = "   ".join(words)
        result = normalize_text(text_with_multiple_spaces)
        
        assert result is not None
        # Check no consecutive spaces remain
        assert "  " not in result, f"Multiple spaces found in: '{result}'"

    def test_none_input_returns_none(self):
        """None input should return None."""
        from src.engines.article_normalizer import normalize_text
        
        assert normalize_text(None) is None

    def test_empty_string_returns_empty(self):
        """Empty string should return empty string."""
        from src.engines.article_normalizer import normalize_text
        
        assert normalize_text("") == ""

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only string should return empty string."""
        from src.engines.article_normalizer import normalize_text
        
        assert normalize_text("   ") == ""
        assert normalize_text("\t\n\r") == ""

    def test_unicode_normalization(self):
        """Unicode should be normalized to NFC form."""
        from src.engines.article_normalizer import normalize_text
        import unicodedata
        
        # NFD form of é (e + combining acute accent)
        nfd_text = "cafe\u0301"  # café in NFD
        result = normalize_text(nfd_text)
        
        assert result is not None
        # Result should be in NFC form
        assert unicodedata.is_normalized('NFC', result)
