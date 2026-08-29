# ScraPrime

**Enterprise-grade web scraping package with 3-tiered WAF bypass architecture**

ScraPrime is a commercial-grade Python package designed to bypass enterprise Web Application Firewalls (WAFs) including Cloudflare, DataDome, and Akamai. It uses an intelligent 3-tiered fallback system that prioritizes speed while ensuring maximum success rates.

## Features

- **3-Tiered Fallback Architecture**: 
  - Tier 1: Fast HTTP requests with TLS/JA3 spoofing using `curl_cffi`
  - Tier 2: Stealth fetching with `scrapling.StealthyFetcher`
  - Tier 3: Full browser emulation with `camoufox` for extreme WAFs

- **Adaptive Parsing**: Uses `scrapling.Adaptor` for auto-healing CSS selectors when HTML structure changes

- **Webhook Integration**: Built-in support for sending extracted data to n8n or any webhook endpoint

- **Async/Await Support**: Fully asynchronous design for high-performance concurrent scraping

- **Proxy Support**: Compatible with HTTP/HTTPS proxies across all tiers

## Installation

```bash
pip install scraprime

# With GeoIP support for better fingerprint spoofing
pip install scraprime[geoip]
```

Or install from source:

```bash
git clone https://github.com/scraprime/scraprime.git
cd scraprime
pip install -r requirements.txt
pip install -e .
```

## Quick Start

```python
import asyncio
from scraprime import StealthFetcher, Adaptor

async def main():
    # Initialize the fetcher with optional proxy
    fetcher = StealthFetcher(proxy={"server": "http://your-proxy:port"})
    
    # Fetch HTML with automatic 3-tier fallback
    html = await fetcher.fetch("https://example.com/product")
    
    # Parse adaptively with scrapling
    tree = Adaptor(html)
    price = tree.css_first('[data-testid="product-price"]')
    
    print(f"Price: {price.text() if price else 'Not found'}")

asyncio.run(main())
```

## Advanced Usage

### Complete Example with Webhook

```python
import asyncio
from scraprime import StealthFetcher, Adaptor, send_to_webhook
from scraprime.models import ScrapingRequest, ScrapingResponse

async def scrape_and_send():
    # Define request with validation
    request = ScrapingRequest(
        url="https://www.very.co.uk/some-product-page",
        headers={"User-Agent": "Mozilla/5.0 ..."},
        proxy={"server": "http://ip:port", "username": "user", "password": "pass"}
    )
    
    # Initialize fetcher
    fetcher = StealthFetcher(proxy=request.proxy)
    
    # Fetch with 3-tier fallback
    html = await fetcher.fetch(request.url, request.headers)
    
    if not html:
        print("All tiers failed to fetch the page")
        return
    
    # Adaptive parsing with auto-healing selectors
    tree = Adaptor(html)
    
    # Extract data using flexible CSS selectors
    product_data = {
        "name": tree.css_first(".product-title")?.text() or "",
        "price": tree.css_first('[data-testid="product-price__basic"]')?.text() or "",
        "availability": tree.css_first(".stock-status")?.text() or "",
        "image": tree.css_first(".product-image img")?.attributes.get("src") or ""
    }
    
    # Create validated response
    response = ScrapingResponse(
        url=request.url,
        success=True,
        tier_used=fetcher.last_tier_used,
        data=product_data
    )
    
    # Send to n8n webhook
    webhook_url = "https://your-n8n-instance.com/webhook/scraping-data"
    await send_to_webhook(webhook_url, response.model_dump())
    
    print(f"Extracted: {product_data}")

asyncio.run(scrape_and_send())
```

### Manual Tier Selection

You can also use individual tier methods directly:

```python
from scraprime import StealthFetcher

fetcher = StealthFetcher()

# Use only Tier 1 (fastest)
html = await fetcher._fetch_tier1_curl(url)

# Use only Tier 2 (medium speed)
html = await fetcher._fetch_tier2_scrapling(url)

# Use only Tier 3 (slowest but most powerful)
html = await fetcher._fetch_tier3_camoufox(url)
```

## Configuration Options

### StealthFetcher Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `proxy` | `dict`, optional | Proxy configuration in format `{"server": "http://...", "username": "...", "password": "..."}` |

### AsyncCamoufox Options (Tier 3)

- `humanize=True`: Simulates human-like mouse movements and typing
- `geoip=True`: Spoofs geolocation based on IP
- `block_images=False`: Loads images for complete page rendering
- `os=['windows']`: Spoofs Windows OS fingerprint

## Pydantic Models

### ScrapingRequest

```python
class ScrapingRequest(BaseModel):
    url: HttpUrl
    headers: Optional[Dict[str, str]] = None
    proxy: Optional[Dict[str, str]] = None
    timeout: int = 30
```

### ScrapingResponse

```python
class ScrapingResponse(BaseModel):
    url: str
    success: bool
    tier_used: int
    data: Dict[str, Any]
    timestamp: datetime
    error_message: Optional[str] = None
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ScraPrime                              │
├─────────────────────────────────────────────────────────────┤
│  Tier 1: curl_cffi (Fast HTTP with TLS spoofing)           │
│         ↓ (403/503/WAF detected)                            │
│  Tier 2: scrapling.StealthyFetcher (Stealth HTTP)          │
│         ↓ (Still blocked)                                   │
│  Tier 3: camoufox.AsyncCamoufox (Full Browser Emulation)   │
├─────────────────────────────────────────────────────────────┤
│  Adaptive Parser: scrapling.Adaptor (Auto-healing CSS)     │
├─────────────────────────────────────────────────────────────┤
│  Webhook: aiohttp → n8n / Custom API                       │
└─────────────────────────────────────────────────────────────┘
```

## WAF Detection

ScraPrime automatically detects WAF blocks by checking for:

- HTTP status codes: 403, 429, 503
- HTML signatures: "challenge-platform", "datadome", "Access Denied"
- Empty or minimal responses

## Troubleshooting

### All Tiers Failed

If all three tiers fail to fetch a page:

1. Check your proxy configuration
2. Verify the target URL is accessible
3. Try rotating to a different proxy IP
4. Increase timeouts for slow-loading pages

### Camoufox Import Error

```bash
pip install camoufox[geoip]
```

### Slow Performance

- Tier 3 (Camoufox) is intentionally slower but more reliable
- Consider running multiple requests concurrently with `asyncio.gather()`
- Use Tier 1 or 2 when possible for high-volume scraping

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please submit PRs to the GitHub repository.

## Support

For enterprise support and custom integrations, contact: support@scraprime.io
