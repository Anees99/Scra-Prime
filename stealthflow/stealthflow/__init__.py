"""
StealthFlow - Enterprise-grade web scraping with 3-tiered WAF bypass architecture.

This package provides intelligent fallback mechanisms to bypass enterprise WAFs
including Cloudflare, DataDome, and Akamai.
"""

from stealthflow.fetcher import StealthFetcher
from stealthflow.parser import AdaptiveParser
from stealthflow.webhook import send_to_webhook
from stealthflow.models import ScrapingRequest, ScrapingResponse

# Re-export scrapling's Adaptor for convenience
from scrapling import Adaptor

__version__ = "1.0.0"
__author__ = "StealthFlow Team"
__all__ = [
    "StealthFetcher",
    "AdaptiveParser",
    "send_to_webhook",
    "ScrapingRequest",
    "ScrapingResponse",
    "Adaptor",
]
