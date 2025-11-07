"""
Exception classes for element location failures.
"""


class ElementLocatorError(Exception):
    """Base exception for element location failures"""
    pass


class ElementNotFoundError(ElementLocatorError):
    """No element found matching fingerprint"""
    pass


class AmbiguousMatchError(ElementLocatorError):
    """Multiple elements found, cannot disambiguate"""
    pass


class ElementValidationError(ElementLocatorError):
    """Element found but failed validation checks (wrong element, not visible, viewport issues, etc.)"""
    pass

