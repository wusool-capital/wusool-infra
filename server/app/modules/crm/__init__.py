"""Buyer and seller roles for the Engine: reads with server-side filters, search and
cursor paging, and writes sent through `ddl_commands` (Attio first, then Postgres).
The `engine` module composes these into page views."""

from app.modules.crm.api.dependencies import CurrentUser, require_user
from app.modules.crm.api.problems import ProblemError, install_problem_handlers, problem
from app.modules.crm.api.router import router
from app.modules.crm.api.schemas import (
    ApiModel,
    BuyerFilterOptionsView,
    BuyerFilterQuery,
    BuyerQuery,
    BuyerRoleView,
    PersonView,
    ProblemDetail,
    SellerFilterOptionsView,
    SellerFilterQuery,
    SellerQuery,
    SellerRoleView,
    TeamMemberView,
)
from app.modules.crm.application.service import CrmService
from app.modules.crm.bootstrap import crm_service
from app.modules.crm.domain.roles import BuyersPage, SellersPage, SignedInUser

__all__ = [
    "ApiModel",
    "BuyerFilterOptionsView",
    "BuyerFilterQuery",
    "BuyerQuery",
    "BuyerRoleView",
    "BuyersPage",
    "CrmService",
    "CurrentUser",
    "PersonView",
    "ProblemDetail",
    "ProblemError",
    "SellerFilterOptionsView",
    "SellerFilterQuery",
    "SellerQuery",
    "SellerRoleView",
    "SellersPage",
    "SignedInUser",
    "TeamMemberView",
    "crm_service",
    "install_problem_handlers",
    "problem",
    "require_user",
    "router",
]
