"""AWS News Blog scraper for fetching articles via RSS or HTML fallback."""

import logging
import time
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config.settings import Settings
from src.engines.article_normalizer import RawArticle


logger = logging.getLogger(__name__)


# AWS News Blog RSS feed URL
AWS_RSS_URL = "https://aws.amazon.com/blogs/aws/feed/"

# AWS News Blog HTML fallback URL
AWS_BLOG_URL = "https://aws.amazon.com/blogs/aws/"


class AWSNewsBlogScraper:
    """Scraper for AWS News Blog articles.
    
    Prefers RSS feed for fetching articles, falls back to HTML scraping
    if RSS is unavailable. Implements retry with exponential backoff
    for transient failures.
    
    Attributes:
        source_name: Identifier for this source ("AWS News Blog")
        settings: Configuration settings for the scraper
    """
    
    def __init__(self, settings: Settings):
        """Initialize the AWS News Blog scraper.
        
        Args:
            settings: Configuration settings including request delays and retries
        """
        self.settings = settings
        self._source_name = "AWS News Blog"
    
    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return self._source_name

    def fetch(self, limit: int) -> list[RawArticle]:
        """Fetch articles from AWS News Blog up to the specified limit.
        
        Attempts RSS feed first, falls back to HTML scraping if RSS fails.
        Respects request pacing with configurable delays.
        
        Args:
            limit: Maximum number of articles to fetch
            
        Returns:
            List of RawArticle objects, at most `limit` items
        """
        try:
            articles = self._fetch_rss(limit)
            if articles:
                logger.info(f"Fetched {len(articles)} articles from AWS News Blog RSS")
                return articles[:limit]
        except Exception as e:
            logger.warning(f"RSS fetch failed for AWS News Blog, trying HTML: {e}")
        
        # Fallback to HTML scraping
        try:
            articles = self._fetch_html(limit)
            logger.info(f"Fetched {len(articles)} articles from AWS News Blog HTML")
            return articles[:limit]
        except Exception as e:
            logger.error(f"HTML fetch also failed for AWS News Blog: {e}")
            raise
    
    def _fetch_rss(self, limit: int) -> list[RawArticle]:
        """Fetch articles from RSS feed.
        
        Args:
            limit: Maximum number of articles to fetch
            
        Returns:
            List of RawArticle objects parsed from RSS
        """
        content = self._fetch_url(AWS_RSS_URL)
        feed = feedparser.parse(content)
        
        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed: {feed.bozo_exception}")
        
        articles: list[RawArticle] = []
        for entry in feed.entries[:limit]:
            article = self._parse_rss_entry(entry)
            if article:
                articles.append(article)
        
        return articles
    
    def _parse_rss_entry(self, entry: Any) -> RawArticle | None:
        """Parse a single RSS entry into a RawArticle.
        
        Args:
            entry: feedparser entry object
            
        Returns:
            RawArticle or None if parsing fails
        """
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            
            if not title or not link:
                return None
            
            # Get published date
            published = entry.get("published") or entry.get("updated")
            
            # Get author
            author = None
            if "author" in entry:
                author = entry.author
            elif "authors" in entry and entry.authors:
                author = entry.authors[0].get("name")
            
            # Get teaser/summary
            teaser = None
            if "summary" in entry:
                # Strip HTML tags from summary
                soup = BeautifulSoup(entry.summary, "lxml")
                teaser = soup.get_text(separator=" ", strip=True)
            elif "description" in entry:
                soup = BeautifulSoup(entry.description, "lxml")
                teaser = soup.get_text(separator=" ", strip=True)
            
            return RawArticle(
                source=self.source_name,
                title=title,
                url=link,
                published_date=published,
                author=author,
                teaser=teaser,
            )
        except Exception as e:
            logger.warning(f"Failed to parse RSS entry: {e}")
            return None

    def _fetch_html(self, limit: int) -> list[RawArticle]:
        """Fetch articles by scraping HTML page.
        
        Args:
            limit: Maximum number of articles to fetch
            
        Returns:
            List of RawArticle objects parsed from HTML
        """
        content = self._fetch_url(AWS_BLOG_URL)
        soup = BeautifulSoup(content, "lxml")
        
        articles: list[RawArticle] = []
        
        # AWS blog uses article elements or blog-post divs
        post_elements = soup.select("article, .blog-post, .lb-post")
        
        for element in post_elements[:limit]:
            article = self._parse_html_post(element)
            if article:
                articles.append(article)
        
        return articles
    
    def _parse_html_post(self, element: Any) -> RawArticle | None:
        """Parse a single HTML post element into a RawArticle.
        
        Args:
            element: BeautifulSoup element representing a blog post
            
        Returns:
            RawArticle or None if parsing fails
        """
        try:
            # Find title and link
            title_elem = element.select_one("h2 a, h3 a, .blog-post-title a, a.title")
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            link = title_elem.get("href", "")
            
            if not title or not link:
                return None
            
            # Make absolute URL if relative
            if link.startswith("/"):
                link = f"https://aws.amazon.com{link}"
            
            # Find published date
            published = None
            date_elem = element.select_one("time, .date, .post-date, .lb-post-date")
            if date_elem:
                published = date_elem.get("datetime") or date_elem.get_text(strip=True)
            
            # Find author
            author = None
            author_elem = element.select_one(".author, .post-author, .lb-post-author")
            if author_elem:
                author = author_elem.get_text(strip=True)
            
            # Find teaser
            teaser = None
            teaser_elem = element.select_one("p, .excerpt, .teaser, .lb-post-excerpt")
            if teaser_elem:
                teaser = teaser_elem.get_text(strip=True)
            
            return RawArticle(
                source=self.source_name,
                title=title,
                url=link,
                published_date=published,
                author=author,
                teaser=teaser,
            )
        except Exception as e:
            logger.warning(f"Failed to parse HTML post: {e}")
            return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    )
    def _fetch_url(self, url: str) -> str:
        """Fetch content from URL with retry logic.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response content as string
            
        Raises:
            requests.RequestException: On network errors after retries
        """
        # Respect request pacing
        time.sleep(self.settings.request_delay_seconds)
        
        headers = {
            "User-Agent": "ContentAgent/1.0 (Blog Scraper)",
            "Accept": "application/rss+xml, application/xml, text/html",
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.text
