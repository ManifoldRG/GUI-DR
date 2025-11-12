"""
Text Density Measurement - Measures text density in viewport and crop regions.
"""

import asyncio
import os
from typing import Dict, Optional, Tuple


async def _visualize_crop_region(page, crop_left: float, crop_top: float, crop_right: float, crop_bottom: float, scroll_x: float, scroll_y: float):
    """Visualize the crop region on the page for debugging."""
    await page.evaluate("""
        ({cropLeft, cropTop, cropRight, cropBottom, scrollX, scrollY}) => {
            // Remove existing visualization
            const existing = document.getElementById('debug-text-density-region');
            if (existing) existing.remove();
            
            // Convert page coordinates to viewport coordinates for visualization
            const viewportLeft = cropLeft - scrollX;
            const viewportTop = cropTop - scrollY;
            const viewportRight = cropRight - scrollX;
            const viewportBottom = cropBottom - scrollY;
            const viewportWidth = viewportRight - viewportLeft;
            const viewportHeight = viewportBottom - viewportTop;
            
            const overlay = document.createElement('div');
            overlay.id = 'debug-text-density-region';
            Object.assign(overlay.style, {
                position: 'fixed',  // Fixed to viewport
                left: viewportLeft + 'px',
                top: viewportTop + 'px',
                width: viewportWidth + 'px',
                height: viewportHeight + 'px',
                border: '4px dashed #FFA500',  // Orange dashed border
                backgroundColor: 'rgba(255, 165, 0, 0.1)',  // Light orange fill
                pointerEvents: 'none',
                zIndex: '999997',
                boxSizing: 'border-box',
                boxShadow: '0 0 20px rgba(255, 165, 0, 0.5)'
            });
            
            // Add label
            const label = document.createElement('div');
            label.textContent = 'Text Density Region';
            Object.assign(label.style, {
                position: 'absolute',
                top: '-25px',
                left: '0',
                color: '#FFA500',
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                padding: '2px 6px',
                fontSize: '12px',
                fontWeight: 'bold',
                whiteSpace: 'nowrap',
                pointerEvents: 'none'
            });
            overlay.appendChild(label);
            
            document.body.appendChild(overlay);
        }
    """, {
        'cropLeft': crop_left,
        'cropTop': crop_top,
        'cropRight': crop_right,
        'cropBottom': crop_bottom,
        'scrollX': scroll_x,
        'scrollY': scroll_y
    })


async def measure_viewport_text_density(page) -> Dict[str, float]:
    """Measure text density in the current viewport.
    
    Returns:
        Dictionary with:
        - word_count: Number of words in viewport
        - character_count: Number of characters in viewport
        - text_elements_count: Number of text-containing elements
        - viewport_width: Viewport width
        - viewport_height: Viewport height
        - words_per_pixel: Density metric
    """
    result = await page.evaluate("""
        () => {
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
            
            // Get all text nodes in viewport
            const textNodes = [];
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            
            let node;
            while (node = walker.nextNode()) {
                const text = node.textContent.trim();
                if (text.length > 0) {
                    // Check if parent element is visible and in viewport
                    const parent = node.parentElement;
                    if (parent) {
                        const rect = parent.getBoundingClientRect();
                        const style = window.getComputedStyle(parent);
                        
                        // Check if element is visible and in viewport
                        if (style.display !== 'none' && 
                            style.visibility !== 'hidden' &&
                            style.opacity !== '0' &&
                            rect.width > 0 && rect.height > 0 &&
                            rect.top < viewportHeight &&
                            rect.bottom > 0 &&
                            rect.left < viewportWidth &&
                            rect.right > 0) {
                            textNodes.push({
                                text: text,
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height
                            });
                        }
                    }
                }
            }
            
            // Count words and characters
            let wordCount = 0;
            let characterCount = 0;
            const textElements = new Set();
            
            textNodes.forEach(node => {
                const words = node.text.split(/\\s+/).filter(w => w.length > 0);
                wordCount += words.length;
                characterCount += node.text.length;
                textElements.add(node.text.substring(0, 50)); // Use first 50 chars as element identifier
            });
            
            const viewportArea = viewportWidth * viewportHeight;
            const wordsPerPixel = viewportArea > 0 ? wordCount / viewportArea : 0;
            
            return {
                word_count: wordCount,
                character_count: characterCount,
                text_elements_count: textElements.size,
                viewport_width: viewportWidth,
                viewport_height: viewportHeight,
                viewport_area: viewportArea,
                words_per_pixel: wordsPerPixel,
                words_per_1000_pixels: wordsPerPixel * 1000
            };
        }
    """)
    
    return result


async def measure_crop_text_density(
    page, 
    crop_info: Tuple[float, float, float, float],
    bounding_box: Optional[Tuple[float, float, float, float]] = None
) -> Dict[str, float]:
    """Measure text density in the crop region.
    
    Args:
        page: Playwright page object
        crop_info: Tuple of (effective_crop_left, effective_crop_top, scrollX, scrollY)
        bounding_box: Optional bounding box (x, y, width, height) in viewport coordinates
    
    Returns:
        Dictionary with text density metrics for the crop region
    """
    effective_crop_left, effective_crop_top, scroll_x, scroll_y = crop_info
    crop_width = 1920
    crop_height = 1080
    
    # The effective_crop_left/top are in page coordinates and represent where the crop starts
    # in the final 1920x1080 image. However, we need to account for:
    # 1. The actual crop might have been clamped to page boundaries
    # 2. The crop might have padding (paste_x, paste_y) if the page was smaller than 1920x1080
    
    # Get current page dimensions and scroll position
    # Note: scroll position might have changed since screenshot was taken, but we use scroll_x/scroll_y from crop_info
    page_info = await page.evaluate("""
        () => ({
            pageWidth: document.documentElement.scrollWidth,
            pageHeight: document.documentElement.scrollHeight
        })
    """)
    
    # Calculate actual crop bounds in page coordinates
    # effective_crop_left is the page coordinate that maps to x=0 in the final 1920x1080 image
    # This already accounts for paste_x/paste_y offsets from padding
    # 
    # IMPORTANT: With vertical-only adjustment, effective_crop_left should be scrollX (or 0 if page < 1920px)
    # The crop region in page coordinates:
    crop_left_page = effective_crop_left
    crop_top_page = effective_crop_top
    crop_right_page = crop_left_page + crop_width  # Always 1920px width (or padded)
    crop_bottom_page = crop_top_page + crop_height  # Always 1080px height (or padded)
    
    # Clamp to actual page bounds (same as screenshot handler does in crop_and_pad_image)
    # This ensures we don't try to measure outside the actual page
    # Horizontal: crop_left_page should be at scrollX (or 0), so clamp right edge
    crop_left_page = max(0, min(crop_left_page, page_info['pageWidth']))
    crop_top_page = max(0, min(crop_top_page, page_info['pageHeight']))
    crop_right_page = min(crop_right_page, page_info['pageWidth'])
    crop_bottom_page = min(crop_bottom_page, page_info['pageHeight'])
    
    # IMPORTANT: Restore scroll position to match when screenshot was taken
    # This ensures getBoundingClientRect() returns correct viewport-relative coordinates
    await page.evaluate(f"window.scrollTo({scroll_x}, {scroll_y})")
    await asyncio.sleep(0.1)  # Small delay for scroll to complete
    
    # Add debug visualization of crop region (if DEBUG mode)
    if os.environ.get('DEBUG', 'False').lower() == 'true':
        await _visualize_crop_region(page, crop_left_page, crop_top_page, crop_right_page, crop_bottom_page, scroll_x, scroll_y)
    
    result = await page.evaluate("""
        (cropBounds) => {
            const { cropLeft, cropTop, cropRight, cropBottom, scrollX, scrollY } = cropBounds;
            
            // Get all text nodes
            const textNodes = [];
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            
            let node;
            while (node = walker.nextNode()) {
                const text = node.textContent.trim();
                if (text.length > 0) {
                    const parent = node.parentElement;
                    if (parent) {
                        const rect = parent.getBoundingClientRect();
                        const style = window.getComputedStyle(parent);
                        
                        // Convert viewport coordinates to page coordinates
                        // Since we restored scroll position, window.scrollX/Y should match cropBounds.scrollX/Y
                        // But use cropBounds values to be safe
                        const pageX = rect.left + scrollX;
                        const pageY = rect.top + scrollY;
                        const pageRight = rect.right + scrollX;
                        const pageBottom = rect.bottom + scrollY;
                        
                        // Check if element is visible and intersects crop region
                        if (style.display !== 'none' && 
                            style.visibility !== 'hidden' &&
                            style.opacity !== '0' &&
                            rect.width > 0 && rect.height > 0 &&
                            pageRight > cropLeft &&
                            pageX < cropRight &&
                            pageBottom > cropTop &&
                            pageY < cropBottom) {
                            
                            // Calculate intersection area
                            const intersectLeft = Math.max(pageX, cropLeft);
                            const intersectTop = Math.max(pageY, cropTop);
                            const intersectRight = Math.min(pageRight, cropRight);
                            const intersectBottom = Math.min(pageBottom, cropBottom);
                            const intersectWidth = Math.max(0, intersectRight - intersectLeft);
                            const intersectHeight = Math.max(0, intersectBottom - intersectTop);
                            const intersectArea = intersectWidth * intersectHeight;
                            const elementArea = rect.width * rect.height;
                            const coverageRatio = elementArea > 0 ? intersectArea / elementArea : 0;
                            
                            // Only count if significant portion is in crop region
                            if (coverageRatio > 0.1) {
                                textNodes.push({
                                    text: text,
                                    coverage: coverageRatio
                                });
                            }
                        }
                    }
                }
            }
            
            // Count words and characters (weighted by coverage)
            let wordCount = 0;
            let characterCount = 0;
            const textElements = new Set();
            
            textNodes.forEach(node => {
                const words = node.text.split(/\\s+/).filter(w => w.length > 0);
                const weightedWordCount = Math.round(words.length * node.coverage);
                const weightedCharCount = Math.round(node.text.length * node.coverage);
                
                wordCount += weightedWordCount;
                characterCount += weightedCharCount;
                textElements.add(node.text.substring(0, 50));
            });
            
            const cropArea = 1920 * 1080; // Fixed crop size
            const wordsPerPixel = cropArea > 0 ? wordCount / cropArea : 0;
            
            return {
                word_count: wordCount,
                character_count: characterCount,
                text_elements_count: textElements.size,
                crop_width: 1920,
                crop_height: 1080,
                crop_area: cropArea,
                words_per_pixel: wordsPerPixel,
                words_per_1000_pixels: wordsPerPixel * 1000
            };
        }
    """, {
        'cropLeft': crop_left_page,
        'cropTop': crop_top_page,
        'cropRight': crop_right_page,
        'cropBottom': crop_bottom_page,
        'scrollX': scroll_x,  # Use scroll position from when screenshot was taken
        'scrollY': scroll_y
    })
    
    return result

