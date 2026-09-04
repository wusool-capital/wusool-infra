"""Shared constructor for every application-layer mixin in this module —
each mixin subclasses this instead of redeclaring its own `__init__`, so
`service.py`'s composed facade ends up with exactly one constructor no
matter how many mixins it combines.
"""

from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWorkFactory


class ServiceBase:
    def __init__(self, uow_factory: DdlCommandsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory
