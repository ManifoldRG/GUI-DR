"""
Step instruction generation from action representations.
"""

import re
from typing import Tuple

# Regex pattern for parsing target_action_reprs: [element_type] element_text -> ACTION_TYPE(: action_value)?
TARGET_ACTION_REPRS_PATTERN = r"\[(.*?)\]\s(.*?)\s->\s(CLICK|SELECT|TYPE)(?:\s*:\s*(.*))?"
TARGET_ACTION_REPRS_PATTERN_SIMPLE = r"\[(.*?)\]\s(.*?)\s->.*"


def parse_target_action_reprs(target_action_reprs: str) -> Tuple[str, str]:
    """Parse target_action_reprs to extract element type and text.
    
    Args:
        target_action_reprs: String like "[button] Submit -> CLICK"
    
    Returns:
        Tuple of (target_element_type, target_element_text)
    """
    match = re.match(TARGET_ACTION_REPRS_PATTERN_SIMPLE, target_action_reprs)
    if not match:
        raise ValueError(f"Invalid target action reprs: {target_action_reprs}")
    
    return match.group(1).strip(), match.group(2).strip()


def generate_step_instruction(target_action_reprs: str) -> str:
    """Convert target_action_reprs to natural language step instruction."""
    match = re.match(TARGET_ACTION_REPRS_PATTERN, target_action_reprs)
    if not match:
        raise ValueError(f"Invalid target action reprs: {target_action_reprs}")
    
    element_type, element_text, action_type, action_value = [
        g.strip() if g else g for g in match.groups()
    ]
    
    if action_type == "CLICK":
        if element_type == "heading":
            return f"Click on '{element_text}' in the heading"
        return f"Click on '{element_text}' {element_type}"
    elif action_type == "SELECT":
        return f"Select '{action_value}' in '{element_text}' {element_type}"
    elif action_type == "TYPE":
        return f"Type '{action_value}' in '{element_text}' {element_type}"
    else:
        return f"{action_type} on '{element_text}' {element_type}"

