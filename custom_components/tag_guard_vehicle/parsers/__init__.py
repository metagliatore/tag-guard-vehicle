"""Parser registry for tag brands/ecosystems.

Each parser module should expose at minimum:
- parse_connection_state(ops, attrs) -> (connected: bool, last_op: dict)
- extract_coords_from_ops_attrs(last_op, attrs) -> (lat, lon)

Register new parsers by adding a module in this package named after the brand
or model (e.g. `samsung.py`) and ensure the module-level functions above are
present.
"""
from typing import Callable, Dict, Optional, Tuple

# Simple registry mapping keys (e.g. 'samsung_smarttag2') to parser callables.
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
    from . import samsung as samsung_parser

    register("samsung_smarttag2", samsung_parser.parse_connection_state, samsung_parser.extract_coords_from_ops_attrs)
except Exception:
    # ignore missing optional parsers
    pass
