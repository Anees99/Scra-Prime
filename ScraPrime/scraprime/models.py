"""
Pydantic models for ScraPrime request/response validation.

This module provides type-safe data models for scraping requests and responses,
ensuring proper validation of URLs, headers, proxies, and extracted data.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, HttpUrl, validator


class ScrapingRequest(BaseModel):
    """
    Model representing a scraping request configuration.
    
    Attributes:
        url: The target URL to scrape (must be valid HTTP/HTTPS)
        headers: Optional HTTP headers to include in the request
        proxy: Optional proxy configuration dictionary
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
    """
    
    url: HttpUrl = Field(..., description="The target URL to scrape")
    headers: Optional[Dict[str, str]] = Field(
        default=None, 
        description="Optional HTTP headers"
    )
    proxy: Optional[Dict[str, str]] = Field(
        default=None,
        description="Proxy configuration with keys: server, username, password"
    )
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    
    @validator('proxy')
    def validate_proxy(cls, v):
        """Validate proxy dictionary structure."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("Proxy must be a dictionary")
            
            required_keys = ['server']
            for key in required_keys:
                if key not in v:
                    raise ValueError(f"Proxy must contain '{key}' key")
            
            # Convert to curl_cffi compatible format if needed
            if 'username' in v and 'password' in v:
                # Format: {"http": "http://user:pass@host:port", "https": "http://user:pass@host:port"}
                auth = f"{v['username']}:{v['password']}@"
                server = v['server']
                if not server.startswith('http'):
                    server = f"http://{server}"
                return {
                    "http": server.replace('http://', f'http://{auth}'),
                    "https": server.replace('http://', f'http://{auth}')
                }
            elif not v['server'].startswith('http'):
                return {"http": f"http://{v['server']}", "https": f"http://{v['server']}"}
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.example.com/product/123",
                "headers": {"User-Agent": "Mozilla/5.0"},
                "proxy": {
                    "server": "http://proxy.example.com:8080",
                    "username": "user",
                    "password": "pass"
                },
                "timeout": 30,
                "max_retries": 3
            }
        }


class ScrapingResponse(BaseModel):
    """
    Model representing a scraping response with extracted data.
    
    Attributes:
        url: The original URL that was scraped
        success: Whether the scraping operation was successful
        tier_used: Which tier (1, 2, or 3) successfully fetched the content
        data: Dictionary containing extracted/parsed data
        timestamp: ISO 8601 timestamp of when the response was generated
        error_message: Optional error message if scraping failed
        raw_html: Optional raw HTML content (can be disabled for memory efficiency)
    """
    
    url: str = Field(..., description="The original URL that was scraped")
    success: bool = Field(..., description="Whether scraping was successful")
    tier_used: Optional[int] = Field(
        default=None,
        ge=1,
        le=3,
        description="Which tier successfully fetched the content (1=fast, 2=stealth, 3=browser)"
    )
    data: Dict[str, Any] = Field(default_factory=dict, description="Extracted data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    raw_html: Optional[str] = Field(default=None, description="Optional raw HTML content")
    
    @validator('tier_used')
    def validate_tier_used(cls, v, values):
        """Ensure tier_used is set when success is True."""
        if values.get('success') and v is None:
            raise ValueError("tier_used must be set when success is True")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.example.com/product/123",
                "success": True,
                "tier_used": 2,
                "data": {
                    "name": "Example Product",
                    "price": "$99.99",
                    "availability": "In Stock"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "error_message": None
            }
        }


class WebhookPayload(BaseModel):
    """
    Model for webhook payload sent to n8n or other endpoints.
    
    Attributes:
        event_type: Type of event (e.g., "scraping.completed", "scraping.failed")
        source: Source system identifier
        response: The ScrapingResponse object
        metadata: Additional metadata for the webhook consumer
    """
    
    event_type: str = Field(..., description="Type of webhook event")
    source: str = Field(default="scraprime", description="Source system identifier")
    response: ScrapingResponse = Field(..., description="The scraping response")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata for webhook consumers"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "scraping.completed",
                "source": "scraprime",
                "response": {
                    "url": "https://www.example.com/product/123",
                    "success": True,
                    "tier_used": 1,
                    "data": {"price": "$99.99"},
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "metadata": {"job_id": "abc123", "priority": "high"}
            }
        }
