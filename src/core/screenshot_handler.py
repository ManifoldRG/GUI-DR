"""
Screenshot Handler - Handles taking and processing screenshots.

Takes screenshots, crops them to include target elements, and handles coordinate conversion.
"""

import os
import asyncio
import traceback
from typing import Dict, Optional, Tuple
from PIL import Image


class ScreenshotHandler:
    """Handles screenshot taking and image processing."""
    
    def __init__(self, page, screenshots_base_dir: str):
        self.page = page
        self.screenshots_base_dir = screenshots_base_dir
    
    async def ensure_viewport_size(self, min_width: int = 1920, min_height: int = 1080):
        """Ensure viewport is at least the specified size."""
        try:
            current_viewport = self.page.viewport_size
            if not current_viewport or current_viewport.get('width', 0) < min_width or current_viewport.get('height', 0) < min_height:
                await self.page.set_viewport_size({"width": min_width, "height": min_height})
                await asyncio.sleep(0.2)
        except Exception:
            await self.page.set_viewport_size({"width": min_width, "height": min_height})
            await asyncio.sleep(0.2)
    
    async def get_page_info(self) -> Dict[str, float]:
        """Get current scroll position and page dimensions."""
        return await self.page.evaluate("""
            () => ({
                scrollX: window.scrollX,
                scrollY: window.scrollY,
                pageWidth: document.documentElement.scrollWidth,
                pageHeight: document.documentElement.scrollHeight
            })
        """)
    
    def calculate_crop_region(self, bounding_box: Tuple[float, float, float, float], page_info: Dict[str, float], 
                               crop_width: int = 1920, crop_height: int = 1080, padding: int = 20) -> Tuple[float, float]:
        """Calculate crop region coordinates to include bounding box with padding.
        
        IMPORTANT: Only adjusts vertically. Horizontal crop always starts at scrollX (or 0 if page is smaller).
        This ensures no horizontal scrolling or cropping - always uses full 1920px width.
        """
        x, y, width, height = bounding_box
        bbox_left = x + page_info['scrollX']
        bbox_top = y + page_info['scrollY']
        bbox_right = bbox_left + width
        bbox_bottom = bbox_top + height
        
        # HORIZONTAL: Always start at scrollX (no horizontal adjustment)
        # If page is smaller than 1920px, start at 0
        crop_left = max(0, page_info['scrollX'])
        
        # VERTICAL: Center crop on bounding box vertically
        bbox_center_y = (bbox_top + bbox_bottom) / 2
        crop_top = bbox_center_y - crop_height / 2
        
        # Adjust vertically if bounding box with padding would be cut off
        if bbox_top - padding < crop_top:
            crop_top = max(0, bbox_top - padding)
        if bbox_bottom + padding > crop_top + crop_height:
            crop_top = max(0, bbox_bottom + padding - crop_height)
        
        return crop_left, crop_top
    
    def crop_and_pad_image(self, img: Image.Image, crop_left: float, crop_top: float, 
                           crop_width: int = 1920, crop_height: int = 1080) -> Tuple[Image.Image, Tuple[int, int], Tuple[float, float]]:
        """Crop image and pad if necessary. Returns (final_image, (paste_x, paste_y), (clamped_crop_left, clamped_crop_top)).
        
        IMPORTANT: Horizontal crop always uses full width (or full page if smaller than crop_width).
        Only vertical crop is adjusted.
        """
        page_width, page_height = img.size
        
        # HORIZONTAL: Always use full page width (or start at 0 if page is smaller than crop_width)
        # No horizontal clamping - we want full width
        clamped_crop_left = max(0, min(crop_left, page_width))  # Don't subtract crop_width here
        # Actual horizontal crop width is min of crop_width and available page width from crop_left
        actual_crop_width = min(crop_width, page_width - int(clamped_crop_left))
        
        # VERTICAL: Clamp crop coordinates to image boundaries
        clamped_crop_top = max(0, min(crop_top, page_height - crop_height))
        actual_crop_height = min(crop_height, page_height - int(clamped_crop_top))
        
        # Crop the image
        crop_left_int = int(clamped_crop_left)
        crop_top_int = int(clamped_crop_top)
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
            # HORIZONTAL: Always paste at x=0 (left-aligned, no centering)
            # This ensures the content starts at the left edge of the 1920px image
            paste_x = 0
            # VERTICAL: Center vertically (only vertical adjustment)
            paste_y = (crop_height - actual_crop_height) // 2 if actual_crop_height < crop_height else 0
            final_img.paste(cropped_img, (paste_x, paste_y))
            cropped_img = final_img
        
        return cropped_img, (paste_x, paste_y), (clamped_crop_left, clamped_crop_top)
    
    async def take_screenshot(self, step_index: int, action: str, bounding_box: Optional[Tuple[float, float, float, float]] = None, 
                             scroll_info: Optional[Dict[str, float]] = None) -> Tuple[str, Optional[Tuple[float, float, float, float]]]:
        """Take screenshot and save it.
        
        If bounding_box is provided (x, y, width, height), takes a full-page screenshot,
        crops it to 1920x1080 to include the entire bounding box, and saves the cropped image.
        Otherwise, takes a full page screenshot.
        
        Args:
            scroll_info: Optional scroll info dict with scrollX and scrollY from when bounding_box was obtained.
                        If not provided, will be fetched before taking screenshot.
        
        Returns:
            Tuple of (filepath, crop_info) where crop_info is (effective_crop_left, effective_crop_top, scrollX, scrollY) 
            if screenshot was cropped, None otherwise. This info can be used to convert 
            coordinates from viewport frame to cropped frame.
        """
        try:
            filename = f"step_{step_index}_{action.lower()}.png"
            filepath = os.path.join(self.screenshots_base_dir, filename)
            
            if bounding_box:
                await self.ensure_viewport_size()
                
                # Use provided scroll_info if available, otherwise get it now
                if scroll_info is None:
                    page_info = await self.get_page_info()
                else:
                    # Get full page info to know page dimensions for horizontal crop
                    full_page_info = await self.get_page_info()
                    # Convert scroll_info dict to page_info format, but keep page dimensions
                    page_info = {
                        'scrollX': scroll_info.get('scrollX', 0),
                        'scrollY': scroll_info.get('scrollY', 0),
                        'pageWidth': full_page_info['pageWidth'],  # Needed to ensure horizontal crop is correct
                        'pageHeight': full_page_info['pageHeight']  # Needed for vertical crop bounds
                    }
                
                # Take full-page screenshot
                temp_filepath = filepath + ".tmp.png"
                await self.page.screenshot(path=temp_filepath, full_page=True)
                
                # Calculate crop region using the page_info (with scroll position from when bbox was obtained)
                crop_left, crop_top = self.calculate_crop_region(bounding_box, page_info)
                
                # Load, crop, and pad image
                # Handle potential decompression bomb error
                try:
                    img = Image.open(temp_filepath)
                except Exception as img_error:
                    # If image is too large or corrupted, try to take a viewport screenshot instead
                    print(f"⚠️  Error opening full-page screenshot (image may be too large): {img_error}")
                    print(f"   Falling back to viewport screenshot...")
                    await self.page.screenshot(path=filepath, full_page=False)
                    if os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                    print(f"📸 Screenshot saved: {filename} (viewport only)")
                    return filepath, None
                
                # Crop and pad - this will clamp crop_left and crop_top to image boundaries
                cropped_img, (paste_x, paste_y), (clamped_crop_left, clamped_crop_top) = self.crop_and_pad_image(img, crop_left, crop_top)
                
                # IMPORTANT: Use the CLAMPED crop_left and crop_top values returned from crop_and_pad_image
                # because those are the actual coordinates where we cropped from
                # Calculate effective crop offset
                # effective_crop_left represents the page coordinate that maps to x=0 in the final cropped image
                # If we crop at clamped_crop_left and paste at paste_x, then:
                #   page_x = clamped_crop_left maps to image_x = paste_x
                #   So: image_x = page_x - clamped_crop_left + paste_x = page_x - (clamped_crop_left - paste_x)
                #   Therefore: effective_crop_left = clamped_crop_left - paste_x
                effective_crop_left = clamped_crop_left - paste_x
                effective_crop_top = clamped_crop_top - paste_y
                
                # Debug: print conversion info
                print(f"  📐 Crop info: original_crop_left={crop_left:.1f}, clamped_crop_left={clamped_crop_left:.1f}, paste_x={paste_x}, effective_crop_left={effective_crop_left:.1f}")
                print(f"  📐 Crop info: original_crop_top={crop_top:.1f}, clamped_crop_top={clamped_crop_top:.1f}, paste_y={paste_y}, effective_crop_top={effective_crop_top:.1f}")
                print(f"  📐 Scroll: scrollX={page_info['scrollX']:.1f}, scrollY={page_info['scrollY']:.1f}")
                
                # Save and clean up
                cropped_img.save(filepath)
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                
                print(f"📸 Screenshot saved: {filename} (1920x1080, cropped to include element)")
                # Return crop info including scroll position for accurate coordinate conversion
                return filepath, (effective_crop_left, effective_crop_top, page_info['scrollX'], page_info['scrollY'])
            else:
                # Fallback to full page screenshot
                await self.page.screenshot(path=filepath, full_page=True)
                print(f"📸 Screenshot saved: {filename} (full page)")
                return filepath, None
        except Exception as e:
            print(f"❌ Error taking screenshot: {e}")
            traceback.print_exc()
            return "", None
    
    async def convert_coordinates_for_crop(self, coordinates: Tuple[int, int], bounding_box: Tuple[float, float, float, float], 
                                          crop_info: Tuple[float, float, float, float]) -> Tuple[Tuple[int, int], Tuple[float, float, float, float]]:
        """Convert coordinates from viewport frame to cropped 1920x1080 frame.
        
        Args:
            coordinates: Viewport-relative center coordinates (x, y)
            bounding_box: Viewport-relative bounding box (x, y, width, height)
            crop_info: Crop info tuple (effective_crop_left, effective_crop_top, scrollX, scrollY) from take_screenshot
        
        Returns:
            Tuple of (converted_coordinates, converted_bounding_box) in cropped image coordinates
        """
        effective_crop_left, effective_crop_top, scroll_x, scroll_y = crop_info
        
        # Convert bounding box from viewport coordinates to page coordinates, then to cropped image coordinates
        x, y, width, height = bounding_box
        # Viewport to page: add scroll offset (from when screenshot was taken)
        bbox_page_x = x + scroll_x
        bbox_page_y = y + scroll_y
        # Page to cropped image: subtract effective crop offset (which accounts for padding)
        # Formula: image_x = page_x - effective_crop_left
        converted_bounding_box = (bbox_page_x - effective_crop_left, bbox_page_y - effective_crop_top, width, height)
        
        # Debug: print conversion details
        print(f"  🔄 Converting bbox: viewport({x:.1f}, {y:.1f}) -> page({bbox_page_x:.1f}, {bbox_page_y:.1f}) -> cropped({bbox_page_x - effective_crop_left:.1f}, {bbox_page_y - effective_crop_top:.1f})")
        
        # Convert center coordinates
        if coordinates:
            # Viewport to page: add scroll offset (from when screenshot was taken)
            coord_page_x = coordinates[0] + scroll_x
            coord_page_y = coordinates[1] + scroll_y
            # Page to cropped image: subtract effective crop offset
            converted_coordinates = (int(coord_page_x - effective_crop_left), int(coord_page_y - effective_crop_top))
        else:
            converted_coordinates = coordinates
        
        return converted_coordinates, converted_bounding_box

