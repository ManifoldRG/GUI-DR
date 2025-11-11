"""
Element Analyzer - Analyzes page elements to prepare LLM text generation for Type 2.
"""
from typing import Dict, List, Tuple, Optional
from loguru import logger


async def analyze_page_elements(page) -> Dict[str, List[str]]:
    """Analyze page to extract element groups for LLM text generation.
    
    Args:
        page: Playwright page object
    
    Returns:
        Dictionary mapping group IDs to lists of element texts
    """
    try:
        result = await page.evaluate("""
            () => {
                const groups = {};
                const interactiveSelectors = 'button, input[type="button"], input[type="submit"], a[href], li';
                const allElements = Array.from(document.querySelectorAll(interactiveSelectors));
                
                function findSemanticContainer(el) {
                    const semanticTags = ['NAV', 'HEADER', 'SECTION', 'ARTICLE', 'ASIDE', 'MAIN', 'FOOTER', 'UL', 'OL'];
                    const classPatterns = ['menu', 'navbar', 'nav', 'card', 'list', 'item', 'group', 'container', 'bar'];
                    
                    let current = el.parentElement;
                    while (current && current !== document.body && current !== document.documentElement) {
                        if (semanticTags.includes(current.tagName)) {
                            return current;
                        }
                        const classList = Array.from(current.classList || []);
                        if (classList.some(cls => classPatterns.some(pattern => cls.toLowerCase().includes(pattern)))) {
                            return current;
                        }
                        current = current.parentElement;
                    }
                    return el.parentElement || null;
                }
                
                const byContainer = new Map();
                allElements.forEach(el => {
                    const container = findSemanticContainer(el);
                    if (container && container !== document.body) {
                        if (!byContainer.has(container)) {
                            byContainer.set(container, []);
                        }
                        byContainer.get(container).push(el);
                    }
                });
                
                byContainer.forEach((elements, container) => {
                    if (elements.length < 2) return;
                    
                    // Generate group ID
                    const groupId = Array.from(elements)
                        .map(el => el.tagName + (el.textContent || '').substring(0, 10))
                        .join('_')
                        .replace(/[^a-zA-Z0-9_]/g, '')
                        .substring(0, 50);
                    
                    // Extract texts
                    const texts = elements
                        .map(el => {
                            if (el.tagName === 'INPUT' && el.type === 'button') {
                                return el.value || '';
                            }
                            return (el.textContent || '').trim();
                        })
                        .filter(text => text.length > 0);
                    
                    if (texts.length > 0) {
                        groups[groupId] = texts;
                    }
                });
                
                return groups;
            }
        """)
        
        return result or {}
        
    except Exception as e:
        logger.warning(f"Failed to analyze page elements: {e}")
        return {}


def generate_llm_texts_for_groups(
    groups: Dict[str, List[str]],
    text_generator,
    num_clones_per_group: int = 2
) -> Dict[str, List[str]]:
    """Generate LLM texts for element groups.
    
    Args:
        groups: Dictionary mapping group IDs to element texts
        text_generator: TextGenerator instance
        num_clones_per_group: Number of clone texts to generate per group
    
    Returns:
        Dictionary mapping group IDs to LLM-generated texts
    """
    llm_texts = {}
    
    for group_id, element_texts in groups.items():
        if not element_texts:
            continue
        
        try:
            # Determine element type from first element
            element_type = "element"
            if any("button" in text.lower() for text in element_texts[:3]):
                element_type = "button"
            elif any("link" in text.lower() or len(text) < 15 for text in element_texts[:3]):
                element_type = "link"
            elif any(len(text) > 30 for text in element_texts[:3]):
                element_type = "list item"
            
            # Generate texts
            generated = text_generator.generate_clone_texts(
                element_texts=element_texts,
                num_clones=num_clones_per_group,
                element_type=element_type
            )
            
            llm_texts[group_id] = generated
            
        except Exception as e:
            logger.warning(f"Failed to generate LLM texts for group {group_id}: {e}")
            # Use fallback
            llm_texts[group_id] = [f"Option {i+1}" for i in range(num_clones_per_group)]
    
    return llm_texts

