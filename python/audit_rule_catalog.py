import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent / "audit_rules.json"


def load_sections() -> list[dict]:
    with CATALOG_PATH.open("r", encoding="utf-8") as catalog_file:
        return json.load(catalog_file)["sections"]


SECTIONS = load_sections()
RULES = [
    {
        **rule,
        "section_key": section["section_key"],
        "section_label": section["section_label"],
    }
    for section in SECTIONS
    for rule in section["rules"]
]
RULE_MAP = {rule["rule_key"]: rule for rule in RULES}
DEFAULT_ENABLED_RULES = {
    rule["rule_key"]: bool(rule.get("default_enabled", True))
    for rule in RULES
}


def normalize_enabled_rules(enabled_rules: dict | None) -> dict[str, bool]:
    resolved = DEFAULT_ENABLED_RULES.copy()
    for rule_key, value in (enabled_rules or {}).items():
        resolved[str(rule_key)] = _to_bool(value)
    return resolved


def section_rule_keys(section_key: str) -> list[str]:
    for section in SECTIONS:
        if section["section_key"] == section_key:
            return [rule["rule_key"] for rule in section["rules"]]
    return []


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
