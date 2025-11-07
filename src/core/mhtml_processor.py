"""
MHTML Processor - Minimal Prototype

Processes MHTML files, injects UI modifications, and extracts element coordinates.
"""

import asyncio
import os
import traceback
from typing import List, Dict, Any, Optional, Tuple, Union
from PIL import Image
from loguru import logger
from ui.randomization import generate_diverse_ui_params
from ui.injection import generate_injection_js
from exceptions import ElementLocatorError, ElementNotFoundError, AmbiguousMatchError, ElementValidationError
from locators.element_locator import ElementLocator
from core.action_replay import ActionReplayer
from core.element_validator import ElementValidator
from core.element_type_resolver import ElementTypeResolver
from core.element_scroller import ElementScroller
from core.screenshot_handler import ScreenshotHandler
from core.element_highlighter import ElementHighlighter

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Increase PIL image size limit to handle large screenshots
# Default limit is ~178M pixels, we'll set it to 500M pixels
Image.MAX_IMAGE_PIXELS = 500_000_000   


class MHTMLProcessor:
    """Minimal MHTML processor with UI modification support"""
    
    def __init__(self, playwright_page, screenshots_base_dir: str = None, refresh_ui_params_per_step: bool = True, enable_element_reordering: bool = True):
        self.page = playwright_page
        self.screenshots_base_dir = screenshots_base_dir or "screenshots"
        self._refresh_ui_params_per_step = refresh_ui_params_per_step
        self._ui_params_cache = None
        self._enable_element_reordering = enable_element_reordering
        self.page_pre_actions: List[Dict[str, Any]] = []  # Store {pos_candidate, target_element_type, target_element_text, coordinates, op}
        
        # Initialize helper classes
        self.action_replayer = ActionReplayer(self.page, find_element_func=self.find_element_by_pos_info)
        self.element_validator = ElementValidator(self.page)
        self.element_type_resolver = ElementTypeResolver(self.page)
        self.element_scroller = ElementScroller(self.page)
        self.screenshot_handler = ScreenshotHandler(self.page, self.screenshots_base_dir)
        self.element_highlighter = ElementHighlighter(self.page)
    
    async def load_mhtml(self, mhtml_path: str) -> bool:
        """Load MHTML file into Playwright page. Clears page state but preserves page_pre_actions.
        
        Returns:
            True if loaded successfully, False otherwise.
        """
        if not os.path.exists(mhtml_path):
            logger.error(f"MHTML file not found: {mhtml_path}")
            return False
        
        try:
            # Clear page state by navigating to blank page first
            # This closes any open menus/dropdowns from previous MHTML
            # Note: We DON'T clear page_pre_actions here - those are handled by should_reset_page_pre_actions
            await self.page.goto('about:blank', wait_until='domcontentloaded', timeout=5000)
            await asyncio.sleep(0.1)  # Small delay to ensure page is cleared
            
            abs_path = os.path.abspath(mhtml_path)
            file_url = f"file://{abs_path}"
            
            await self.page.goto(file_url, wait_until='domcontentloaded', timeout=10000)
            # Use timeout for networkidle to prevent hanging
            try:
                await asyncio.wait_for(
                    self.page.wait_for_load_state('networkidle'),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.warning("Network idle timeout, continuing anyway...")
                # Continue even if networkidle times out
            
            logger.info(f"✅ Loaded MHTML: {os.path.basename(mhtml_path)}")
            return True
        except Exception as e:
            logger.error(f"Error loading MHTML {mhtml_path}: {e}")
            traceback.print_exc()
            return False
    
    def _generate_ui_params(self) -> Dict[str, Any]:
        """Generate random UI modification parameters using diverse design styles with WCAG contrast compliance."""
        return generate_diverse_ui_params()
    
    def set_refresh_ui_params_per_step(self, refresh: bool):
        """Set whether to refresh UI parameters at each step or reuse cached values for trajectory."""
        self._refresh_ui_params_per_step = refresh
        if refresh:
            self._ui_params_cache = None  # Clear cache when enabling per-step refresh
    
    def reset_ui_params_cache(self):
        """Reset the cached UI parameters (useful when starting a new trajectory)."""
        self._ui_params_cache = None
    
    def set_enable_element_reordering(self, enable: bool):
        """Set whether to reorder DOM elements (buttons, links) in the same container.
        
        Args:
            enable: If True, elements will be reordered unless they are intentionally 
                   alphabetically ordered. If False, elements keep their original order.
        """
        self._enable_element_reordering = enable
    
    async def inject_ui_modifications(self) -> Dict[str, Any]:
        """Inject random UI modifications: colors, fonts, styles, and reorder DOM elements.
        
        Returns:
            The parameters used for UI modifications.
        """
        # Use cached params if refresh_per_step is False, otherwise generate new ones
        if self._refresh_ui_params_per_step or self._ui_params_cache is None:
            params = self._generate_ui_params()
            self._ui_params_cache = params
        else:
            params = self._ui_params_cache
        
        # Make a copy of params for return
        params_return = params.copy()
        
        # Add reordering flag to params
        params_with_reorder = params.copy()
        params_with_reorder['enableElementReordering'] = self._enable_element_reordering
        
        # Generate JavaScript injection code based on design style
        injection_js = generate_injection_js(params)
        
        # Execute the generated JavaScript
        await self.page.evaluate(injection_js, params_with_reorder)
        logger.info("✅ Random UI modifications injected")
        return params_return

    async def find_element_by_pos_info(
        self, pos_element: Union[str, List[str]], target_element_type: str, target_element_text: str
    ) -> Optional[Dict[str, Any]]:
        """Find element using pos_element information with priority cascade strategy.
        
        Raises:
            ElementLocatorError: If element cannot be found with 100% confidence
            (ElementNotFoundError, AmbiguousMatchError, ElementValidationError)
        """
        # Normalize input: if it's a list, use the first element
        if isinstance(pos_element, list):
            if not pos_element:
                raise ElementNotFoundError("Empty pos_element list provided")
            pos_element = pos_element[0]
        
        # ElementLocatorError (including AmbiguousMatchError, ElementNotFoundError) should propagate
        locator = ElementLocator(pos_element, target_element_type, target_element_text)
        element = await locator.find_element(self.page)
        
        # Scroll element into view, especially important for elements in scrollable containers (dropdowns)
        await self.element_scroller.ensure_element_visible(element)
        
        bounding_box = await element.bounding_box()
        if not bounding_box:
            raise ElementValidationError("Element found but is not visible (no bounding box) after scrolling.")
        
        # STRICT VALIDATION: Verify bounding box is reasonable and in viewport
        await self.element_validator.validate_bounding_box(bounding_box)
        
        center_x, center_y = (int(bounding_box['x'] + bounding_box['width'] / 2), int(bounding_box['y'] + bounding_box['height'] / 2))

        return {
            'coordinates': (center_x, center_y),
            'bounding_box': (bounding_box['x'], bounding_box['y'], bounding_box['width'], bounding_box['height']),
            'locator': element,
            'original_box': locator.original_box  # Include for debug highlighting
        }
    
    async def _prepare_action_context(self, should_reset_page_pre_actions: bool, type_action_value: str, should_randomize: bool) -> Dict[str, Any]:
        """Prepare action context: reset pre-actions, replay previous actions, inject UI modifications."""
        if should_reset_page_pre_actions:
            self.page_pre_actions = []
        
        # Replay actions to restore dynamic states (e.g., open menus)
        # This should be fast (< 2 seconds) if elements exist, otherwise we skip gracefully
        try:
            await self.action_replayer.replay_actions(self.page_pre_actions, type_action_value)
        except Exception as replay_error:
            logger.warning(f"Error during action replay: {replay_error}")
            # Continue processing even if replay fails - the MHTML might already have the state we need
        
        if should_randomize:
            return await self.inject_ui_modifications()
        return {}
    
    async def _find_and_prepare_element(self, pos_candidate: str, target_element_type: str, target_element_text: str, action_op: str):
        """Find element and handle special cases (e.g., label -> input for checkbox/radio).
        
        Also handles finding parent elements when child elements are found (e.g., span inside link).
        """
        logger.info(f"Finding element by pos_candidate: {pos_candidate}")
        element_info = await self.find_element_by_pos_info(pos_candidate, target_element_type, target_element_text)
        
        element = element_info.get('locator')
        
        # Handle finding parent elements when child elements are found
        element = await self.element_type_resolver.ensure_correct_element_type(element, target_element_type)
        
        # For label elements with checkbox/radio, find the actual input for better coordinates
        if element and action_op.upper() == 'CLICK':
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            if tag_name == 'label':
                label_for = await element.get_attribute('for')
                input_element = None
                
                if label_for:
                    input_element = self.page.locator(f"#{label_for}")
                    if await input_element.count() == 0:
                        input_element = None
                else:
                    input_element = element.locator("input[type='checkbox'], input[type='radio']")
                    if await input_element.count() == 0:
                        input_element = None
                
                if input_element:
                    element = input_element
                    logger.info("  📌 Using input checkbox/radio instead of label")
        
        # STRICT VALIDATION: Verify element matches expected type and text after all adjustments
        await self.element_validator.validate_element(element, target_element_type, target_element_text)
        
        # STRICT VALIDATION: Verify element is still valid and visible after scrolling
        await self.element_validator.validate_after_scroll(element, target_element_type, target_element_text)
        
        return element, element_info
    
    async def _get_element_coordinates(self, element, element_info: Dict[str, Any]) -> Tuple[Tuple[int, int], Tuple[float, float, float, float]]:
        """Get coordinates and bounding box from element."""
        bbox = await element.bounding_box()
        if bbox:
            coordinates = (int(bbox['x'] + bbox['width'] / 2), int(bbox['y'] + bbox['height'] / 2))
            bounding_box = (bbox['x'], bbox['y'], bbox['width'], bbox['height'])
        else:
            coordinates = element_info.get('coordinates')
            bounding_box = element_info.get('bounding_box')
        
        return coordinates, bounding_box
    
    def _store_action_state(self, pos_candidate: str, target_element_type: str, target_element_text: str, 
                           coordinates: Tuple[int, int], action_op: str, type_action_value: str):
        """Store element info for next step.
        
        We store pos_candidate, target_element_type, and target_element_text instead of the element locator
        because element locators become invalid when we load a new MHTML file. We'll re-find the element
        using this information when replaying actions.
        """
        if coordinates:
            stored_value = None
            if action_op.upper() == 'SELECT' or action_op.upper().startswith('TYPE'):
                stored_value = type_action_value if type_action_value else None
            
            self.page_pre_actions.append({
                'pos_candidate': pos_candidate,
                'target_element_type': target_element_type,
                'target_element_text': target_element_text,
                'coordinates': coordinates,
                'op': action_op,
                'value': stored_value,
            })
    
    async def process_action(
        self,
        action_uid: str,
        action_op: str,
        type_action_value: str,
        pos_candidate: str,
        target_element_type: str,
        target_element_text: str,
        step_index: int = None,
        should_reset_page_pre_actions: bool = False,
        should_randomize: bool = True
    ) -> Dict[str, Any]:
        """Process a single action entry"""
        logger.info(f"\n🎬 Processing action: {action_uid} ({action_op})")
        
        try:
            # Prepare context: reset, replay, inject UI
            ui_params = await self._prepare_action_context(should_reset_page_pre_actions, type_action_value, should_randomize)
            
            # Find and prepare element
            element, element_info = await self._find_and_prepare_element(pos_candidate, target_element_type, target_element_text, action_op)
            
            # Get coordinates
            coordinates, bounding_box = await self._get_element_coordinates(element, element_info)
            logger.info(f"Found element at coordinates: {coordinates} with bounding box: {bounding_box}")
            
            # Get scroll position at the SAME time as bounding box to ensure consistency
            scroll_info_at_bbox = await self.page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")
            
            # Debug visualization: highlight found element and original bounding box
            if DEBUG:
                original_box = element_info.get('original_box')
                if original_box:
                    await self.element_highlighter.highlight_original_box(original_box)
                if element:
                    await self.element_highlighter.highlight_element(element)
                # Add a small delay so the highlights are visible
                await asyncio.sleep(0.3)
            
            # Store action state for next step (store info to re-find element, not the element itself)
            self._store_action_state(pos_candidate, target_element_type, target_element_text, 
                                    coordinates, action_op, type_action_value)
            
            # Take screenshot - pass scroll info to ensure consistency
            await asyncio.sleep(0.2)
            screenshot_path, crop_info = await self.screenshot_handler.take_screenshot(
                step_index, action_op, bounding_box, scroll_info_at_bbox
            )
            
            # Convert coordinates if screenshot was cropped
            converted_coordinates = coordinates
            converted_bounding_box = bounding_box
            if crop_info is not None and bounding_box is not None:
                converted_coordinates, converted_bounding_box = await self.screenshot_handler.convert_coordinates_for_crop(
                    coordinates, bounding_box, crop_info
                )

            return {
                'action_uid': action_uid,
                'op': action_op,
                'augmentation_success': True,
                'coordinates': converted_coordinates,
                'bounding_box': converted_bounding_box,
                'screenshot': screenshot_path,
                'ui_params': ui_params
            }
        except Exception as e:
            logger.error(f"Error in process_action: {e}")
            traceback.print_exc()
            raise
