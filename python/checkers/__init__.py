from dataclasses import dataclass, field


@dataclass
class CheckResult:
    check_name: str
    category:   str
    status:     str   # "pass" | "fail" | "warning" | "skip"
    message:    str
    details:    dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "check_name": self.check_name,
            "category":   self.category,
            "status":     self.status,
            "message":    self.message,
            "details":    self.details,
        }
