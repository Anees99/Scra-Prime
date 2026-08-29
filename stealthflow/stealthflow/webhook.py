"""
Webhook integration module for sending scraping results to n8n or other endpoints.

This module provides functionality to send extracted data payloads to webhook
endpoints, supporting n8n workflows and custom API integrations.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp
from pydantic import BaseModel

logger = logging.getLogger(__name__)


async def send_to_webhook(
    webhook_url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> bool:
    """
    Send a JSON payload to a webhook endpoint with retry logic.
    
    This function sends data to n8n webhooks or any other HTTP endpoint that
    accepts JSON payloads. It includes automatic retry logic for transient
    failures and proper error handling.
    
    Args:
        webhook_url: The webhook URL to send the payload to
        payload: Dictionary containing the data to send
        headers: Optional additional HTTP headers
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts on failure
        retry_delay: Base delay between retries (exponential backoff)
    
    Returns:
        True if the webhook was successfully called, False otherwise
    
    Example:
        >>> success = await send_to_webhook(
        ...     "https://n8n.example.com/webhook/scraping",
        ...     {"product": "Widget", "price": "$99.99"}
        ... )
        >>> if success:
        ...     print("Webhook sent successfully")
    """
    if not webhook_url:
        logger.error("Webhook URL is empty")
        return False
    
    # Prepare request headers
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": "StealthFlow/1.0"
    }
    
    if headers:
        request_headers.update(headers)
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.info(f"Retrying webhook ({attempt + 1}/{max_retries}) after {delay}s")
                await asyncio.sleep(delay)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=request_headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status in (200, 201, 202, 204):
                        logger.info(f"Webhook sent successfully (status: {response.status})")
                        return True
                    else:
                        error_body = await response.text()
                        logger.warning(
                            f"Webhook returned non-success status: {response.status}. "
                            f"Body: {error_body[:200]}"
                        )
                        last_error = f"HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            last_error = "Request timed out"
            logger.warning(f"Webhook request timed out (attempt {attempt + 1}/{max_retries})")
            
        except aiohttp.ClientError as e:
            last_error = f"Client error: {type(e).__name__}"
            logger.warning(f"Webhook client error (attempt {attempt + 1}/{max_retries}): {e}")
            
        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}"
            logger.exception(f"Unexpected error sending webhook (attempt {attempt + 1}/{max_retries})")
    
    logger.error(f"Failed to send webhook after {max_retries} attempts. Last error: {last_error}")
    return False


async def send_scraping_result(
    webhook_url: str,
    url: str,
    success: bool,
    data: Dict[str, Any],
    tier_used: Optional[int] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send a standardized scraping result to a webhook.
    
    This function formats scraping results into a consistent structure before
    sending to the webhook endpoint.
    
    Args:
        webhook_url: The webhook URL to send the result to
        url: The original URL that was scraped
        success: Whether the scraping operation succeeded
        data: Extracted data dictionary
        tier_used: Which tier (1, 2, or 3) successfully fetched the content
        error_message: Optional error message if scraping failed
        metadata: Optional additional metadata
    
    Returns:
        True if successfully sent, False otherwise
    
    Example:
        >>> await send_scraping_result(
        ...     webhook_url="https://n8n.example.com/webhook/scraping",
        ...     url="https://example.com/product/123",
        ...     success=True,
        ...     data={"price": "$99.99", "name": "Widget"},
        ...     tier_used=2
        ... )
    """
    from datetime import datetime
    
    payload = {
        "event_type": "scraping.completed" if success else "scraping.failed",
        "source": "stealthflow",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": {
            "url": url,
            "success": success,
            "tier_used": tier_used,
            "extracted_data": data,
            "error_message": error_message
        }
    }
    
    if metadata:
        payload["metadata"] = metadata
    
    return await send_to_webhook(webhook_url, payload)


class WebhookSender:
    """
    Class-based webhook sender with configuration persistence.
    
    This class provides a reusable webhook sender with configurable defaults,
    useful for applications that send multiple webhooks.
    
    Attributes:
        webhook_url: Default webhook URL
        default_headers: Default headers to include in all requests
        timeout: Default timeout for requests
        max_retries: Default number of retry attempts
    
    Example:
        >>> sender = WebhookSender(
        ...     webhook_url="https://n8n.example.com/webhook/data",
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> await sender.send({"key": "value"})
    """
    
    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize the WebhookSender.
        
        Args:
            webhook_url: Default webhook URL
            headers: Default headers to include
            timeout: Default timeout in seconds
            max_retries: Default number of retry attempts
        """
        self.webhook_url = webhook_url
        self.default_headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
    
    async def send(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ) -> bool:
        """
        Send a payload to the configured webhook.
        
        Args:
            payload: Data to send
            headers: Optional override headers (merged with defaults)
            timeout: Optional override timeout
            max_retries: Optional override retry count
            
        Returns:
            True if successful, False otherwise
        """
        merged_headers = {**self.default_headers}
        if headers:
            merged_headers.update(headers)
        
        return await send_to_webhook(
            webhook_url=self.webhook_url,
            payload=payload,
            headers=merged_headers,
            timeout=timeout or self.timeout,
            max_retries=max_retries or self.max_retries
        )
    
    async def send_batch(
        self,
        payloads: list,
        batch_size: int = 10
    ) -> Dict[str, int]:
        """
        Send multiple payloads with controlled concurrency.
        
        Args:
            payloads: List of payload dictionaries to send
            batch_size: Number of concurrent sends
            
        Returns:
            Dictionary with 'success' and 'failed' counts
        """
        semaphore = asyncio.Semaphore(batch_size)
        
        async def send_with_semaphore(payload):
            async with semaphore:
                return await self.send(payload)
        
        tasks = [send_with_semaphore(payload) for payload in payloads]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        failed_count = len(results) - success_count
        
        return {"success": success_count, "failed": failed_count}


async def main():
    """Example usage of webhook functionality."""
    # Simple webhook send
    success = await send_to_webhook(
        "https://httpbin.org/post",
        {"test": "data", "value": 123}
    )
    print(f"Webhook sent: {success}")
    
    # Using the class-based sender
    sender = WebhookSender("https://httpbin.org/post")
    success = await sender.send({"message": "Hello from StealthFlow"})
    print(f"Class-based send: {success}")


if __name__ == "__main__":
    asyncio.run(main())
