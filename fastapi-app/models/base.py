"""Shared pieces for every table module: the naming convention and small column helpers.

Imported by every table module before its tables are defined, so the naming convention is in place
when constraints get their names.
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Identity, Integer, func
from sqlmodel import Field, SQLModel

# Stable constraint/index names, so Alembic migrations stay predictable.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

TIMESTAMPTZ = DateTime(timezone=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def int_pk():
    return Field(default=None, sa_column=Column(Integer, Identity(), primary_key=True))


def bigint_pk():
    return Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))


def created_at_field():
    return Field(default_factory=utcnow, sa_type=TIMESTAMPTZ,
                 sa_column_kwargs={"server_default": func.now(), "nullable": False})


def updated_at_field():
    return Field(default_factory=utcnow, sa_type=TIMESTAMPTZ,
                 sa_column_kwargs={"server_default": func.now(), "onupdate": func.now(), "nullable": False})


def one_of(column: str, enum: type[Enum]) -> CheckConstraint:
    """CHECK (column IN (...)) built from a Python enum, named ck_<table>_<column>."""
    values = ", ".join(f"'{member.value}'" for member in enum)
    return CheckConstraint(f"{column} IN ({values})", name=column)
