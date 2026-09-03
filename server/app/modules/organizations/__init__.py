"""Organization persistence, shared by `ddl_commands` (Slack org-selection/
search/edit) and `matching_engine` (buyer/seller org-name search) — the one
canonical implementation of a trigram organization-name search previously
duplicated 3 ways across both modules' own repositories.

Treated as a **full-access peer module** (`server/tests/test_architecture.py`'s
`_FULL_ACCESS_MODULES`), the same documented exception `utilities`/`attio`
get: this module has no domain layer, and its entire surface — a single
concrete `OrganizationRepository` — is exactly what consumers
(`ddl_commands/bootstrap.py`, its own Unit-of-Work) need to construct
directly, not a narrow Port worth hiding behind an adapter.
"""

from app.modules.organizations.application.ports.organizations import OrganizationRepositoryPort
from app.modules.organizations.persistence.repositories.organizations_repository import (
    OrganizationRepository,
)

__all__ = ["OrganizationRepository", "OrganizationRepositoryPort"]
