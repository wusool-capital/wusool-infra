"""Shared-kernel ORM models: entities no single module owns.

These map tables read by more than one module (buyers, sellers, matching).
Only imports from `app.shared.database.base` — never from `app.modules.*`,
so the dependency direction stays one-way (modules depend on shared, not the
reverse).
"""

from app.shared.database.models.deal import Deal
from app.shared.database.models.mandate import Mandate
from app.shared.database.models.organization import Organization
from app.shared.database.models.person import Person

__all__ = ["Deal", "Mandate", "Organization", "Person"]
