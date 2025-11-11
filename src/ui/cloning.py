"""
Element and Section Cloning Module - Generates JavaScript for cloning UI elements and sections.
"""


def generate_cloning_js() -> str:
    """Generate JavaScript code for cloning elements and sections."""
    element_cloning_js = _generate_element_cloning_js()
    section_cloning_js = _generate_section_cloning_js()
    
    return f"""
            // Element and section cloning
            if (params.enableElementCloning !== false) {{{{
                {element_cloning_js}
                {section_cloning_js}
            }}}}
    """


def _generate_element_cloning_js() -> str:
    """Generate JavaScript for cloning individual elements (buttons, list items, etc.)."""
    return """
                // ===== Element Cloning Logic =====
                function generateVariation(text) {
                    if (!text || text.trim().length === 0) return 'Option';
                    const variations = [
                        text + ' Plus',
                        'New ' + text,
                        text + ' Pro',
                        'Extra ' + text,
                        text.replace(/s$/, '') + 's',
                        text.split(' ').reverse().join(' '),
                    ];
                    return variations[Math.floor(Math.random() * variations.length)];
                }
                
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
                    const text = (el.textContent || '').trim().toLowerCase();
                    
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
                    
                    if (tagName === 'P') {
                        const isShort = text.length < 50;
                        const isTitleLike = text.split(' ').length <= 5 && /^[A-Z]/.test(text);
                        const isFirstInSection = !el.previousElementSibling || 
                                                ['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(el.previousElementSibling.tagName);
                        if (isShort && isTitleLike && isFirstInSection) {
                            return true;
                        }
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
                
                function cloneElementWithVariation(original) {
                    const clone = original.cloneNode(true);
                    clone.removeAttribute('id');
                    
                    const tagName = clone.tagName;
                    const text = (clone.textContent || clone.innerText || '').trim();
                    
                    if (tagName === 'BUTTON' || tagName === 'A') {
                        if (text) clone.textContent = generateVariation(text);
                    }
                    
                    if (tagName === 'LI') {
                        if (text) clone.textContent = generateVariation(text);
                        clone.style.display = 'list-item';
                    }
                    
                    if (tagName === 'DIV' && (clone.className.includes('card') || clone.className.includes('item'))) {
                        const textNodes = Array.from(clone.querySelectorAll('p, span, h1, h2, h3, h4, h5, h6'));
                        textNodes.forEach(node => {
                            const nodeText = (node.textContent || '').trim();
                            if (nodeText && !['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(node.tagName)) {
                                node.textContent = generateVariation(nodeText);
                            }
                        });
                    }
                    
                    if (tagName === 'INPUT') {
                        const inputType = clone.getAttribute('type') || 'text';
                        if (clone.placeholder) clone.placeholder = generateVariation(clone.placeholder);
                        if (clone.value && ['text', 'search', 'email'].includes(inputType)) {
                            clone.value = generateVariation(clone.value);
                        }
                        if (clone.name) clone.name = clone.name + '_clone_' + Math.random().toString(36).slice(2, 7);
                    }
                    
                    if (tagName === 'TEXTAREA') {
                        if (clone.placeholder) clone.placeholder = generateVariation(clone.placeholder);
                        if (clone.value) clone.value = generateVariation(clone.value);
                        if (clone.name) clone.name = clone.name + '_clone_' + Math.random().toString(36).slice(2, 7);
                    }
                    
                    if (tagName === 'SELECT') {
                        if (clone.name) clone.name = clone.name + '_clone_' + Math.random().toString(36).slice(2, 7);
                        const options = Array.from(clone.options);
                        if (options.length > 1) {
                            const shuffled = [...options].sort(() => Math.random() - 0.5);
                            clone.innerHTML = '';
                            shuffled.forEach(opt => clone.appendChild(opt));
                        }
                    }
                    
                    if (tagName === 'A') {
                        clone.href = '#' + Math.random().toString(36).slice(2, 11);
                    }
                    
                    return clone;
                }
                
                // Clone elements - double the group size
                const interactiveSelectors = 'button, input[type="button"], input[type="submit"], input[type="text"], input[type="email"], input[type="password"], textarea, select, a[href]';
                const listItemSelectors = 'li';
                const cardSelectors = '[class*="card"], [class*="item"]';
                
                const allCandidates = [
                    ...Array.from(document.querySelectorAll(interactiveSelectors)),
                    ...Array.from(document.querySelectorAll(listItemSelectors)),
                    ...Array.from(document.querySelectorAll(cardSelectors))
                ].filter(el => !shouldSkipElement(el));
                
                const elementsToClone = allCandidates.filter(el => {
                    if (el.tagName === 'LI') return true;
                    return isPartOfRepeatedPattern(el);
                });
                
                const byContainer = new Map();
                elementsToClone.forEach(el => {
                    const container = findSemanticContainer(el);
                    if (container && container !== document.body && container !== document.documentElement) {
                        if (!byContainer.has(container)) byContainer.set(container, []);
                        byContainer.get(container).push(el);
                    }
                });
                
                byContainer.forEach((elements, container) => {
                    if (elements.length === 0) return;
                    
                    // Double the group: clone all elements
                    const numToClone = elements.length;
                    const shuffled = [...elements].sort(() => Math.random() - 0.5);
                    
                    for (let i = 0; i < numToClone; i++) {
                        try {
                            const original = shuffled[i];
                            const clone = cloneElementWithVariation(original);
                            
                            const originalStyle = window.getComputedStyle(original);
                            if (['block', 'flex', 'grid'].includes(originalStyle.display)) {
                                clone.style.display = originalStyle.display;
                            }
                            
                            if (original.nextSibling) {
                                container.insertBefore(clone, original.nextSibling);
                            } else {
                                container.appendChild(clone);
                            }
                        } catch (e) {
                            console.debug('Failed to clone element:', e);
                        }
                    }
                });
    """


def _generate_section_cloning_js() -> str:
    """Generate JavaScript for cloning entire sections (e.g., 'Top Rated' -> 'Best Review')."""
    return """
                // ===== Section Cloning Logic =====
                function findSectionHeading(section) {
                    // Find first heading in section (h1-h6)
                    const headings = Array.from(section.querySelectorAll('h1, h2, h3, h4, h5, h6'));
                    if (headings.length === 0) return null;
                    
                    // Prefer headings that are direct children or early in the DOM
                    for (const heading of headings) {
                        let depth = 0;
                        let current = heading.parentElement;
                        while (current && current !== section) {
                            depth++;
                            current = current.parentElement;
                        }
                        if (depth <= 2) return heading;
                    }
                    return headings[0];
                }
                
                function hasSectionStructure(section) {
                    // Check if section has heading + content
                    const heading = findSectionHeading(section);
                    if (!heading) return false;
                    
                    // Check if section has meaningful content (not just heading)
                    const content = Array.from(section.children).filter(child => 
                        child.tagName !== 'H1' && child.tagName !== 'H2' && child.tagName !== 'H3' &&
                        child.tagName !== 'H4' && child.tagName !== 'H5' && child.tagName !== 'H6'
                    );
                    
                    return content.length > 0;
                }
                
                function isSectionLike(el) {
                    const tagName = el.tagName;
                    const classList = Array.from(el.classList || []).map(c => c.toLowerCase());
                    
                    // Semantic section tags
                    if (['SECTION', 'ARTICLE'].includes(tagName)) {
                        return true;
                    }
                    
                    // Divs with section-like classes
                    if (tagName === 'DIV') {
                        const sectionPatterns = ['section', 'block', 'widget', 'panel', 'card', 'container'];
                        if (classList.some(c => sectionPatterns.some(p => c.includes(p)))) {
                            return true;
                        }
                    }
                    
                    return false;
                }
                
                function findSimilarSections(section) {
                    // Find sibling sections with similar structure
                    const parent = section.parentElement;
                    if (!parent) return [];
                    
                    const siblings = Array.from(parent.children).filter(sibling => {
                        if (sibling === section) return false;
                        if (!isSectionLike(sibling)) return false;
                        if (!hasSectionStructure(sibling)) return false;
                        
                        // Check if structure is similar (both have headings + content)
                        return true;
                    });
                    
                    return siblings;
                }
                
                function cloneSectionWithVariation(original) {
                    const clone = original.cloneNode(true);
                    clone.removeAttribute('id');
                    
                    // Find and modify section heading
                    const heading = findSectionHeading(clone);
                    if (heading) {
                        const originalText = (heading.textContent || '').trim();
                        if (originalText) {
                            heading.textContent = generateVariation(originalText);
                        }
                    }
                    
                    // Modify content within section (but keep structure)
                    const contentElements = Array.from(clone.querySelectorAll('li, p, span, button, a'));
                    contentElements.forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (text && el.tagName !== 'H1' && el.tagName !== 'H2' && el.tagName !== 'H3' &&
                            el.tagName !== 'H4' && el.tagName !== 'H5' && el.tagName !== 'H6') {
                            el.textContent = generateVariation(text);
                        }
                    });
                    
                    return clone;
                }
                
                // Find all section-like containers
                const sectionSelectors = 'section, article, div[class*="section"], div[class*="block"], div[class*="widget"], div[class*="panel"]';
                const allSections = Array.from(document.querySelectorAll(sectionSelectors))
                    .filter(el => isSectionLike(el) && hasSectionStructure(el));
                
                // Group sections by parent and find those with similar siblings
                const sectionsToClone = allSections.filter(section => {
                    const similarSiblings = findSimilarSections(section);
                    // Only clone if there are similar sibling sections (repeated pattern)
                    return similarSiblings.length >= 1;
                });
                
                // Clone sections
                sectionsToClone.forEach(section => {
                    try {
                        const clone = cloneSectionWithVariation(section);
                        
                        // Insert after original section
                        if (section.nextSibling) {
                            section.parentElement.insertBefore(clone, section.nextSibling);
                        } else {
                            section.parentElement.appendChild(clone);
                        }
                    } catch (e) {
                        console.debug('Failed to clone section:', e);
                    }
                });
    """

