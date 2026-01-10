"""Unit tests for Microsoft Purview Blog scraper parsing.

Feature: content-agent
Tests Requirements 1.4 - Microsoft Purview Blog article extraction.
"""

from unittest.mock import patch, MagicMock
import pytest

from src.config.settings import Settings
from src.engines.purview_blog_scraper import PurviewBlogScraper
from src.engines.article_normalizer import RawArticle


# Sample RSS feed content for testing
SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Microsoft Purview Blog</title>
    <link>https://techcommunity.microsoft.com/category/microsoftpurview/blog/microsoftpurviewblog</link>
    <description>Microsoft Purview Blog</description>
    <item>
      <title>New Data Loss Prevention Features in Purview</title>
      <link>https://techcommunity.microsoft.com/blog/microsoftpurviewblog/new-dlp-features</link>
      <pubDate>Mon, 15 Jan 2024 10:30:00 GMT</pubDate>
      <dc:creator>Sarah Chen</dc:creator>
      <description><![CDATA[<p>Announcing new DLP capabilities to help protect your sensitive data.</p>]]></description>
    </item>
    <item>
      <title>Compliance Manager Updates for 2024</title>
      <link>https://techcommunity.microsoft.com/blog/microsoftpurviewblog/compliance-manager-2024</link>
      <pubDate>Sun, 14 Jan 2024 09:00:00 GMT</pubDate>
      <author>Mike Johnson</author>
      <description><![CDATA[<p>Learn about the latest updates to Compliance Manager.</p>]]></description>
    </item>
    <item>
      <title>Information Protection Best Practices</title>
      <link>https://techcommunity.microsoft.com/blog/microsoftpurviewblog/info-protection-best-practices</link>
      <pubDate>Sat, 13 Jan 2024 14:00:00 GMT</pubDate>
      <description><![CDATA[<p>Best practices for implementing information protection policies.</p>]]></description>
    </item>
  </channel>
</rss>
"""

# Sample HTML content for testing fallback
SAMPLE_HTML_PAGE = """<!DOCTYPE html>
<html>
<head><title>Microsoft Purview Blog</title></head>
<body>
  <article class="blog-post">
    <h2><a href="/blog/microsoftpurviewblog/data-governance-update">Data Governance Update</a></h2>
    <time datetime="2024-01-15">January 15, 2024</time>
    <span class="author">Emily Davis</span>
    <p>New data governance features now available in Microsoft Purview.</p>
  </article>
  <article class="blog-post">
    <h2><a href="https://techcommunity.microsoft.com/blog/microsoftpurviewblog/audit-log-improvements">Audit Log Improvements</a></h2>
    <time datetime="2024-01-14">January 14, 2024</time>
    <span class="author">David Wilson</span>
    <p>Enhanced audit logging capabilities for better compliance tracking.</p>
  </article>
</body>
</html>
"""


class TestPurviewScraperRSSParsing:
    """Unit tests for Purview scraper RSS feed parsing."""

    def test_parse_rss_extracts_title(self):
        """RSS parsing SHALL extract article title."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert len(articles) == 3
        assert articles[0].title == "New Data Loss Prevention Features in Purview"
        assert articles[1].title == "Compliance Manager Updates for 2024"
        assert articles[2].title == "Information Protection Best Practices"

    def test_parse_rss_extracts_link(self):
        """RSS parsing SHALL extract article link."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert articles[0].url == "https://techcommunity.microsoft.com/blog/microsoftpurviewblog/new-dlp-features"
        assert articles[1].url == "https://techcommunity.microsoft.com/blog/microsoftpurviewblog/compliance-manager-2024"

    def test_parse_rss_extracts_published_date(self):
        """RSS parsing SHALL extract published date."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert articles[0].published_date == "Mon, 15 Jan 2024 10:30:00 GMT"
        assert articles[1].published_date == "Sun, 14 Jan 2024 09:00:00 GMT"

    def test_parse_rss_extracts_author_from_dc_creator(self):
        """RSS parsing SHALL extract author from dc:creator element."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        # First article uses dc:creator
        assert articles[0].author == "Sarah Chen"

    def test_parse_rss_extracts_author_from_author_element(self):
        """RSS parsing SHALL extract author from author element."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        # Second article uses author element
        assert articles[1].author == "Mike Johnson"

    def test_parse_rss_extracts_teaser(self):
        """RSS parsing SHALL extract teaser text from description."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        # HTML should be stripped from teaser
        assert "Announcing new DLP capabilities" in articles[0].teaser
        assert "<p>" not in articles[0].teaser

    def test_parse_rss_sets_source_name(self):
        """RSS parsing SHALL set source to 'Microsoft Purview Blog'."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        for article in articles:
            assert article.source == "Microsoft Purview Blog"

    def test_parse_rss_respects_limit(self):
        """RSS parsing SHALL respect the limit parameter."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(2)
        
        assert len(articles) == 2

    def test_parse_rss_returns_raw_articles(self):
        """RSS parsing SHALL return RawArticle instances."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        for article in articles:
            assert isinstance(article, RawArticle)


class TestPurviewScraperHTMLParsing:
    """Unit tests for Purview scraper HTML fallback parsing."""

    def test_parse_html_extracts_title(self):
        """HTML parsing SHALL extract article title."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert len(articles) == 2
        assert articles[0].title == "Data Governance Update"
        assert articles[1].title == "Audit Log Improvements"

    def test_parse_html_extracts_link(self):
        """HTML parsing SHALL extract article link."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        # Relative URL should be made absolute
        assert articles[0].url == "https://techcommunity.microsoft.com/blog/microsoftpurviewblog/data-governance-update"
        # Absolute URL should be preserved
        assert articles[1].url == "https://techcommunity.microsoft.com/blog/microsoftpurviewblog/audit-log-improvements"

    def test_parse_html_extracts_date(self):
        """HTML parsing SHALL extract published date."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert articles[0].published_date == "2024-01-15"

    def test_parse_html_extracts_author(self):
        """HTML parsing SHALL extract author when available."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert articles[0].author == "Emily Davis"
        assert articles[1].author == "David Wilson"

    def test_parse_html_extracts_teaser(self):
        """HTML parsing SHALL extract teaser text."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert "New data governance features" in articles[0].teaser

    def test_parse_html_sets_source_name(self):
        """HTML parsing SHALL set source to 'Microsoft Purview Blog'."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        for article in articles:
            assert article.source == "Microsoft Purview Blog"


class TestPurviewScraperFetchBehavior:
    """Unit tests for Purview scraper fetch behavior."""

    def test_fetch_prefers_rss(self):
        """fetch SHALL prefer RSS over HTML when RSS succeeds."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_rss', return_value=[
            RawArticle(source="Microsoft Purview Blog", title="RSS Article", url="https://example.com/rss")
        ]) as mock_rss:
            with patch.object(scraper, '_fetch_html') as mock_html:
                articles = scraper.fetch(10)
        
        mock_rss.assert_called_once_with(10)
        mock_html.assert_not_called()
        assert len(articles) == 1
        assert articles[0].title == "RSS Article"

    def test_fetch_falls_back_to_html_on_rss_failure(self):
        """fetch SHALL fall back to HTML when RSS fails."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_rss', side_effect=Exception("RSS failed")):
            with patch.object(scraper, '_fetch_html', return_value=[
                RawArticle(source="Microsoft Purview Blog", title="HTML Article", url="https://example.com/html")
            ]) as mock_html:
                articles = scraper.fetch(10)
        
        mock_html.assert_called_once_with(10)
        assert len(articles) == 1
        assert articles[0].title == "HTML Article"

    def test_fetch_respects_limit(self):
        """fetch SHALL respect the limit parameter."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        many_articles = [
            RawArticle(source="Microsoft Purview Blog", title=f"Article {i}", url=f"https://example.com/{i}")
            for i in range(20)
        ]
        
        with patch.object(scraper, '_fetch_rss', return_value=many_articles):
            articles = scraper.fetch(5)
        
        assert len(articles) == 5

    def test_source_name_property(self):
        """source_name property SHALL return 'Microsoft Purview Blog'."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        assert scraper.source_name == "Microsoft Purview Blog"


class TestPurviewScraperEdgeCases:
    """Unit tests for Purview scraper edge cases."""

    def test_empty_rss_feed(self):
        """Scraper SHALL handle empty RSS feed."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Microsoft Purview Blog</title>
          </channel>
        </rss>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=empty_rss):
            articles = scraper._fetch_rss(10)
        
        assert articles == []

    def test_rss_entry_missing_title_skipped(self):
        """RSS entries without title SHALL be skipped."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        rss_with_missing_title = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <link>https://example.com/no-title</link>
            </item>
            <item>
              <title>Valid Article</title>
              <link>https://example.com/valid</link>
            </item>
          </channel>
        </rss>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=rss_with_missing_title):
            articles = scraper._fetch_rss(10)
        
        assert len(articles) == 1
        assert articles[0].title == "Valid Article"

    def test_rss_entry_missing_link_skipped(self):
        """RSS entries without link SHALL be skipped."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        rss_with_missing_link = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>No Link Article</title>
            </item>
            <item>
              <title>Valid Article</title>
              <link>https://example.com/valid</link>
            </item>
          </channel>
        </rss>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=rss_with_missing_link):
            articles = scraper._fetch_rss(10)
        
        assert len(articles) == 1
        assert articles[0].title == "Valid Article"

    def test_html_with_no_articles(self):
        """Scraper SHALL handle HTML page with no articles."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        empty_html = """<!DOCTYPE html>
        <html><body><p>No articles here</p></body></html>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=empty_html):
            articles = scraper._fetch_html(10)
        
        assert articles == []

    def test_rss_with_no_author(self):
        """RSS entries without author SHALL have None author."""
        settings = Settings()
        scraper = PurviewBlogScraper(settings)
        
        rss_no_author = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Article Without Author</title>
              <link>https://example.com/no-author</link>
              <pubDate>Mon, 15 Jan 2024 10:30:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=rss_no_author):
            articles = scraper._fetch_rss(10)
        
        assert len(articles) == 1
        assert articles[0].author is None
