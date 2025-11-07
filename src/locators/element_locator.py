"""
Element Locator - Finds elements using a priority cascade strategy.
Simplified to use strategy classes.
"""

import json
from typing import Dict, Optional, List

from exceptions import ElementLocatorError, ElementNotFoundError, AmbiguousMatchError
from .strategies import (
    IdStrategy, DataTestIdStrategy, RoleAndTextStrategy, TextStrategy,
    FingerprintStrategy, TagAndClassStrategy, BroadSearchStrategy,
    ContextualContainerStrategy
)


class ElementLocator:
    """
    Finds elements using a simple priority cascade strategy.
    Tries each locator method in order, stops at first success.
    """
    

    def __init__(self, pos_candidate_json: str, target_element_type: str, target_element_text: str):
        """Parses the input JSON and extracts fingerprint + bounding box."""
        try:
            parsed_data = json.loads(pos_candidate_json) if isinstance(pos_candidate_json, str) else pos_candidate_json
        except json.JSONDecodeError:
            raise ValueError("Input is not valid JSON.")
        
        try:
            attrs_str = parsed_data.get('attributes', '{}')
            self.attrs = json.loads(attrs_str) if isinstance(attrs_str, str) else attrs_str or {}
        except json.JSONDecodeError:
            self.attrs = {}
        
        self.parsed_data = parsed_data
        self.fingerprint: Dict[str, str] = {}
        self._extract_fingerprint()
        self.original_box = self._extract_bbox()
        self.target_element_type = target_element_type
        self.target_element_text = target_element_text

    def _get_attr(self, key: str, normalize: bool = True) -> Optional[str]:
        """Get attribute value from nested or top-level, optionally normalize key."""
        value = self.attrs.get(key) or self.attrs.get(key.replace('_', '-'))
        if not value:
            value = self.parsed_data.get(key)
        if value and str(value).strip():
            return str(value).strip()
        return None
    
    def _extract_fingerprint(self):
        """Extract element fingerprint from attributes."""
        if tag := self.parsed_data.get('tag'):
            self.fingerprint['tag'] = tag
        
        for key in ['id', 'aria_label', 'aria-label', 'placeholder', 'name']:
            if value := self._get_attr(key):
                self.fingerprint[key.replace('-', '_')] = value
        
        if value := self._get_attr('role'):
            self.fingerprint['role'] = value
        
        if value := self._get_attr('class'):
            classes = value.split()
            if classes:
                self.fingerprint['class'] = classes[0]
        
        test_id = (self.attrs.get('data-testid') or 
                  self.attrs.get('data_pw_testid_buckeye_candidate') or
                  self.attrs.get('data-testid_buckeye_candidate'))
        if test_id and str(test_id).strip():
            self.fingerprint['data_testid'] = str(test_id).strip()
    
    def _extract_bbox(self) -> Optional[Dict[str, float]]:
        """Extract bounding box from attributes."""
        bbox_str = self.attrs.get('bounding_box_rect') or self.parsed_data.get('bounding_box_rect')
        if not bbox_str or not isinstance(bbox_str, str):
            return None
        
        try:
            parts = bbox_str.split(',')
            if len(parts) >= 4:
                return {
                    'x': float(parts[0]),
                    'y': float(parts[1]),
                    'width': float(parts[2]),
                    'height': float(parts[3])
                }
        except (ValueError, IndexError):
            pass
        return None

    
    async def find_element(self, page):
        """Find element using text, type, and fingerprint in priority order.
        target_element_text can be empty, but target_element_type is required."""
        if not self.target_element_type:
            raise ElementNotFoundError("target_element_type must be provided")
        
        has_text = self.target_element_text and self.target_element_text.strip()
        text_display = self.target_element_text if has_text else "(empty)"
        print(f"🔍 Searching for element: type='{self.target_element_type}', text='{text_display}'")
        print(f"   Fingerprint: {self.fingerprint}")
        
        type_lower = self.target_element_type.lower()
        
        # Map type to Playwright role
        type_to_role = {
            'link': 'link', 'button': 'button', 'searchbox': 'searchbox',
            'input': 'textbox', 'textbox': 'textbox', 'combobox': 'combobox',
            'checkbox': 'checkbox', 'menuitem': 'menuitem', 'heading': 'heading', 'option': 'option',
        }
        role = type_to_role.get(type_lower)
        
        # Create strategy instances
        strategies = [
            IdStrategy(self.fingerprint, self.target_element_type, self.target_element_text or '', self.original_box),
            DataTestIdStrategy(self.fingerprint, self.target_element_type, self.target_element_text or '', self.original_box),
        ]
        
        # Add text-based strategies only if we have meaningful text
        if has_text:
            strategies.extend([
                ContextualContainerStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
                RoleAndTextStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
                TextStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            ])
        
        # Add fingerprint-based strategies (work with or without text)
        strategies.extend([
            FingerprintStrategy(self.fingerprint, self.target_element_type, self.target_element_text or '', self.original_box),
            TagAndClassStrategy(self.fingerprint, self.target_element_type, self.target_element_text or '', self.original_box),
        ])
        
        # Add broad search only if we have text
        if has_text:
            strategies.append(
                BroadSearchStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box)
            )
        
        # Try strategies in priority order
        for strategy in strategies:
            if isinstance(strategy, RoleAndTextStrategy):
                result = await strategy.execute(page, role)
            elif isinstance(strategy, (FingerprintStrategy, TagAndClassStrategy, ContextualContainerStrategy)):
                result = await strategy.execute(page, type_lower)
            else:
                result = await strategy.execute(page)
            
            if result:
                return result
        
        raise ElementNotFoundError(
            f"No element found: type='{self.target_element_type}', text='{text_display}', "
            f"fingerprint={self.fingerprint}"
        )

