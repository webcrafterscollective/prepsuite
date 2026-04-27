from __future__ import annotations

from enum import StrEnum


class AcademicYearStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class RuleStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class IntegrationStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
