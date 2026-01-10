"""Source fetcher protocol and base utilities for article fetching."""

from typing import Protocol, runtime_checkable

from src.engines.article_normalizer import RawArticle


@runtime_checkable
class SourceFetcher(Protocol):
    """Protocol defining the interface for source fetchers.
    
    All source fetchers must implement this protocol to be used
    in the content agent pipeline.
    
    Attributes:
        source_name: Identifier for the source (e.g., "AWS News Blog")
    """
    
    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        ...
    
    def fetch(self, limit: int) -> list[RawArticle]:
        """Fetch articles from the source up to the specified limit.
        
        Args:
            limit: Maximum number of articles to fetch
            
        Returns:
            List of RawArticle objects, at most `limit` items
            
        Raises:
            May raise exceptions on network or parsing errors,
            which should be handled by the caller.
        """
        ...
