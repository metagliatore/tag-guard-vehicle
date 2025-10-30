"""Validate translation JSON files parse and share expected keys across locales.
"""

import json
import os

TRANS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "custom_components", "tag_guard_vehicle", "translations")


def _load_component_messages(path):
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    # either top-level 'component' or language -> component
    if 'component' in data:
        comp = data['component']
    else:
        # first value should be language dict
        first = next(iter(data.values()))
        comp = first.get('component') if isinstance(first, dict) else None
    if comp is None:
        return None
    # look for 'messages' node
    return comp.get('messages') if isinstance(comp, dict) else None


def test_all_translation_files_have_messages():
    files = [f for f in os.listdir(TRANS_DIR) if f.endswith('.json')]
    assert files, "No translation files found"
    for f in files:
        path = os.path.join(TRANS_DIR, f)
        msgs = _load_component_messages(path)
        assert msgs is not None, f"{f} missing component.messages"


def test_all_locales_have_same_message_keys():
    files = [f for f in os.listdir(TRANS_DIR) if f.endswith('.json')]
    all_keys = None
    for f in files:
        path = os.path.join(TRANS_DIR, f)
        msgs = _load_component_messages(path)
        assert msgs is not None, f"{f} missing component.messages"
        keys = set(msgs.keys())
        if all_keys is None:
            all_keys = keys
        else:
            missing = all_keys - keys
            extra = keys - all_keys
            assert not missing, f"{f} missing keys: {missing}"
            assert not extra, f"{f} has extra keys: {extra}"
