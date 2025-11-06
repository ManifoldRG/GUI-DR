"""
MHTML Processor - Minimal Prototype

Processes MHTML files, injects UI modifications, and extracts element coordinates.
"""

import asyncio
import os
import traceback
from typing import List, Dict, Any, Optional, Tuple, Union
from PIL import Image
from ui.randomization import generate_diverse_ui_params
from ui.injection import generate_injection_js
from exceptions import ElementLocatorError, ElementNotFoundError, AmbiguousMatchError
from locators.element_locator import ElementLocator
from core.action_replay import ActionReplayer

DEBUG = True   


class MHTMLProcessor:
    """Minimal MHTML processor with UI modification support"""
    
    def __init__(self, playwright_page, screenshots_base_dir: str = None, refresh_ui_params_per_step: bool = True, enable_element_reordering: bool = True):
        self.page = playwright_page
        self.screenshots_base_dir = screenshots_base_dir or "screenshots"
        self._refresh_ui_params_per_step = refresh_ui_params_per_step
        self._ui_params_cache = None
        self._enable_element_reordering = enable_element_reordering
        self.page_pre_actions: List[Dict[str, Any]] = []  # Store {element, coordinates, op}
        self.action_replayer = ActionReplayer(self.page)
    
    async def load_mhtml(self, mhtml_path: str) -> bool:
        """Load MHTML file into Playwright page. Clears page state but preserves page_pre_actions.
        
        Returns:
            True if loaded successfully, False otherwise.
        """
        if not os.path.exists(mhtml_path):
            print(f"❌ MHTML file not found: {mhtml_path}")
            return False
        
        # Clear page state by navigating to blank page first
        # This closes any open menus/dropdowns from previous MHTML
        # Note: We DON'T clear page_pre_actions here - those are handled by should_reset_page_pre_actions
        await self.page.goto('about:blank', wait_until='domcontentloaded', timeout=5000)
        await asyncio.sleep(0.1)  # Small delay to ensure page is cleared
        
        abs_path = os.path.abspath(mhtml_path)
        file_url = f"file://{abs_path}"
        
        await self.page.goto(file_url, wait_until='domcontentloaded', timeout=10000)
        await self.page.wait_for_load_state('networkidle')
        
        print(f"✅ Loaded MHTML: {os.path.basename(mhtml_path)}")
        return True
    
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
        print("✅ Random UI modifications injected")
        return params_return

    async def find_element_by_pos_info(
        self, pos_element: Union[str, List[str]], target_element_type: str, target_element_text: str
    ) -> Optional[Dict[str, Any]]:
        """Find element using pos_element information with priority cascade strategy.
        
        Raises:
            ElementLocatorError: If element cannot be found with 100% confidence
            (ElementNotFoundError, AmbiguousMatchError, etc.)
        """
        # Normalize input: if it's a list, use the first element
        if isinstance(pos_element, list):
            if not pos_element:
                raise ElementNotFoundError("Empty pos_element list provided")
            pos_element = pos_element[0]
        
        # ElementLocatorError (including AmbiguousMatchError, ElementNotFoundError) should propagate
        locator = ElementLocator(pos_element, target_element_type, target_element_text)
        element = await locator.find_element(self.page)
        
        bounding_box = await element.bounding_box()
        if not bounding_box:
            raise ElementNotFoundError("Element found but is not visible (no bounding box).")
        
        center_x, center_y = (int(bounding_box['x'] + bounding_box['width'] / 2), int(bounding_box['y'] + bounding_box['height'] / 2))

        return {
            'coordinates': (center_x, center_y),
            'bounding_box': (bounding_box['x'], bounding_box['y'], bounding_box['width'], bounding_box['height']),
            'locator': element,
            'original_box': locator.original_box  # Include for debug highlighting
        }
    
    async def _highlight_element(self, element_locator):
        """Debug helper: Visually highlight the found element on the page."""
        try:
            await element_locator.evaluate("""
                el => {
                    if (el) {
                        el.style.outline = '4px solid #FF0000';
                        el.style.outlineOffset = '2px';
                        el.style.boxShadow = '0 0 10px rgba(255, 0, 0, 0.5)';
                        el.style.zIndex = '999999';
                    }
                }
            """)
        except Exception as e:
            print(f"⚠️ Could not highlight element: {e}")

    async def _highlight_original_box(self, original_box):
        """Debug helper: Visually highlight the original bounding box from pos_candidate."""
        if not original_box:
            return
        
        try:
            await self.page.evaluate("""
                ({x, y, width, height}) => {
                    const existing = document.getElementById('debug-original-box-overlay');
                    if (existing) existing.remove();
                    
                    const overlay = document.createElement('div');
                    overlay.id = 'debug-original-box-overlay';
                    Object.assign(overlay.style, {
                        position: 'fixed',
                        left: x + 'px',
                        top: y + 'px',
                        width: width + 'px',
                        height: height + 'px',
                        border: '3px dashed #00FF00',
                        backgroundColor: 'rgba(0, 255, 0, 0.1)',
                        pointerEvents: 'none',
                        zIndex: '999998',
                        boxSizing: 'border-box'
                    });
                    document.body.appendChild(overlay);
                }
            """, original_box)
        except Exception as e:
            print(f"⚠️ Could not highlight original box: {e}")

    async def _ensure_viewport_size(self, min_width: int = 1920, min_height: int = 1080):
        """Ensure viewport is at least the specified size."""
        try:
            current_viewport = self.page.viewport_size
            if not current_viewport or current_viewport.get('width', 0) < min_width or current_viewport.get('height', 0) < min_height:
                await self.page.set_viewport_size({"width": min_width, "height": min_height})
                await asyncio.sleep(0.2)
        except Exception:
            await self.page.set_viewport_size({"width": min_width, "height": min_height})
            await asyncio.sleep(0.2)
    
    async def _get_page_info(self) -> Dict[str, float]:
        """Get current scroll position and page dimensions."""
        return await self.page.evaluate("""
            () => ({
                scrollX: window.scrollX,
                scrollY: window.scrollY,
                pageWidth: document.documentElement.scrollWidth,
                pageHeight: document.documentElement.scrollHeight
            })
        """)
    
    def _calculate_crop_region(self, bounding_box: Tuple[float, float, float, float], page_info: Dict[str, float], 
                               crop_width: int = 1920, crop_height: int = 1080, padding: int = 20) -> Tuple[float, float]:
        """Calculate crop region coordinates to include bounding box with padding."""
        x, y, width, height = bounding_box
        bbox_left = x + page_info['scrollX']
        bbox_top = y + page_info['scrollY']
        bbox_right = bbox_left + width
        bbox_bottom = bbox_top + height
        
        # Calculate crop region center to include bounding box with padding
        bbox_center_x = (bbox_left + bbox_right) / 2
        bbox_center_y = (bbox_top + bbox_bottom) / 2
        
        # Start with crop centered on bounding box
        crop_left = bbox_center_x - crop_width / 2
        crop_top = bbox_center_y - crop_height / 2
        
        # Adjust if bounding box with padding would be cut off
        if bbox_left - padding < crop_left:
            crop_left = max(0, bbox_left - padding)
        if bbox_right + padding > crop_left + crop_width:
            crop_left = max(0, bbox_right + padding - crop_width)
        
        if bbox_top - padding < crop_top:
            crop_top = max(0, bbox_top - padding)
        if bbox_bottom + padding > crop_top + crop_height:
            crop_top = max(0, bbox_bottom + padding - crop_height)
        
        return crop_left, crop_top
    
    def _crop_and_pad_image(self, img: Image.Image, crop_left: float, crop_top: float, 
                           crop_width: int = 1920, crop_height: int = 1080) -> Tuple[Image.Image, Tuple[int, int]]:
        """Crop image and pad if necessary. Returns (final_image, (paste_x, paste_y))."""
        page_width, page_height = img.size
        
        # Clamp crop coordinates to image boundaries
        crop_left = max(0, min(crop_left, page_width - crop_width))
        crop_top = max(0, min(crop_top, page_height - crop_height))
        
        # Calculate actual crop dimensions
        actual_crop_width = min(crop_width, page_width - int(crop_left))
        actual_crop_height = min(crop_height, page_height - int(crop_top))
        
        # Crop the image
        crop_left_int = int(crop_left)
        crop_top_int = int(crop_top)
        cropped_img = img.crop((
            crop_left_int,
            crop_top_int,
            crop_left_int + actual_crop_width,
            crop_top_int + actual_crop_height
        ))
        
        # Pad if necessary
        paste_x, paste_y = 0, 0
        if actual_crop_width < crop_width or actual_crop_height < crop_height:
            final_img = Image.new('RGB', (crop_width, crop_height), color='white')
            paste_x = (crop_width - actual_crop_width) // 2 if actual_crop_width < crop_width else 0
            paste_y = (crop_height - actual_crop_height) // 2 if actual_crop_height < crop_height else 0
            final_img.paste(cropped_img, (paste_x, paste_y))
            cropped_img = final_img
        
        return cropped_img, (paste_x, paste_y)
    
    async def take_screenshot(self, step_index: int, action: str, bounding_box: Optional[Tuple[float, float, float, float]] = None) -> Tuple[str, Optional[Tuple[float, float]]]:
        """Take screenshot and save it.
        
        If bounding_box is provided (x, y, width, height), takes a full-page screenshot,
        crops it to 1920x1080 to include the entire bounding box, and saves the cropped image.
        Otherwise, takes a full page screenshot.
        
        Returns:
            Tuple of (filepath, crop_offset) where crop_offset is (crop_left, crop_top) 
            if screenshot was cropped, None otherwise. This offset can be used to convert 
            coordinates from full-page frame to cropped frame.
        """
        try:
            filename = f"step_{step_index}_{action.lower()}.png"
            filepath = os.path.join(self.screenshots_base_dir, filename)
            
            if bounding_box:
                await self._ensure_viewport_size()
                
                # Take full-page screenshot
                temp_filepath = filepath + ".tmp.png"
                await self.page.screenshot(path=temp_filepath, full_page=True)
                
                # Get page info and calculate crop region
                page_info = await self._get_page_info()
                crop_left, crop_top = self._calculate_crop_region(bounding_box, page_info)
                
                # Load, crop, and pad image
                img = Image.open(temp_filepath)
                cropped_img, (paste_x, paste_y) = self._crop_and_pad_image(img, crop_left, crop_top)
                
                # Calculate effective crop offset
                effective_crop_left = crop_left - paste_x
                effective_crop_top = crop_top - paste_y
                
                # Save and clean up
                cropped_img.save(filepath)
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                
                print(f"📸 Screenshot saved: {filename} (1920x1080, cropped to include element)")
                return filepath, (effective_crop_left, effective_crop_top)
            else:
                # Fallback to full page screenshot
                await self.page.screenshot(path=filepath, full_page=True)
                print(f"📸 Screenshot saved: {filename} (full page)")
                return filepath, None
        except Exception as e:
            print(f"❌ Error taking screenshot: {e}")
            traceback.print_exc()
            return "", None
    
    async def _prepare_action_context(self, should_reset_page_pre_actions: bool, type_action_value: str, should_randomize: bool) -> Dict[str, Any]:
        """Prepare action context: reset pre-actions, replay previous actions, inject UI modifications."""
        if should_reset_page_pre_actions:
            self.page_pre_actions = []
        
        await self.action_replayer.replay_actions(self.page_pre_actions, type_action_value)
        
        if should_randomize:
            return await self.inject_ui_modifications()
        return {}
    
    async def _find_and_prepare_element(self, pos_candidate: str, target_element_type: str, target_element_text: str, action_op: str):
        """Find element and handle special cases (e.g., label -> input for checkbox/radio)."""
        print(f"Finding element by pos_candidate: {pos_candidate}")
        element_info = await self.find_element_by_pos_info(pos_candidate, target_element_type, target_element_text)
        
        element = element_info.get('locator')
        
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
                    print(f"  📌 Using input checkbox/radio instead of label")
        
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
    
    def _store_action_state(self, element, coordinates: Tuple[int, int], action_op: str, type_action_value: str):
        """Store element info for next step."""
        if element and coordinates:
            stored_value = None
            if action_op.upper() == 'SELECT' or action_op.upper().startswith('TYPE'):
                stored_value = type_action_value if type_action_value else None
            
            self.page_pre_actions.append({
                'element': element,
                'coordinates': coordinates,
                'op': action_op,
                'value': stored_value,
            })
    
    async def _convert_coordinates_for_crop(self, coordinates: Tuple[int, int], bounding_box: Tuple[float, float, float, float], 
                                          crop_offset: Tuple[float, float]) -> Tuple[Tuple[int, int], Tuple[float, float, float, float]]:
        """Convert coordinates from full-page frame to cropped 1920x1080 frame."""
        crop_left, crop_top = crop_offset
        scroll_info = await self.page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")
        
        # Convert bounding box
        x, y, width, height = bounding_box
        bbox_page_x = x + scroll_info['scrollX']
        bbox_page_y = y + scroll_info['scrollY']
        converted_bounding_box = (bbox_page_x - crop_left, bbox_page_y - crop_top, width, height)
        
        # Convert center coordinates
        if coordinates:
            coord_page_x = coordinates[0] + scroll_info['scrollX']
            coord_page_y = coordinates[1] + scroll_info['scrollY']
            converted_coordinates = (int(coord_page_x - crop_left), int(coord_page_y - crop_top))
        else:
            converted_coordinates = coordinates
        
        return converted_coordinates, converted_bounding_box
    
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
        print(f"\n🎬 Processing action: {action_uid} ({action_op})")
        
        # Prepare context: reset, replay, inject UI
        ui_params = await self._prepare_action_context(should_reset_page_pre_actions, type_action_value, should_randomize)
        
        # Find and prepare element
        element, element_info = await self._find_and_prepare_element(pos_candidate, target_element_type, target_element_text, action_op)
        
        # Get coordinates
        coordinates, bounding_box = await self._get_element_coordinates(element, element_info)
        print(f"Found element at coordinates: {coordinates} with bounding box: {bounding_box}")
        
        # Store action state for next step
        self._store_action_state(element, coordinates, action_op, type_action_value)
        
        # Take screenshot
        await asyncio.sleep(0.2)
        screenshot_path, crop_offset = await self.take_screenshot(step_index, action_op, bounding_box)
        
        # Convert coordinates if screenshot was cropped
        converted_coordinates = coordinates
        converted_bounding_box = bounding_box
        if crop_offset is not None and bounding_box is not None:
            converted_coordinates, converted_bounding_box = await self._convert_coordinates_for_crop(
                coordinates, bounding_box, crop_offset
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