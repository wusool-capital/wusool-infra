"""The Engine's page reads. Composes `crm` into one payload per page and owns no tables;
blocks whose source is not live yet come back empty and named in `unavailable`."""

from app.modules.engine.api.router import router

__all__ = ["router"]
