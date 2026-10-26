"""The product namespace for the field scripts, read from `brand.json` : the one place the name lives.

    setting("MCP_TOKEN")  ->  "<NS>_MCP_TOKEN", NS the upper-cased namespace (core's `paths.setting_name`, without importing core)
"""
import json
import os

_BRAND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "brand.json")


def namespace():
    with open(_BRAND, encoding="utf-8") as f:
        return json.load(f)["namespace"]


def setting(name):
    return f"{namespace().upper()}_{name}"
