"""
Action Replay - Handles replaying previous page interactions.
"""

import asyncio
from typing import List, Dict, Any, Optional
from exceptions import ElementNotFoundError, AmbiguousMatchError

# Timing constants for action replay delays
HOVER_DELAY = 0.2  # Delay after hover operations
CLICK_DELAY = 0.2  # Delay after click operations
CHANGE_EVENT_DELAY = 0.3  # Delay after triggering change events


def log_replay(action_type: str, details: str = ""):
    """Helper function for consistent replay logging."""
    message = f"✅ Replayed {action_type} interaction"
    if details:
        message += f" ({details})"
    print(message)


class ActionReplayer:
    """Handles replaying previous page interactions to restore state."""
    
    def __init__(self, page, find_element_func=None):
        """Initialize with a Playwright page object and optional element finder function.
        
        Args:
            page: Playwright page object
            find_element_func: Function to re-find elements using pos_candidate info.
                             Signature: async (pos_candidate, target_element_type, target_element_text) -> element
        """
        self.page = page
        self.find_element_func = find_element_func
    
    async def replay_actions(self, page_pre_actions: List[Dict[str, Any]], type_action_value: str = None):
        """Replay previous interactions to open menus/hover states.
        
        Args:
            page_pre_actions: List of previous action states with keys:
                - 'pos_candidate': JSON string with element info to re-find element
                - 'target_element_type': Element type (button, link, etc.)
                - 'target_element_text': Element text
                - 'coordinates': Tuple of (x, y) coordinates (fallback)
                - 'op': Operation type (CLICK, SELECT, SCROLL, TYPE, HOVER)
                - 'value': Stored value for SELECT/TYPE actions
            type_action_value: Current type action value to use as fallback for TYPE operations
        """
        if not page_pre_actions:
            return
        
        for prev_state in page_pre_actions:
            pos_candidate = prev_state.get('pos_candidate')
            target_element_type = prev_state.get('target_element_type')
            target_element_text = prev_state.get('target_element_text')
            prev_coords = prev_state.get('coordinates')
            prev_op = prev_state.get('op', 'CLICK')
            prev_value = prev_state.get('value')  # Stored value for SELECT/TYPE actions
            
            if not prev_coords:
                continue
            
            # Re-find the element using stored information (elements become invalid after loading new MHTML)
            prev_element = None
            if self.find_element_func and pos_candidate and target_element_type and target_element_text:
                try:
                    element_info = await self.find_element_func(pos_candidate, target_element_type, target_element_text)
                    # find_element_by_pos_info returns a dict with 'locator' key
                    prev_element = element_info.get('locator') if element_info else None
                except (ElementNotFoundError, AmbiguousMatchError) as find_error:
                    # These are expected - element might not exist in the new MHTML
                    print(f"⚠️  Could not re-find element for replay: {find_error}")
                    print(f"   Operation: {prev_op}, will use coordinate fallback if needed")
                except Exception as find_error:
                    # Unexpected error
                    print(f"⚠️  Unexpected error re-finding element for replay: {find_error}")
                    print(f"   Operation: {prev_op}, will use coordinate fallback if needed")
            
            prev_op_upper = prev_op.upper()
            
            if prev_op_upper == 'CLICK':
                await self._replay_click(prev_element, prev_coords)
            
            elif prev_op_upper == 'SELECT':
                await self._replay_select(prev_element, prev_value)
            
            elif prev_op_upper == 'SCROLL':
                await self._replay_scroll(prev_element, prev_coords)
            
            elif prev_op_upper.startswith('TYPE'):
                await self._replay_type(prev_element, prev_value, type_action_value, prev_coords)
            
            elif prev_op_upper == 'HOVER':
                await self._replay_hover(prev_element, prev_coords)
            
            else:
                print(f"⚠️  Unknown action type: {prev_op_upper}, skipping")
    
    async def _find_input_for_label(self, label_element):
        """Find input element associated with a label element."""
        label_for = await label_element.get_attribute('for')
        if label_for:
            input_element = self.page.locator(f"#{label_for}")
            if await input_element.count() > 0:
                return input_element
        else:
            input_element = label_element.locator("input[type='checkbox'], input[type='radio']")
            if await input_element.count() > 0:
                return input_element
        return None
    
    async def _click_input_element(self, input_element, prev_coords):
        """Click an input element (checkbox/radio or other input types)."""
        input_type = await input_element.evaluate("el => el.type")
        
        if input_type == 'checkbox':
            is_checked = await input_element.is_checked()
            if not is_checked:
                await input_element.check(timeout=5000)
                log_replay("CLICK", "checkbox checked")
            else:
                await input_element.uncheck(timeout=5000)
                log_replay("CLICK", "checkbox unchecked")
        elif input_type == 'radio':
            await input_element.check(timeout=5000)
            log_replay("CLICK", "radio checked")
        else:
            try:
                await input_element.hover(timeout=2000)
                await asyncio.sleep(HOVER_DELAY)
            except Exception as hover_error:
                print(f"⚠️  Hover failed for input element: {hover_error}")
            
            try:
                await input_element.click(timeout=2000)
                await asyncio.sleep(CLICK_DELAY)
                log_replay("CLICK", "input")
            except Exception as click_error:
                print(f"⚠️  Click failed for input element: {click_error}")
                raise
        
        # Trigger change event
        await input_element.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
        await asyncio.sleep(CHANGE_EVENT_DELAY)
    
    async def _click_by_coordinates(self, prev_coords):
        """Fallback: click using stored coordinates."""
        await self.page.mouse.move(prev_coords[0], prev_coords[1])
        await asyncio.sleep(HOVER_DELAY)
        await self.page.mouse.click(prev_coords[0], prev_coords[1])
        await asyncio.sleep(CHANGE_EVENT_DELAY)
        log_replay("CLICK", "using coordinates")
    
    async def _replay_click(self, prev_element, prev_coords):
        """Replay a CLICK interaction."""
        if not prev_element:
            # Element not found, use coordinate fallback
            await self._click_by_coordinates(prev_coords)
            return
        
        try:
            tag_name = await prev_element.evaluate("el => el.tagName.toLowerCase()")
        except Exception as e:
            print(f"⚠️  Error getting tag name for click replay: {e}, using coordinates")
            await self._click_by_coordinates(prev_coords)
            return
        
        if tag_name == 'label':
            # For label elements, find and click the associated input checkbox/radio
            input_element = await self._find_input_for_label(prev_element)
            
            if input_element:
                await self._click_input_element(input_element, prev_coords)
            else:
                # No input found, use coordinates
                await self._click_by_coordinates(prev_coords)
        else:
            # For non-label elements, use element click
            try:
                await prev_element.hover(timeout=2000)
                await asyncio.sleep(HOVER_DELAY)
            except Exception as hover_error:
                print(f"⚠️  Hover failed during click replay: {hover_error}")
                print(f"   Attempting click without hover...")
            
            try:
                await prev_element.click(timeout=2000)
                await asyncio.sleep(CLICK_DELAY)
                log_replay("CLICK")
            except Exception as click_error:
                print(f"⚠️  Click failed, falling back to coordinate click: {click_error}")
                await self._click_by_coordinates(prev_coords)
    
    async def _replay_select(self, prev_element, prev_value):
        """Replay a SELECT interaction."""
        if not prev_element:
            print(f"⚠️  Element not found for select replay, skipping")
            return
        
        try:
            await prev_element.hover(timeout=2000)
            await asyncio.sleep(HOVER_DELAY)
        except Exception as hover_error:
            print(f"⚠️  Hover failed during select replay: {hover_error}")
            # Continue without hover
        
        if prev_value:
            # Try selecting by value first, then by label
            try:
                await prev_element.select_option(prev_value, timeout=2000)
                log_replay("SELECT", f"with value: {prev_value}")
            except Exception:
                try:
                    await prev_element.select_option(label=prev_value, timeout=2000)
                    log_replay("SELECT", f"with label: {prev_value}")
                except Exception as select_error:
                    print(f"⚠️  SELECT action failed: {select_error}")
        else:
            print(f"⚠️ SELECT action has no stored value, hover only")
        
        await asyncio.sleep(CLICK_DELAY)
    
    async def _replay_scroll(self, prev_element, prev_coords):
        """Replay a SCROLL interaction."""
        if not prev_element:
            # Element not found, skip scroll
            print(f"⚠️  Element not found for scroll replay, skipping")
            return
        
        try:
            await prev_element.scroll_into_view_if_needed(timeout=2000)
            await asyncio.sleep(HOVER_DELAY)
            log_replay("SCROLL")
        except Exception as scroll_error:
            print(f"⚠️  Scroll replay failed: {scroll_error}")
    
    async def _replay_type(self, prev_element, prev_value, type_action_value, prev_coords):
        """Replay a TYPE interaction."""
        if not prev_element:
            print(f"⚠️  Element not found for type replay, skipping")
            return
        
        # Use stored value if available, otherwise use current type_action_value
        value_to_type = prev_value if prev_value else type_action_value
        if not value_to_type:
            print(f"⚠️  No value to type, skipping type replay")
            return
        
        try:
            await prev_element.fill(value_to_type, timeout=2000)
            await asyncio.sleep(CLICK_DELAY)
            log_replay("TYPE", f"with value: {value_to_type}")
        except Exception as type_error:
            print(f"⚠️  Type replay failed: {type_error}")
    
    async def _replay_hover(self, prev_element, prev_coords):
        """Replay a HOVER interaction."""
        if not prev_element:
            print(f"⚠️  Element not found for hover replay, skipping")
            return
        
        try:
            await prev_element.hover(timeout=2000)
            await asyncio.sleep(HOVER_DELAY)
            log_replay("HOVER")
        except Exception as hover_error:
            print(f"⚠️  Hover replay failed: {hover_error}")
            print(f"   This may be due to element being obscured or not interactable")
            # Don't raise - continue processing

