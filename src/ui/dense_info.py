"""
Type 2: Complex, Dense Information - Paraphrase text and clone elements with LLM-generated text.
Consolidates all cloning logic from the codebase.
"""
from typing import List, Dict, Any, Optional
from loguru import logger


def generate_dense_info_js(
    llm_texts: Optional[Dict[str, List[str]]] = None,
    target_element_text: Optional[str] = None,
    enable_paraphrase: bool = True
) -> str:
    """Generate JavaScript for dense information modifications (Type 2).
    
    Args:
        llm_texts: Dictionary mapping element group IDs to LLM-generated texts
        target_element_text: Text content of target element (for paraphrasing)
        enable_paraphrase: Whether to enable paragraph paraphrasing
    
    Returns:
        JavaScript code string
    """
    # Check if target element has text content
    if not target_element_text or not target_element_text.strip():
        logger.warning("Target element has no text content, skipping Type 2 dense info modifications")
        return ""
    
    llm_texts_js = _format_llm_texts_for_js(llm_texts or {})
    target_text_js = f'"{target_element_text.strip()}"' if target_element_text else 'null'
    
    return f"""
            // Type 2: Complex, dense information
            if (params.enableDenseInfo) {{
                const llmTexts = {llm_texts_js};
                const targetElementText = {target_text_js};
                
                // Check if target element has text
                if (!targetElementText || !targetElementText.trim()) {{
                    console.debug('Skipping Type 2: target element has no text content');
                    return;
                }}
                
                // Helper functions (consolidated from cloning.py)
                {_generate_helper_functions_js()}
                
                // Paraphrase paragraph sections to incorporate target element text
                {_generate_paraphrase_js() if enable_paraphrase else ''}
                
                // Clone elements with LLM-generated text
                {_generate_llm_cloning_js()}
            }}
    """


def _format_llm_texts_for_js(llm_texts: Dict[str, List[str]]) -> str:
    """Format LLM texts dictionary for JavaScript."""
    if not llm_texts:
        return "{}"
    
    items = []
    for group_id, texts in llm_texts.items():
        # Escape quotes in text and format as JavaScript array
        escaped_texts = [t.replace('"', '\\"').replace('\\', '\\\\') for t in texts]
        texts_js = "[" + ", ".join([f'"{t}"' for t in escaped_texts]) + "]"
        items.append(f'"{group_id}": {texts_js}')
    
    return "{" + ", ".join(items) + "}"


def _generate_helper_functions_js() -> str:
    """Generate helper functions for cloning (from cloning.py)."""
    return """
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
                
                function shouldSkipElement(el) {
                    const style = window.getComputedStyle(el);
                    const display = style.display;
                    const tagName = el.tagName;
                    const classList = Array.from(el.classList || []).map(c => c.toLowerCase());
                    const id = (el.id || '').toLowerCase();
                    
                    if (['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(tagName)) {
                        return true;
                    }
                    
                    if (id.includes('logo') || classList.some(c => c.includes('logo') || c.includes('brand'))) {
                        return true;
                    }
                    
                    if (display === 'inline' && !['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(tagName)) {
                        return true;
                    }
                    
                    if (['SPAN', 'EM', 'STRONG', 'I', 'B', 'U', 'SMALL'].includes(tagName) && display === 'inline') {
                        return true;
                    }
                    
                    return false;
                }
                
                function isPartOfRepeatedPattern(el) {
                    const tagName = el.tagName;
                    const inputType = el.getAttribute('type') || '';
                    
                    if (tagName === 'INPUT' && (inputType === 'search' || (el.placeholder && el.placeholder.toLowerCase().includes('search')))) {
                        const allSearchInputs = Array.from(document.querySelectorAll('input[type="search"]'));
                        if (allSearchInputs.length <= 1) return false;
                    }
                    
                    const parent = el.parentElement;
                    if (!parent) return false;
                    
                    const siblings = Array.from(parent.children).filter(child => {
                        if (child === el || shouldSkipElement(child)) return false;
                        if (child.tagName !== tagName) return false;
                        if (tagName === 'INPUT') {
                            return (child.getAttribute('type') || '') === inputType;
                        }
                        return true;
                    });
                    
                    return siblings.length >= 1;
                }
    """


def _generate_paraphrase_js() -> str:
    """Generate JavaScript for paraphrasing paragraph sections to incorporate target element text."""
    return """
                // Paraphrase paragraphs to incorporate target element text
                function paraphraseParagraphs() {
                    if (!targetElementText || !targetElementText.trim()) return;
                    
                    const paragraphs = document.querySelectorAll('p');
                    paragraphs.forEach(p => {
                        const text = p.textContent.trim();
                        if (text.length > 50 && text.length < 500) {
                            // Incorporate target element text naturally into paragraph
                            const words = text.split(' ');
                            if (words.length > 10) {
                                // Find a natural insertion point (middle of paragraph)
                                const midPoint = Math.floor(words.length / 2);
                                
                                // Create paraphrased version incorporating target text
                                const firstHalf = words.slice(0, midPoint).join(' ');
                                const secondHalf = words.slice(midPoint).join(' ');
                                
                                // Incorporate target text naturally
                                const paraphrased = `${firstHalf} ${targetElementText} ${secondHalf}. ${text}`;
                                p.innerHTML = paraphrased;
                            }
                        }
                    });
                }
                
                paraphraseParagraphs();
    """


def _generate_llm_cloning_js() -> str:
    """Generate JavaScript for cloning elements with LLM-generated text."""
    return """
                // Clone elements with LLM-generated text
                function cloneWithLLMTexts() {
                    const interactiveSelectors = 'button, input[type="button"], input[type="submit"], a[href], li';
                    const allElements = Array.from(document.querySelectorAll(interactiveSelectors))
                        .filter(el => !shouldSkipElement(el));
                    
                    // Filter to elements that are part of repeated patterns
                    const elementsToClone = allElements.filter(el => {
                        if (el.tagName === 'LI') return true;
                        return isPartOfRepeatedPattern(el);
                    });
                    
                    const byContainer = new Map();
                    elementsToClone.forEach(el => {
                        const container = findSemanticContainer(el);
                        if (container && container !== document.body && container !== document.documentElement) {
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
                            .map(el => el.tagName + (el.textContent || el.value || '').substring(0, 10))
                            .join('_')
                            .replace(/[^a-zA-Z0-9_]/g, '')
                            .substring(0, 50);
                        
                        // Get LLM texts for this group
                        const llmTextsForGroup = llmTexts[groupId] || [];
                        if (llmTextsForGroup.length === 0) return;
                        
                        // Clone elements with LLM-generated text
                        const numToClone = Math.min(llmTextsForGroup.length, elements.length);
                        const shuffled = [...elements].sort(() => Math.random() - 0.5);
                        
                        for (let i = 0; i < numToClone; i++) {
                            try {
                                const original = shuffled[i];
                                const clone = original.cloneNode(true);
                                clone.removeAttribute('id');
                                
                                // Set LLM-generated text
                                const newText = llmTextsForGroup[i];
                                const tagName = clone.tagName;
                                
                                if (tagName === 'LI') {
                                    clone.textContent = newText;
                                    clone.style.display = 'list-item';
                                } else if (tagName === 'BUTTON' || tagName === 'A') {
                                    clone.textContent = newText;
                                } else if (tagName === 'INPUT') {
                                    const inputType = clone.getAttribute('type') || 'text';
                                    if (inputType === 'button' || inputType === 'submit') {
                                        clone.value = newText;
                                    } else if (clone.placeholder) {
                                        clone.placeholder = newText;
                                    }
                                    if (clone.name) {
                                        clone.name = clone.name + '_clone_' + Math.random().toString(36).slice(2, 7);
                                    }
                                }
                                
                                // Preserve display style
                                const originalStyle = window.getComputedStyle(original);
                                if (['block', 'flex', 'grid'].includes(originalStyle.display)) {
                                    clone.style.display = originalStyle.display;
                                }
                                
                                // Insert clone
                                if (original.nextSibling) {
                                    container.insertBefore(clone, original.nextSibling);
                                } else {
                                    container.appendChild(clone);
                                }
                            } catch (e) {
                                console.debug('Failed to clone with LLM text:', e);
                            }
                        }
                    });
                }
                
                cloneWithLLMTexts();
    """
