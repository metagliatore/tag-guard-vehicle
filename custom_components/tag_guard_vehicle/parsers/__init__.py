"""Parser registry for tag brands/ecosystems.

Each parser module should expose at minimum:
- parse_connection_state(ops, attrs) -> (connected: bool, last_op: dict)
- extract_coords_from_ops_attrs(last_op, attrs) -> (lat, lon)

Register new parsers by adding a module in this package named after the brand
or model (e.g. `vedeneb_ha_smartthings_find.py`) and ensure the module-level functions above are
present.
"""
from typing import Callable, Dict, Optional, Tuple

# Simple registry mapping keys (e.g. 'vedeneb_ha_smartthings_find') to parser callables.
_REGISTRY: Dict[str, Dict[str, Callable]] = {}


def register(key: str, parse_connection_state: Callable, extract_coords: Callable) -> None:
    _REGISTRY[key] = {
        "parse_connection_state": parse_connection_state,
        "extract_coords_from_ops_attrs": extract_coords,
    }


def get_parser(key: str) -> Optional[Dict[str, Callable]]:
    return _REGISTRY.get(key)


# Auto-register known parsers if present
try:
    from . import vedeneb_ha_smartthings_find as vedeneb_parser

    register("vedeneb_ha_smartthings_find", vedeneb_parser.parse_connection_state, vedeneb_parser.extract_coords_from_ops_attrs)
    register("samsung_smarttag2", vedeneb_parser.parse_connection_state, vedeneb_parser.extract_coords_from_ops_attrs)
except Exception:
    # ignore missing optional parsers
    pass

try:
    from . import smartthings_find_by_pixelshober as st_find_parser

    register(
        "pixelshober_ha_smartthings_find",
        st_find_parser.parse_connection_state,
        st_find_parser.extract_coords_from_ops_attrs,
    )
except Exception:
    # ignore missing optional parsers
    pass
