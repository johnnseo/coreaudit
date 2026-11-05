from dataclasses import dataclass, asdict, field
from typing import Optional

AREAS = {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


@dataclass
class Finding:
    id: str
    area: str              # C, O, R or E
    title: str
    status: str            # pass | fail | warn | unknown
    severity: str = "medium"
    evidence: str = ""     # exact text/value found on the site
    why: str = ""
    fix: str = ""
    source: str = "rule"   # rule | ai | google
    level: int = 1         # 1 = instant preview, 2 = full report

    def to_dict(self):
        return asdict(self)
