"""Organization persistence, shared by `ddl_commands` (Slack org-selection/
search/edit) and `matching_engine` (buyer/seller org-name search) — the one
canonical implementation of a trigram organization-name search previously
duplicated 3 ways across both modules' own repositories.

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.organizations.application.ports.organizations import OrganizationRepositoryPort
from app.modules.organizations.persistence.repositories.organizations_repository import (
    OrganizationRepository,
)

__all__ = ["OrganizationRepository", "OrganizationRepositoryPort"]
