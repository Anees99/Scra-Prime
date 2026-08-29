"""
ScraPrime - Enterprise-grade web scraping with 3-tiered WAF bypass architecture.

This package provides intelligent fallback mechanisms to bypass enterprise WAFs
including Cloudflare, DataDome, and Akamai.
"""

from scraprime.fetcher import StealthFetcher
from scraprime.parser import AdaptiveParser
from scraprime.webhook import send_to_webhook
from scraprime.models import ScrapingRequest, ScrapingResponse

# Re-export scrapling's Adaptor for convenience
from scrapling.parser import Adaptor

__version__ = "1.0.0"
__author__ = "ScraPrime Team"
__all__ = [
    "StealthFetcher",
    "AdaptiveParser",
    "send_to_webhook",
    "ScrapingRequest",
    "ScrapingResponse",
    "Adaptor",
]
