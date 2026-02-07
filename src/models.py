from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Any


@dataclass
class SkillSpec:
    """技能孵化任务规范"""

    name: str
    keyword: str
    description: str

    research_strategy: str = "context7_first"  # context7_first | local_first | hybrid
    language: str = "python"  # python | javascript | typescript
    min_context_tokens: int = 20000
    max_distilled_tokens: int = 10000

    references: Optional[list[str]] = field(default_factory=list)
    skip_distillation: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillSpec":
        return cls(
            name=data["name"],
            keyword=data["keyword"],
            description=data.get("description", ""),
            research_strategy=data.get("research_strategy", "context7_first"),
            language=data.get("language", "python"),
            min_context_tokens=int(data.get("min_context_tokens", 20000)),
            max_distilled_tokens=int(data.get("max_distilled_tokens", 10000)),
            references=data.get("references", []) or [],
            skip_distillation=bool(data.get("skip_distillation", False)),
        )


@dataclass
class SkillResult:
    """技能孵化结果"""

    skill_name: str
    status: str  # success | partial_success | failed | timeout
    skill_dir: str
    skill_file: str
    demo_code: str = ""
    error_log: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
