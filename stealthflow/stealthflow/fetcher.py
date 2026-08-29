"""
Core fetcher module implementing the 3-tiered WAF bypass architecture.

This module provides the StealthFetcher class which implements an intelligent
fallback system to bypass enterprise WAFs:
- Tier 1: Fast HTTP requests with TLS/JA3 spoofing (curl_cffi)
- Tier 2: Stealth fetching with built-in anti-detection (scrapling)
- Tier 3: Full browser emulation for extreme WAFs (camoufox)
"""

import asyncio
import logging
from typing import Dict, Optional

from curl_cffi import requests as cffi_requests
from scrapling import StealthyFetcher as ScraplingStealthyFetcher

try:
    from camoufox.async_api import AsyncCamoufox
    HAS_CAMOUFOX = True
except ImportError:
    HAS_CAMOUFOX = False
    AsyncCamoufox = None

logger = logging.getLogger(__name__)


class StealthFetcher:
    """
    Enterprise-grade web fetcher with 3-tiered WAF bypass capabilities.
    
    This class implements an intelligent fallback system that prioritizes speed
    while ensuring maximum success rates against enterprise WAFs like Cloudflare,
    DataDome, and Akamai.
    
    Attributes:
        proxy: Optional proxy configuration dictionary
        last_tier_used: The tier number (1, 2, or 3) used in the last fetch
        logger: Logger instance for debugging and monitoring
    
    Example:
        >>> fetcher = StealthFetcher(proxy={"server": "http://proxy:8080"})
        >>> html = await fetcher.fetch("https://example.com")
        >>> print(f"Content fetched using Tier {fetcher.last_tier_used}")
    """
    
    # WAF detection signatures
    WAF_SIGNATURES = [
        "challenge-platform",
        "datadome",
        "access denied",
        "captcha",
        "verify you are human",
        "checking your browser",
        "cloudflare",
        "akamai",
        "perimeterx",
        "incapsula",
    ]
    
    # HTTP status codes indicating WAF blocks
    BLOCK_STATUS_CODES = {403, 429, 503, 502}
    
    def __init__(self, proxy: Optional[Dict[str, str]] = None):
        """
        Initialize the StealthFetcher.
        
        Args:
            proxy: Optional proxy configuration. Can be:
                   - Dict with 'server' key (and optionally 'username', 'password')
                   - Dict with 'http' and 'https' keys for full proxy URLs
        """
        self.proxy = self._normalize_proxy(proxy) if proxy else None
        self.last_tier_used: Optional[int] = None
        self.logger = logging.getLogger(__name__)
    
    def _normalize_proxy(self, proxy: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize proxy configuration to curl_cffi format.
        
        Args:
            proxy: Raw proxy configuration
            
        Returns:
            Normalized proxy dictionary compatible with curl_cffi
        """
        if not proxy:
            return {}
        
        # Already in correct format
        if 'http' in proxy or 'https' in proxy:
            return proxy
        
        # Convert simple format to full format
        server = proxy.get('server', '')
        username = proxy.get('username')
        password = proxy.get('password')
        
        if not server.startswith('http'):
            server = f"http://{server}"
        
        if username and password:
            # Inject auth into URL
            if '://' in server:
                protocol, rest = server.split('://', 1)
                server = f"{protocol}://{username}:{password}@{rest}"
            else:
                server = f"http://{username}:{password}@{server}"
        
        return {"http": server, "https": server}
    
    async def fetch(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ) -> Optional[str]:
        """
        Fetch HTML content using the 3-tiered fallback system.
        
        This method attempts to fetch the target URL using three progressively
        more powerful techniques:
        1. Fast HTTP request with TLS spoofing
        2. Stealth fetcher with anti-detection
        3. Full headless browser emulation
        
        Args:
            url: The target URL to fetch
            headers: Optional HTTP headers to include
            timeout: Request timeout in seconds (default: 30)
            
        Returns:
            HTML content as string if successful, None if all tiers fail
            
        Example:
            >>> fetcher = StealthFetcher()
            >>> html = await fetcher.fetch("https://example.com")
            >>> if html:
            ...     print(f"Successfully fetched {len(html)} bytes")
        """
        self.logger.info(f"[StealthFlow] Starting fetch for: {url}")
        
        # TIER 1: Fast HTTP with TLS spoofing
        html_content = await self._fetch_tier1_curl(url, headers, timeout)
        
        if html_content is None:
            self.logger.warning(f"[StealthFlow] Tier 1 blocked. Falling back to Tier 2 (Scrapling) for {url}")
            html_content = await self._fetch_tier2_scrapling(url, headers, timeout)
        
        if html_content is None:
            self.logger.warning(f"[StealthFlow] Tier 2 blocked. Falling back to Tier 3 (Camoufox) for {url}")
            html_content = await self._fetch_tier3_camoufox(url, timeout)
        
        if html_content:
            self.logger.info(f"[StealthFlow] Successfully fetched {url} using Tier {self.last_tier_used}")
        else:
            self.logger.error(f"[StealthFlow] All tiers failed for {url}")
        
        return html_content
    
    async def _fetch_tier1_curl(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]],
        timeout: int
    ) -> Optional[str]:
        """
        Tier 1: Fast HTTP request with TLS/JA3 fingerprint spoofing.
        
        Uses curl_cffi to impersonate Chrome's TLS fingerprint, which bypasses
        basic bot detection. This is the fastest tier but may not work against
        advanced WAFs.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers
            timeout: Request timeout
            
        Returns:
            HTML content if successful, None if blocked
        """
        try:
            response = await asyncio.to_thread(
                cffi_requests.get,
                url,
                impersonate="chrome120",
                proxies=self.proxy,
                headers=headers,
                timeout=timeout
            )
            
            # Check for block status codes
            if response.status_code in self.BLOCK_STATUS_CODES:
                self.logger.debug(f"Tier 1 blocked: HTTP {response.status_code}")
                return None
            
            text = response.text
            
            # Check for WAF signatures in response
            if self._is_waf_response(text):
                self.logger.debug("Tier 1 blocked: WAF signature detected")
                return None
            
            # Check for empty or minimal responses
            if len(text.strip()) < 100:
                self.logger.debug("Tier 1 blocked: Minimal response")
                return None
            
            self.last_tier_used = 1
            return text
            
        except Exception as e:
            self.logger.debug(f"Tier 1 exception: {type(e).__name__}: {e}")
            return None
    
    async def _fetch_tier2_scrapling(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]],
        timeout: int
    ) -> Optional[str]:
        """
        Tier 2: Stealth fetcher with built-in anti-detection.
        
        Uses scrapling's StealthyFetcher which implements various techniques
        to bypass moderate WAF protections including Cloudflare's 5-second shield.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers
            timeout: Request timeout
            
        Returns:
            HTML content if successful, None if blocked
        """
        try:
            fetcher = ScraplingStealthyFetcher(auto_match=False)
            
            response = await asyncio.to_thread(
                fetcher.get,
                url,
                proxies=self.proxy,
                headers=headers,
                timeout=timeout
            )
            
            # Check status code
            if hasattr(response, 'status') and response.status in self.BLOCK_STATUS_CODES:
                self.logger.debug(f"Tier 2 blocked: HTTP {response.status}")
                return None
            
            # Get body content
            body = response.body if hasattr(response, 'body') else response.text
            
            # Validate response
            if not body or len(body.strip()) < 100:
                self.logger.debug("Tier 2 blocked: Empty or minimal response")
                return None
            
            if self._is_waf_response(body):
                self.logger.debug("Tier 2 blocked: WAF signature detected")
                return None
            
            self.last_tier_used = 2
            return body
            
        except Exception as e:
            self.logger.debug(f"Tier 2 exception: {type(e).__name__}: {e}")
            return None
    
    async def _fetch_tier3_camoufox(self, url: str, timeout: int) -> Optional[str]:
        """
        Tier 3: Full headless browser emulation for extreme WAFs.
        
        Uses Camoufox with C++ level fingerprint spoofing to bypass the most
        advanced WAFs including DataDome and Arkose. This is the slowest tier
        but has the highest success rate.
        
        Args:
            url: Target URL
            timeout: Maximum time to wait for page load
            
        Returns:
            HTML content if successful, None if blocked
            
        Raises:
            ImportError: If camoufox is not installed
        """
        if not HAS_CAMOUFOX:
            self.logger.error("Camoufox is not installed. Run: pip install camoufox[geoip]")
            raise ImportError(
                "Camoufox is required for Tier 3 fetching. "
                "Please install it with: pip install camoufox[geoip]"
            )
        
        try:
            async with AsyncCamoufox(
                headless=True,
                humanize=True,        # Simulate human behavior
                geoip=True,           # Spoof geolocation based on IP
                block_images=False,   # Load images for complete rendering
                os=['windows'],       # Spoof Windows OS
                proxy=self.proxy
            ) as browser:
                page = await browser.new_page()
                
                try:
                    # Navigate and wait for network to settle
                    await page.goto(url, wait_until="networkidle", timeout=min(timeout * 1000, 60000))
                    
                    # Additional wait for invisible JS challenges
                    await page.wait_for_timeout(4000)
                    
                    # Get final HTML after all JS execution
                    html = await page.content()
                    
                    # Final validation
                    if html and len(html.strip()) > 100 and not self._is_waf_response(html):
                        self.last_tier_used = 3
                        return html
                    
                    self.logger.debug("Tier 3: WAF still present after browser render")
                    return None
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            self.logger.error(f"Tier 3 exception: {type(e).__name__}: {e}")
            return None
    
    def _is_waf_response(self, html: str) -> bool:
        """
        Detect if HTML content contains WAF blocking indicators.
        
        Args:
            html: HTML content to analyze
            
        Returns:
            True if WAF signatures detected, False otherwise
        """
        if not html:
            return True
        
        html_lower = html.lower()
        
        for signature in self.WAF_SIGNATURES:
            if signature.lower() in html_lower:
                return True
        
        return False
    
    async def fetch_with_retry(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Fetch with automatic retry logic for transient failures.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers
            timeout: Request timeout
            max_retries: Maximum number of retry attempts
            
        Returns:
            HTML content if successful, None if all retries fail
        """
        last_error = None
        
        for attempt in range(max_retries):
            if attempt > 0:
                self.logger.info(f"Retry attempt {attempt + 1}/{max_retries} for {url}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            result = await self.fetch(url, headers, timeout)
            
            if result is not None:
                return result
            
            last_error = f"All tiers failed on attempt {attempt + 1}"
        
        self.logger.error(f"All retries exhausted for {url}: {last_error}")
        return None


async def main():
    """Example usage of StealthFetcher."""
    fetcher = StealthFetcher()
    
    url = "https://httpbin.org/html"
    html = await fetcher.fetch(url)
    
    if html:
        print(f"Successfully fetched {len(html)} bytes using Tier {fetcher.last_tier_used}")
    else:
        print("Failed to fetch content")


if __name__ == "__main__":
    asyncio.run(main())
