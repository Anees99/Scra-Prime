"""
Adaptive parsing module using scrapling's auto-healing capabilities.

This module provides the AdaptiveParser class which wraps scrapling's Adaptor
to provide intelligent, self-healing HTML parsing that automatically adapts
when website structures change.
"""

import logging
from typing import Any, Dict, List, Optional

from scrapling.parser import Adaptor as ScraplingAdaptor

logger = logging.getLogger(__name__)


class AdaptiveParser:
    """
    Intelligent HTML parser with auto-healing capabilities.
    
    This class wraps scrapling's Adaptor to provide robust parsing that
    automatically adapts when CSS selectors or HTML structures change slightly.
    It supports multiple fallback selectors and smart text extraction.
    
    Attributes:
        html: The raw HTML content to parse
        tree: The parsed HTML tree (Scrapling Adaptor instance)
        logger: Logger instance for debugging
    
    Example:
        >>> parser = AdaptiveParser(html_content)
        >>> price = parser.extract_first(
        ...     selectors=['.price', '[data-price]', '.product-cost'],
        ...     attribute='text'
        ... )
    """
    
    def __init__(self, html: str):
        """
        Initialize the AdaptiveParser with HTML content.
        
        Args:
            html: Raw HTML string to parse
        """
        self.html = html
        self.tree = ScraplingAdaptor(html)
        self.logger = logging.getLogger(__name__)
    
    def css_first(self, selector: str) -> Optional['ElementWrapper']:
        """
        Find the first element matching a CSS selector.
        
        Args:
            selector: CSS selector string
            
        Returns:
            ElementWrapper if found, None otherwise
        """
        element = self.tree.css_first(selector)
        if element:
            return ElementWrapper(element)
        return None
    
    def css(self, selector: str) -> List['ElementWrapper']:
        """
        Find all elements matching a CSS selector.
        
        Args:
            selector: CSS selector string
            
        Returns:
            List of ElementWrapper objects
        """
        elements = self.tree.css(selector)
        return [ElementWrapper(el) for el in elements]
    
    def extract_first(
        self,
        selectors: List[str],
        attribute: str = 'text',
        default: Any = None
    ) -> Any:
        """
        Extract data using multiple fallback selectors.
        
        Tries each selector in order until one returns a non-None value.
        This provides resilience against HTML structure changes.
        
        Args:
            selectors: List of CSS selectors to try (in priority order)
            attribute: What to extract ('text', 'html', 'href', 'src', or any attribute name)
            default: Default value if no selector matches
            
        Returns:
            Extracted value or default
            
        Example:
            >>> price = parser.extract_first(
            ...     selectors=['.price', '[data-price]', '.cost'],
            ...     attribute='text',
            ...     default='Price not found'
            ... )
        """
        for selector in selectors:
            try:
                element = self.tree.css_first(selector)
                if element:
                    value = self._extract_attribute(element, attribute)
                    if value is not None:
                        self.logger.debug(f"Successfully extracted using selector: {selector}")
                        return value
            except Exception as e:
                self.logger.debug(f"Selector '{selector}' failed: {e}")
                continue
        
        self.logger.debug(f"No selector matched, returning default")
        return default
    
    def extract_all(
        self,
        selector: str,
        attribute: str = 'text'
    ) -> List[Any]:
        """
        Extract data from all elements matching a selector.
        
        Args:
            selector: CSS selector string
            attribute: What to extract ('text', 'html', 'href', 'src', etc.)
            
        Returns:
            List of extracted values
        """
        results = []
        elements = self.tree.css(selector)
        
        for element in elements:
            try:
                value = self._extract_attribute(element, attribute)
                if value is not None:
                    results.append(value)
            except Exception as e:
                self.logger.debug(f"Failed to extract from element: {e}")
                continue
        
        return results
    
    def _extract_attribute(self, element, attribute: str) -> Any:
        """
        Extract a specific attribute from an element.
        
        Args:
            element: Scrapling element object
            attribute: Attribute name ('text', 'html', 'href', 'src', etc.)
            
        Returns:
            Extracted value or None
        """
        if attribute == 'text':
            return element.text()
        elif attribute == 'html':
            return element.inner_html()
        elif attribute == 'outer_html':
            return element.outer_html()
        else:
            # Try to get as an attribute
            attrs = getattr(element, 'attributes', {})
            if isinstance(attrs, dict):
                return attrs.get(attribute)
            elif hasattr(attrs, 'get'):
                return attrs.get(attribute)
            return None
    
    def find_by_text(
        self,
        text_pattern: str,
        tag: Optional[str] = None,
        partial: bool = True
    ) -> Optional['ElementWrapper']:
        """
        Find an element containing specific text.
        
        Args:
            text_pattern: Text to search for
            tag: Optional HTML tag to filter by
            partial: If True, match partial text; if False, exact match only
            
        Returns:
            ElementWrapper if found, None otherwise
        """
        if tag:
            elements = self.tree.css(tag)
        else:
            elements = self.tree.css('*')
        
        for element in elements:
            try:
                text = element.text()
                if text:
                    if partial and text_pattern.lower() in text.lower():
                        return ElementWrapper(element)
                    elif not partial and text_pattern.lower() == text.lower():
                        return ElementWrapper(element)
            except Exception:
                continue
        
        return None
    
    def extract_table(self, table_selector: str) -> List[Dict[str, str]]:
        """
        Extract data from an HTML table into a list of dictionaries.
        
        Args:
            table_selector: CSS selector for the table element
            
        Returns:
            List of dictionaries, one per row
        """
        table = self.tree.css_first(table_selector)
        if not table:
            return []
        
        results = []
        headers = []
        
        # Try to get headers
        header_row = table.css_first('thead tr') or table.css_first('tr')
        if header_row:
            header_elements = header_row.css('th') or header_row.css('td')
            headers = [el.text().strip() for el in header_elements if el.text()]
        
        # Get data rows
        tbody = table.css_first('tbody') or table
        rows = tbody.css('tr')
        
        for row in rows:
            # Skip header rows
            if row.css_first('th') and headers:
                continue
            
            cells = row.css('td')
            if not cells:
                continue
            
            row_data = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    row_data[headers[i]] = cell.text().strip()
                else:
                    row_data[f'column_{i}'] = cell.text().strip()
            
            if row_data:
                results.append(row_data)
        
        return results
    
    def extract_json_ld(self) -> List[Dict[str, Any]]:
        """
        Extract JSON-LD structured data from the page.
        
        Returns:
            List of parsed JSON-LD objects
        """
        results = []
        scripts = self.tree.css('script[type="application/ld+json"]')
        
        for script in scripts:
            try:
                text = script.text()
                if text:
                    import json
                    data = json.loads(text.strip())
                    results.append(data)
            except Exception as e:
                self.logger.debug(f"Failed to parse JSON-LD: {e}")
                continue
        
        return results
    
    def get_meta(self, name_or_property: str) -> Optional[str]:
        """
        Extract meta tag content by name or property.
        
        Args:
            name_or_property: Meta tag name or property
            
        Returns:
            Content value if found, None otherwise
        """
        # Try name attribute
        element = self.tree.css_first(f'meta[name="{name_or_property}"]')
        if element:
            attrs = getattr(element, 'attributes', {})
            if isinstance(attrs, dict):
                return attrs.get('content')
        
        # Try property attribute (Open Graph)
        element = self.tree.css_first(f'meta[property="{name_or_property}"]')
        if element:
            attrs = getattr(element, 'attributes', {})
            if isinstance(attrs, dict):
                return attrs.get('content')
        
        return None
    
    def get_all_meta(self) -> Dict[str, str]:
        """
        Extract all meta tags as a dictionary.
        
        Returns:
            Dictionary mapping meta names to content values
        """
        meta_dict = {}
        metas = self.tree.css('meta')
        
        for meta in metas:
            attrs = getattr(meta, 'attributes', {})
            if isinstance(attrs, dict):
                name = attrs.get('name') or attrs.get('property')
                content = attrs.get('content')
                if name and content:
                    meta_dict[name] = content
        
        return meta_dict


class ElementWrapper:
    """
    Wrapper around Scrapling elements for consistent API.
    
    Provides a uniform interface for extracting data from HTML elements
    regardless of the underlying implementation.
    """
    
    def __init__(self, element):
        """
        Initialize with a Scrapling element.
        
        Args:
            element: Raw Scrapling element object
        """
        self._element = element
    
    def text(self) -> Optional[str]:
        """Get the text content of the element."""
        try:
            return self._element.text()
        except Exception:
            return None
    
    def html(self) -> Optional[str]:
        """Get the inner HTML of the element."""
        try:
            return self._element.inner_html()
        except Exception:
            return None
    
    def outer_html(self) -> Optional[str]:
        """Get the outer HTML of the element."""
        try:
            return self._element.outer_html()
        except Exception:
            return None
    
    def attribute(self, name: str) -> Optional[str]:
        """
        Get a specific attribute value.
        
        Args:
            name: Attribute name
            
        Returns:
            Attribute value or None
        """
        try:
            attrs = getattr(self._element, 'attributes', {})
            if isinstance(attrs, dict):
                return attrs.get(name)
            elif hasattr(attrs, 'get'):
                return attrs.get(name)
        except Exception:
            pass
        return None
    
    @property
    def attributes(self) -> Dict[str, str]:
        """Get all attributes as a dictionary."""
        try:
            attrs = getattr(self._element, 'attributes', {})
            return dict(attrs) if attrs else {}
        except Exception:
            return {}
    
    def css_first(self, selector: str) -> Optional['ElementWrapper']:
        """Find first child element matching selector."""
        try:
            element = self._element.css_first(selector)
            if element:
                return ElementWrapper(element)
        except Exception:
            pass
        return None
    
    def css(self, selector: str) -> List['ElementWrapper']:
        """Find all child elements matching selector."""
        try:
            elements = self._element.css(selector)
            return [ElementWrapper(el) for el in elements]
        except Exception:
            return []
    
    def __bool__(self) -> bool:
        """Truthiness check."""
        return self._element is not None
    
    def __repr__(self) -> str:
        """String representation."""
        text = self.text()
        if text:
            truncated = text[:50] + "..." if len(text) > 50 else text
            return f"<ElementWrapper text='{truncated}'>"
        return "<ElementWrapper>"
