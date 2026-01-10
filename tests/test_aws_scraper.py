"""Unit tests for AWS News Blog scraper parsing.

Feature: content-agent
Tests Requirements 1.3 - AWS News Blog article extraction.
"""

from unittest.mock import patch, MagicMock
import pytest

from src.config.settings import Settings
from src.engines.aws_news_blog_scraper import AWSNewsBlogScraper
from src.engines.article_normalizer import RawArticle


# Sample RSS feed content for testing
SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AWS News Blog</title>
    <link>https://aws.amazon.com/blogs/aws/</link>
    <description>AWS News Blog</description>
    <item>
      <title>New Amazon S3 Feature Announcement</title>
      <link>https://aws.amazon.com/blogs/aws/new-s3-feature</link>
      <pubDate>Mon, 15 Jan 2024 10:30:00 GMT</pubDate>
      <author>Jane Doe</author>
      <description><![CDATA[<p>Today we are announcing a new feature for Amazon S3 that improves security.</p>]]></description>
    </item>
    <item>
      <title>AWS Lambda Updates for 2024</title>
      <link>https://aws.amazon.com/blogs/aws/lambda-updates-2024</link>
      <pubDate>Sun, 14 Jan 2024 09:00:00 GMT</pubDate>
      <author>John Smith</author>
      <description><![CDATA[<p>We are excited to share the latest updates to AWS Lambda.</p>]]></description>
    </item>
    <item>
      <title>Security Best Practices Guide</title>
      <link>https://aws.amazon.com/blogs/aws/security-best-practices</link>
      <pubDate>Sat, 13 Jan 2024 14:00:00 GMT</pubDate>
      <description><![CDATA[<p>Learn about security best practices for your AWS workloads.</p>]]></description>
    </item>
  </channel>
</rss>
"""

# Sample HTML content for testing fallback
SAMPLE_HTML_PAGE = """<!DOCTYPE html>
<html>
<head><title>AWS News Blog</title></head>
<body>
  <article class="blog-post">
    <h2><a href="/blogs/aws/new-ec2-instance">New EC2 Instance Type</a></h2>
    <time datetime="2024-01-15">January 15, 2024</time>
    <span class="author">Alice Johnson</span>
    <p>Introducing a new EC2 instance type optimized for machine learning workloads.</p>
  </article>
  <article class="blog-post">
    <h2><a href="https://aws.amazon.com/blogs/aws/cloudwatch-update">CloudWatch Monitoring Update</a></h2>
    <time datetime="2024-01-14">January 14, 2024</time>
    <span class="author">Bob Williams</span>
    <p>Enhanced monitoring capabilities now available in CloudWatch.</p>
  </article>
</body>
</html>
"""


class TestAWSScraperRSSParsing:
    """Unit tests for AWS scraper RSS feed parsing."""

    def test_parse_rss_extracts_title(self):
        """RSS parsing SHALL extract article title."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert len(articles) == 3
        assert articles[0].title == "New Amazon S3 Feature Announcement"
        assert articles[1].title == "AWS Lambda Updates for 2024"
        assert articles[2].title == "Security Best Practices Guide"

    def test_parse_rss_extracts_link(self):
        """RSS parsing SHALL extract article link."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert articles[0].url == "https://aws.amazon.com/blogs/aws/new-s3-feature"
        assert articles[1].url == "https://aws.amazon.com/blogs/aws/lambda-updates-2024"

    def test_parse_rss_extracts_published_date(self):
        """RSS parsing SHALL extract published date."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert articles[0].published_date == "Mon, 15 Jan 2024 10:30:00 GMT"
        assert articles[1].published_date == "Sun, 14 Jan 2024 09:00:00 GMT"

    def test_parse_rss_extracts_author(self):
        """RSS parsing SHALL extract author when available."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        assert articles[0].author == "Jane Doe"
        assert articles[1].author == "John Smith"

    def test_parse_rss_extracts_teaser(self):
        """RSS parsing SHALL extract teaser text from description."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        # HTML should be stripped from teaser
        assert "Today we are announcing" in articles[0].teaser
        assert "<p>" not in articles[0].teaser

    def test_parse_rss_sets_source_name(self):
        """RSS parsing SHALL set source to 'AWS News Blog'."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        for article in articles:
            assert article.source == "AWS News Blog"

    def test_parse_rss_respects_limit(self):
        """RSS parsing SHALL respect the limit parameter."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(2)
        
        assert len(articles) == 2

    def test_parse_rss_returns_raw_articles(self):
        """RSS parsing SHALL return RawArticle instances."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_RSS_FEED):
            articles = scraper._fetch_rss(10)
        
        for article in articles:
            assert isinstance(article, RawArticle)


class TestAWSScraperHTMLParsing:
    """Unit tests for AWS scraper HTML fallback parsing."""

    def test_parse_html_extracts_title(self):
        """HTML parsing SHALL extract article title."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert len(articles) == 2
        assert articles[0].title == "New EC2 Instance Type"
        assert articles[1].title == "CloudWatch Monitoring Update"

    def test_parse_html_extracts_link(self):
        """HTML parsing SHALL extract article link."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        # Relative URL should be made absolute
        assert articles[0].url == "https://aws.amazon.com/blogs/aws/new-ec2-instance"
        # Absolute URL should be preserved
        assert articles[1].url == "https://aws.amazon.com/blogs/aws/cloudwatch-update"

    def test_parse_html_extracts_date(self):
        """HTML parsing SHALL extract published date."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert articles[0].published_date == "2024-01-15"

    def test_parse_html_extracts_author(self):
        """HTML parsing SHALL extract author when available."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert articles[0].author == "Alice Johnson"
        assert articles[1].author == "Bob Williams"

    def test_parse_html_extracts_teaser(self):
        """HTML parsing SHALL extract teaser text."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        assert "Introducing a new EC2 instance type" in articles[0].teaser

    def test_parse_html_sets_source_name(self):
        """HTML parsing SHALL set source to 'AWS News Blog'."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_url', return_value=SAMPLE_HTML_PAGE):
            articles = scraper._fetch_html(10)
        
        for article in articles:
            assert article.source == "AWS News Blog"


class TestAWSScraperFetchBehavior:
    """Unit tests for AWS scraper fetch behavior."""

    def test_fetch_prefers_rss(self):
        """fetch SHALL prefer RSS over HTML when RSS succeeds."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_rss', return_value=[
            RawArticle(source="AWS News Blog", title="RSS Article", url="https://example.com/rss")
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
        scraper = AWSNewsBlogScraper(settings)
        
        with patch.object(scraper, '_fetch_rss', side_effect=Exception("RSS failed")):
            with patch.object(scraper, '_fetch_html', return_value=[
                RawArticle(source="AWS News Blog", title="HTML Article", url="https://example.com/html")
            ]) as mock_html:
                articles = scraper.fetch(10)
        
        mock_html.assert_called_once_with(10)
        assert len(articles) == 1
        assert articles[0].title == "HTML Article"

    def test_fetch_respects_limit(self):
        """fetch SHALL respect the limit parameter."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        many_articles = [
            RawArticle(source="AWS News Blog", title=f"Article {i}", url=f"https://example.com/{i}")
            for i in range(20)
        ]
        
        with patch.object(scraper, '_fetch_rss', return_value=many_articles):
            articles = scraper.fetch(5)
        
        assert len(articles) == 5

    def test_source_name_property(self):
        """source_name property SHALL return 'AWS News Blog'."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        assert scraper.source_name == "AWS News Blog"


class TestAWSScraperEdgeCases:
    """Unit tests for AWS scraper edge cases."""

    def test_empty_rss_feed(self):
        """Scraper SHALL handle empty RSS feed."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
        empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>AWS News Blog</title>
          </channel>
        </rss>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=empty_rss):
            articles = scraper._fetch_rss(10)
        
        assert articles == []

    def test_rss_entry_missing_title_skipped(self):
        """RSS entries without title SHALL be skipped."""
        settings = Settings()
        scraper = AWSNewsBlogScraper(settings)
        
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
        scraper = AWSNewsBlogScraper(settings)
        
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
        scraper = AWSNewsBlogScraper(settings)
        
        empty_html = """<!DOCTYPE html>
        <html><body><p>No articles here</p></body></html>
        """
        
        with patch.object(scraper, '_fetch_url', return_value=empty_html):
            articles = scraper._fetch_html(10)
        
        assert articles == []
