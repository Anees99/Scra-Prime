"""
StealthFlow Usage Examples

This file demonstrates how to use StealthFlow for various scraping scenarios,
including bypassing DataDome protection, adaptive parsing, and webhook integration.
"""

import asyncio
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# EXAMPLE 1: Basic Scraping with 3-Tiered Fallback
# =============================================================================

async def example_basic_scraping():
    """
    Demonstrate basic HTML fetching with automatic tier fallback.
    """
    from stealthflow import StealthFetcher
    
    fetcher = StealthFetcher()
    
    # Fetch a simple page (should succeed with Tier 1)
    url = "https://httpbin.org/html"
    html = await fetcher.fetch(url)
    
    if html:
        print(f"✓ Successfully fetched {len(html)} bytes using Tier {fetcher.last_tier_used}")
    else:
        print("✗ Failed to fetch content")


# =============================================================================
# EXAMPLE 2: Scraping a DataDome-Protected Site
# =============================================================================

async def example_datadome_scraping():
    """
    Scrape a DataDome-protected e-commerce site with proxy support.
    This demonstrates the full power of the 3-tiered fallback system.
    """
    from stealthflow import StealthFetcher, Adaptor
    
    # Configure your proxy (required for most protected sites)
    proxy_config = {
        "server": "http://your-proxy-server:port",
        "username": "your-username",
        "password": "your-password"
    }
    
    # Initialize fetcher with proxy
    fetcher = StealthFetcher(proxy=proxy_config)
    
    # Target a DataDome-protected product page
    target_url = "https://www.very.co.uk/some-product-page"
    
    # Add custom headers if needed
    custom_headers = {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    # Fetch with automatic fallback through all tiers
    html = await fetcher.fetch(target_url, headers=custom_headers, timeout=45)
    
    if not html:
        logger.error("All tiers failed to fetch the page")
        return None
    
    logger.info(f"Successfully fetched using Tier {fetcher.last_tier_used}")
    
    # Parse with scrapling's Adaptor for adaptive extraction
    tree = Adaptor(html)
    
    # Extract price using flexible selectors (auto-heals if HTML changes)
    price_element = tree.css_first('[data-testid="product-price__basic"]')
    
    if price_element:
        price = price_element.text()
        logger.info(f"Extracted Price: {price}")
        return {"price": price}
    else:
        # Try alternative selectors
        alt_price = tree.css_first('.product-price')
        price = alt_price.text() if alt_price else None
        
        if not price:
            alt_price = tree.css_first('[data-price]')
            price = alt_price.text() if alt_price else None
        
        if not price:
            alt_price = tree.css_first('.price-current')
            price = alt_price.text() if alt_price else None
        
        if price:
            logger.info(f"Extracted Price (fallback): {price}")
            return {"price": price}
    
    logger.warning("Price element not found")
    return None


# =============================================================================
# EXAMPLE 3: Complete Workflow with n8n Webhook Integration
# =============================================================================

async def example_complete_workflow_with_webhook():
    """
    Complete scraping workflow: fetch → parse → send to n8n webhook.
    This is the production-ready pattern for enterprise scraping.
    """
    from stealthflow import StealthFetcher, Adaptor, send_to_webhook
    from stealthflow.models import ScrapingRequest, ScrapingResponse
    
    # Configuration
    WEBHOOK_URL = "https://your-n8n-instance.com/webhook/scraping-data"
    TARGET_URL = "https://www.very.co.uk/product/example-item"
    
    # Proxy configuration (use rotating proxies for production)
    proxy_config = {
        "server": "http://ip:port",
        "username": "user",
        "password": "pass"
    }
    
    # Step 1: Create validated request
    request = ScrapingRequest(
        url=TARGET_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        },
        proxy=proxy_config,
        timeout=45,
        max_retries=3
    )
    
    # Step 2: Initialize fetcher
    fetcher = StealthFetcher(proxy=request.proxy)
    
    # Step 3: Fetch with 3-tier fallback
    logger.info(f"Fetching {request.url}...")
    html = await fetcher.fetch(request.url, request.headers, timeout=request.timeout)
    
    if not html:
        # Send failure notification to webhook
        error_response = ScrapingResponse(
            url=request.url,
            success=False,
            tier_used=None,
            data={},
            error_message="All scraping tiers failed"
        )
        await send_to_webhook(WEBHOOK_URL, error_response.model_dump())
        return
    
    logger.info(f"✓ Content fetched successfully using Tier {fetcher.last_tier_used}")
    
    # Step 4: Adaptive parsing with auto-healing selectors
    tree = Adaptor(html)
    
    # Define multiple selector strategies for resilience
    def get_text_or_empty(selector):
        """Helper to safely extract text from CSS selector."""
        el = tree.css_first(selector)
        return el.text() if el else ""
    
    def get_attribute_or_empty(selector, attr):
        """Helper to safely extract attribute from CSS selector."""
        el = tree.css_first(selector)
        return el.attribute(attr) if el else ""
    
    product_data: Dict[str, Any] = {
        "name": get_text_or_empty('.product-title') or get_text_or_empty('h1.product-name'),
        "price": get_text_or_empty('[data-testid="product-price__basic"]') or 
                 get_text_or_empty('.product-price .current') or 
                 get_text_or_empty('[data-price]'),
        "availability": get_text_or_empty('.stock-status') or 
                       get_text_or_empty('[data-stock]') or 
                       get_text_or_empty('.availability'),
        "image_url": get_attribute_or_empty('.product-image img', 'src') or 
                    get_attribute_or_empty('meta[property="og:image"]', 'content'),
        "description": get_text_or_empty('.product-description') or get_text_or_empty('#product-details')
    }
    
    # Clean up extracted data
    product_data = {k: v.strip() if isinstance(v, str) else v 
                   for k, v in product_data.items()}
    
    logger.info(f"Extracted product data: {product_data}")
    
    # Step 5: Create validated response
    response = ScrapingResponse(
        url=request.url,
        success=True,
        tier_used=fetcher.last_tier_used,
        data=product_data,
        raw_html=None  # Set to html if you need to store raw content
    )
    
    # Step 6: Send to n8n webhook
    webhook_payload = {
        "event_type": "scraping.completed",
        "source": "stealthflow",
        "response": response.model_dump(),
        "metadata": {
            "job_id": "example-job-123",
            "priority": "high",
            "processing_time_ms": 5000  # You can track actual time
        }
    }
    
    success = await send_to_webhook(WEBHOOK_URL, webhook_payload)
    
    if success:
        logger.info("✓ Webhook sent successfully to n8n")
    else:
        logger.error("✗ Failed to send webhook")
    
    return response


# =============================================================================
# EXAMPLE 4: Concurrent Scraping with Multiple URLs
# =============================================================================

async def example_concurrent_scraping():
    """
    Scrape multiple URLs concurrently with controlled parallelism.
    """
    from stealthflow import StealthFetcher, Adaptor
    
    urls = [
        "https://www.very.co.uk/product/item-1",
        "https://www.very.co.uk/product/item-2",
        "https://www.very.co.uk/product/item-3",
        "https://www.very.co.uk/product/item-4",
        "https://www.very.co.uk/product/item-5",
    ]
    
    proxy_config = {
        "server": "http://your-proxy:port",
        "username": "user",
        "password": "pass"
    }
    
    async def scrape_single(url: str, fetcher: StealthFetcher) -> Dict[str, Any]:
        """Scrape a single URL."""
        html = await fetcher.fetch(url)
        
        if not html:
            return {"url": url, "success": False, "data": None}
        
        tree = Adaptor(html)
        
        name_el = tree.css_first('.product-title')
        price_el = tree.css_first('[data-testid="product-price__basic"]')
        
        return {
            "url": url,
            "success": True,
            "tier_used": fetcher.last_tier_used,
            "data": {
                "name": name_el.text() if name_el else "",
                "price": price_el.text() if price_el else ""
            }
        }
    
    # Use semaphore to control concurrency (avoid overwhelming proxies)
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
    
    async def scrape_with_semaphore(url: str, fetcher: StealthFetcher) -> Dict[str, Any]:
        async with semaphore:
            return await scrape_single(url, fetcher)
    
    # Create fetcher per URL or share one (sharing is fine for same domain)
    fetcher = StealthFetcher(proxy=proxy_config)
    
    # Run all scrapes concurrently
    tasks = [scrape_with_semaphore(url, fetcher) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successful = [r for r in results if isinstance(r, dict) and r.get('success')]
    failed = [r for r in results if isinstance(r, dict) and not r.get('success')]
    exceptions = [r for r in results if isinstance(r, Exception)]
    
    logger.info(f"Scraping complete: {len(successful)} successful, {len(failed)} failed, {len(exceptions)} errors")
    
    return results


# =============================================================================
# EXAMPLE 5: Using Individual Tiers Directly
# =============================================================================

async def example_manual_tier_selection():
    """
    Manually select which tier to use based on known site requirements.
    Useful when you know a site needs specific handling.
    """
    from stealthflow import StealthFetcher
    
    fetcher = StealthFetcher()
    url = "https://example.com"
    
    # Use only Tier 1 for simple sites (fastest)
    html = await fetcher._fetch_tier1_curl(url, headers=None, timeout=15)
    if html:
        print(f"Tier 1 succeeded: {len(html)} bytes")
        return
    
    # Use only Tier 2 for Cloudflare 5s shield
    html = await fetcher._fetch_tier2_scrapling(url, headers=None, timeout=30)
    if html:
        print(f"Tier 2 succeeded: {len(html)} bytes")
        return
    
    # Use only Tier 3 for DataDome/Arkose
    html = await fetcher._fetch_tier3_camoufox(url, timeout=60)
    if html:
        print(f"Tier 3 succeeded: {len(html)} bytes")


# =============================================================================
# EXAMPLE 6: Advanced Parsing Techniques
# =============================================================================

async def example_advanced_parsing():
    """
    Demonstrate advanced parsing techniques with AdaptiveParser.
    """
    from stealthflow import StealthFetcher, AdaptiveParser
    
    fetcher = StealthFetcher()
    html = await fetcher.fetch("https://example.com/products")
    
    if not html:
        return
    
    # Use AdaptiveParser for intelligent extraction
    parser = AdaptiveParser(html)
    
    # Method 1: Multiple fallback selectors
    price = parser.extract_first(
        selectors=[
            '.product-price',
            '[data-price]',
            '.price-current',
            'span.cost'
        ],
        attribute='text',
        default='Price not found'
    )
    
    # Method 2: Extract all matching elements
    all_prices = parser.extract_all('.product-price', attribute='text')
    
    # Method 3: Find by text content
    sale_element = parser.find_by_text('Sale', tag='span', partial=True)
    
    # Method 4: Extract table data
    spec_table = parser.extract_table('.product-specifications')
    
    # Method 5: Extract JSON-LD structured data
    json_ld_data = parser.extract_json_ld()
    
    # Method 6: Extract meta tags
    og_title = parser.get_meta('og:title')
    all_meta = parser.get_all_meta()
    
    print(f"Price: {price}")
    print(f"All prices: {all_prices}")
    print(f"JSON-LD: {json_ld_data}")
    print(f"Meta title: {og_title}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

async def main():
    """Run all examples."""
    print("=" * 70)
    print("StealthFlow Usage Examples")
    print("=" * 70)
    
    # Example 1: Basic scraping
    print("\n[Example 1] Basic Scraping")
    await example_basic_scraping()
    
    # Example 2: DataDome scraping (requires valid proxy)
    # print("\n[Example 2] DataDome Scraping")
    # await example_datadome_scraping()
    
    # Example 3: Complete workflow with webhook (configure webhook URL)
    # print("\n[Example 3] Complete Workflow with Webhook")
    # await example_complete_workflow_with_webhook()
    
    # Example 4: Concurrent scraping
    # print("\n[Example 4] Concurrent Scraping")
    # await example_concurrent_scraping()
    
    # Example 5: Manual tier selection
    # print("\n[Example 5] Manual Tier Selection")
    # await example_manual_tier_selection()
    
    # Example 6: Advanced parsing
    # print("\n[Example 6] Advanced Parsing")
    # await example_advanced_parsing()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
