"""The single declarative base every ORM model in this application attaches to."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
