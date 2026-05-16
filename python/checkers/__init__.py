from dataclasses import dataclass, field


@dataclass
class CheckResult:
    check_name: str
    category:   str
    status:     str   # "pass" | "fail" | "warning" | "skip" | "disabled"
    message:    str
    details:    dict = field(default_factory=dict)
    rule_key:   str | None = None

    def to_dict(self):
        return {
            "check_name": self.check_name,
            "category":   self.category,
            "status":     self.status,
            "message":    self.message,
            "details":    self.details,
            "rule_key":   self.rule_key,
        }


def selected(enabled_rule_keys, rule_key: str) -> bool:
    return enabled_rule_keys is None or rule_key in enabled_rule_keys


def result(rule_key: str, check_name: str, category: str, status: str, message: str, details: dict | None = None):
    return CheckResult(
        check_name=check_name,
        category=category,
        status=status,
        message=message,
        details=details or {},
        rule_key=rule_key
    )
