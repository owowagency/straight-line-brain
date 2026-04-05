from pydantic import BaseModel


class LintIssue(BaseModel):
    severity: str  # "warning", "info", "suggestion"
    category: str  # "missing", "orphan", "stale", "gap"
    message: str
    entry_id: str | None = None
    action: str | None = None  # suggested action to fix


class LintReport(BaseModel):
    score: int  # 0-100 health score
    total_issues: int
    issues: list[LintIssue]
    coverage: dict  # which categories are filled
    stats: dict  # counts and metadata
