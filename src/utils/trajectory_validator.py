"""
Trajectory Validator - Validates trajectory.json entries against parquet data.

Detects mismatches between:
1. Action op and element type (e.g., CLICK on textbox is suspicious)
2. step_instruction element type vs target_element_type from parquet
3. step_instruction element text vs target_element_text from parquet
"""

import re
from typing import Dict, Any, List, Optional, Tuple


# Pattern to parse step_instruction: "Click on 'text' element_type" or "Type 'value' in 'text' element_type"
# Also handles "Click on 'text' in the heading"
# Pattern 1: "Click on 'text' element_type" or "Click on 'text' in the heading"
# Pattern 2: "Type 'value' in 'text' element_type" or "Select 'value' in 'text' element_type"

# Valid op and element type combinations
VALID_OP_ELEMENT_COMBINATIONS = {
    'CLICK': ['button', 'link', 'checkbox', 'radio', 'div', 'span', 'heading', 'ins', 'generic'],
    'TYPE': ['textbox', 'input', 'searchbox', 'combobox'],
    'SELECT': ['combobox', 'listbox', 'select'],
}

# Element type aliases (for matching)
ELEMENT_TYPE_ALIASES = {
    'textbox': ['input', 'textbox', 'searchbox'],
    'input': ['input', 'textbox', 'searchbox'],
    'searchbox': ['input', 'textbox', 'searchbox'],
    'combobox': ['combobox', 'select', 'listbox'],
    'select': ['combobox', 'select', 'listbox'],
    'listbox': ['combobox', 'select', 'listbox'],
    'button': ['button'],
    'link': ['link'],
    'checkbox': ['checkbox'],
    'radio': ['radio'],
    'div': ['div'],
    'span': ['span'],
    'heading': ['heading'],
    'ins': ['ins'],
    'generic': ['generic'],
}


def extract_element_info_from_instruction(step_instruction: str) -> Optional[Tuple[str, str]]:
    """Extract element type and text from step_instruction.
    
    Examples:
        "Click on 'View Deal' link" -> ("link", "View Deal")
        "Type 'test' in 'Search' textbox" -> ("textbox", "Search")
        "Select 'Option' in 'Dropdown' combobox" -> ("combobox", "Dropdown")
    
    Returns:
        Tuple of (element_type, element_text) or None if parsing fails
    """
    if not step_instruction:
        return None
    
    # Pattern 1: "Click on 'text' element_type" or "Click on 'text' in the heading"
    click_match = re.search(r"Click on ['\"]([^'\"]+)['\"]\s+(?:in\s+the\s+)?(\w+)", step_instruction)
    if click_match:
        element_text = click_match.group(1)
        element_type = click_match.group(2).lower()
        return element_type, element_text
    
    # Pattern 2: "Type 'value' in 'text' element_type" or "Select 'value' in 'text' element_type"
    type_select_match = re.search(r"(?:Type|Select)\s+['\"]([^'\"]+)['\"]\s+in\s+['\"]([^'\"]+)['\"]\s+(\w+)", step_instruction)
    if type_select_match:
        element_text = type_select_match.group(2)  # Element text (second quoted string)
        element_type = type_select_match.group(3).lower()  # Element type
        return element_type, element_text
    
    return None


def is_valid_op_element_combination(op: str, element_type: str) -> bool:
    """Check if action op and element type are compatible.
    
    Args:
        op: Action operation (CLICK, TYPE, SELECT)
        element_type: Element type (button, link, textbox, etc.)
    
    Returns:
        True if combination is valid, False otherwise
    """
    op_upper = op.upper()
    element_type_lower = element_type.lower()
    
    if op_upper not in VALID_OP_ELEMENT_COMBINATIONS:
        return True  # Unknown op, don't reject
    
    valid_types = VALID_OP_ELEMENT_COMBINATIONS[op_upper]
    
    # Check direct match
    if element_type_lower in valid_types:
        return True
    
    # Check aliases
    for valid_type in valid_types:
        if element_type_lower in ELEMENT_TYPE_ALIASES.get(valid_type, [valid_type]):
            return True
    
    return False


def validate_trajectory_entry(
    trajectory_entry: Dict[str, Any],
    parquet_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate a single trajectory entry for mismatches.
    
    Args:
        trajectory_entry: Entry from trajectory.json
        parquet_data: Optional parquet data for comparison (if available)
    
    Returns:
        Dict with validation results:
        {
            'is_valid': bool,
            'issues': List[str],
            'warnings': List[str]
        }
    """
    issues = []
    warnings = []
    
    op = trajectory_entry.get('op', '').upper()
    target_element_type = trajectory_entry.get('target_element_type', '').lower()
    target_element_text = trajectory_entry.get('target_element_text', '')
    step_instruction = trajectory_entry.get('step_instruction', '')
    
    # Check 1: op and element type compatibility
    if op and target_element_type:
        if not is_valid_op_element_combination(op, target_element_type):
            issues.append(
                f"Invalid op/element combination: {op} on {target_element_type} "
                f"(e.g., {op} should not be used with {target_element_type})"
            )
    
    # Check 2: step_instruction element type vs target_element_type
    if step_instruction:
        instruction_info = extract_element_info_from_instruction(step_instruction)
        if instruction_info:
            inst_element_type, inst_element_text = instruction_info
            
            # Compare element types
            if inst_element_type != target_element_type:
                # Check if they're aliases
                is_alias = False
                for base_type, aliases in ELEMENT_TYPE_ALIASES.items():
                    if (inst_element_type in aliases and target_element_type in aliases) or \
                       (inst_element_type == base_type and target_element_type in aliases) or \
                       (target_element_type == base_type and inst_element_type in aliases):
                        is_alias = True
                        break
                
                if not is_alias:
                    issues.append(
                        f"Element type mismatch: step_instruction has '{inst_element_type}' "
                        f"but parquet has '{target_element_type}'"
                    )
            
            # Compare element text (normalized)
            if inst_element_text and target_element_text:
                # Normalize text for comparison
                def normalize(t):
                    return t.lower().strip().replace('\u2228', '').replace('∨', '')
                
                normalized_inst = normalize(inst_element_text)
                normalized_target = normalize(target_element_text)
                
                # Check if texts match (exact or substring)
                if normalized_inst != normalized_target and \
                   normalized_inst not in normalized_target and \
                   normalized_target not in normalized_inst:
                    # Allow some differences (e.g., whitespace, special chars)
                    # But flag significant differences
                    if abs(len(normalized_inst) - len(normalized_target)) > 5 or \
                       not any(word in normalized_target for word in normalized_inst.split() if len(word) > 3):
                        warnings.append(
                            f"Element text mismatch: step_instruction has '{inst_element_text}' "
                            f"but parquet has '{target_element_text}'"
                        )
        else:
            warnings.append(f"Could not parse step_instruction: '{step_instruction}'")
    
    # Check 3: If parquet data is provided, compare with it
    if parquet_data:
        parquet_op = parquet_data.get('action_op', '').upper()
        if parquet_op and op and parquet_op != op:
            issues.append(
                f"Operation mismatch: trajectory has '{op}' but parquet has '{parquet_op}'"
            )
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }


def validate_trajectory_file(
    trajectory_path: str,
    parquet_data_map: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Validate all entries in a trajectory.json file.
    
    Args:
        trajectory_path: Path to trajectory.json file
        parquet_data_map: Optional dict mapping action_uid to parquet data
    
    Returns:
        Dict with validation results:
        {
            'total_entries': int,
            'valid_entries': int,
            'invalid_entries': int,
            'entries_with_issues': List[Dict],
            'entries_with_warnings': List[Dict]
        }
    """
    import json
    
    with open(trajectory_path, 'r') as f:
        trajectory = json.load(f)
    
    total_entries = len(trajectory)
    valid_entries = 0
    invalid_entries = 0
    entries_with_issues = []
    entries_with_warnings = []
    
    for entry in trajectory:
        action_uid = entry.get('action_uid')
        parquet_data = parquet_data_map.get(action_uid) if parquet_data_map else None
        
        validation = validate_trajectory_entry(entry, parquet_data)
        
        if validation['is_valid']:
            valid_entries += 1
        else:
            invalid_entries += 1
        
        if validation['issues']:
            entries_with_issues.append({
                'action_uid': action_uid,
                'issues': validation['issues'],
                'entry': entry
            })
        
        if validation['warnings']:
            entries_with_warnings.append({
                'action_uid': action_uid,
                'warnings': validation['warnings'],
                'entry': entry
            })
    
    return {
        'total_entries': total_entries,
        'valid_entries': valid_entries,
        'invalid_entries': invalid_entries,
        'entries_with_issues': entries_with_issues,
        'entries_with_warnings': entries_with_warnings
    }

