"""Composition root for the approval use cases (§2, §36)."""

from app.modules.approvals.application.use_cases import ApproveMatchUseCase, RejectMatchUseCase
from app.shared.database import get_sessionmaker


def build_approve_match_use_case() -> ApproveMatchUseCase:
    return ApproveMatchUseCase(get_sessionmaker())


def build_reject_match_use_case() -> RejectMatchUseCase:
    return RejectMatchUseCase(get_sessionmaker())
