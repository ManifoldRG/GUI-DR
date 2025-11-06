"""
Action Replay - Handles replaying previous page interactions.
"""

import asyncio
from typing import List, Dict, Any, Optional

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
    
    def __init__(self, page):
        """Initialize with a Playwright page object."""
        self.page = page
    
    async def replay_actions(self, page_pre_actions: List[Dict[str, Any]], type_action_value: str = None):
        """Replay previous interactions to open menus/hover states.
        
        Args:
            page_pre_actions: List of previous action states with keys:
                - 'element': Playwright element locator
                - 'coordinates': Tuple of (x, y) coordinates
                - 'op': Operation type (CLICK, SELECT, SCROLL, TYPE, HOVER)
                - 'value': Stored value for SELECT/TYPE actions
            type_action_value: Current type action value to use as fallback for TYPE operations
        """
        if not page_pre_actions:
            return
        
        for prev_state in page_pre_actions:
            prev_element = prev_state.get('element')
            prev_coords = prev_state.get('coordinates')
            prev_op = prev_state.get('op', 'CLICK')
            prev_value = prev_state.get('value')  # Stored value for SELECT/TYPE actions
            
            if not prev_element or not prev_coords:
                continue
            
            prev_op_upper = prev_op.upper()
            
            if prev_op_upper == 'CLICK':
                await self._replay_click(prev_element, prev_coords)
            
            elif prev_op_upper == 'SELECT':
                await self._replay_select(prev_element, prev_value)
            
            elif prev_op_upper == 'SCROLL':
                await self._replay_scroll(prev_element)
            
            elif prev_op_upper.startswith('TYPE'):
                await self._replay_type(prev_element, prev_value, type_action_value)
            
            elif prev_op_upper == 'HOVER':
                await self._replay_hover(prev_element)
            
            else:
                raise ValueError(f"Unknown action type: {prev_op_upper}")
    
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
            await input_element.hover(timeout=2000)
            await asyncio.sleep(HOVER_DELAY)
            await input_element.click(timeout=5000)
            await asyncio.sleep(CLICK_DELAY)
            log_replay("CLICK", "input")
        
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
        tag_name = await prev_element.evaluate("el => el.tagName.toLowerCase()")
        
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
            await prev_element.hover(timeout=2000)
            await asyncio.sleep(HOVER_DELAY)
            await prev_element.click(timeout=2000)
            await asyncio.sleep(CLICK_DELAY)
            log_replay("CLICK")
    
    async def _replay_select(self, prev_element, prev_value):
        """Replay a SELECT interaction."""
        await prev_element.hover(timeout=2000)
        await asyncio.sleep(HOVER_DELAY)
        
        if prev_value:
            # Try selecting by value first, then by label
            try:
                await prev_element.select_option(prev_value, timeout=2000)
                log_replay("SELECT", f"with value: {prev_value}")
            except Exception:
                await prev_element.select_option(label=prev_value, timeout=2000)
                log_replay("SELECT", f"with label: {prev_value}")
        else:
            print(f"⚠️ SELECT action has no stored value, hover only")
        
        await asyncio.sleep(CLICK_DELAY)
    
    async def _replay_scroll(self, prev_element):
        """Replay a SCROLL interaction."""
        await prev_element.scroll_into_view_if_needed(timeout=2000)
        await asyncio.sleep(HOVER_DELAY)
        log_replay("SCROLL")
    
    async def _replay_type(self, prev_element, prev_value, type_action_value):
        """Replay a TYPE interaction."""
        # Use stored value if available, otherwise use current type_action_value
        value_to_type = prev_value if prev_value else type_action_value
        await prev_element.fill(value_to_type, timeout=2000)
        await asyncio.sleep(CLICK_DELAY)
        log_replay("TYPE", f"with value: {value_to_type}")
    
    async def _replay_hover(self, prev_element):
        """Replay a HOVER interaction."""
        await prev_element.hover(timeout=2000)
        await asyncio.sleep(HOVER_DELAY)
        log_replay("HOVER")

