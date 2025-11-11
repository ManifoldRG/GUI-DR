"""
Element location modules for finding and disambiguating elements.
"""

from .element_locator import ElementLocator
from .nearest_element_finder import NearestElementFinder
from .strategies import (
    LocatorStrategy,
    IdStrategy,
    DataTestIdStrategy,
    RoleAndTextStrategy,
    TextStrategy,
    FingerprintStrategy,
    TagAndClassStrategy,
    BroadSearchStrategy
)

__all__ = [
    'ElementLocator',
    'NearestElementFinder',
    'LocatorStrategy',
    'IdStrategy',
    'DataTestIdStrategy',
    'RoleAndTextStrategy',
    'TextStrategy',
    'FingerprintStrategy',
    'TagAndClassStrategy',
    'BroadSearchStrategy'
]


