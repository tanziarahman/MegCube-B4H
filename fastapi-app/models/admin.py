"""Admin: non-secret settings and the audit trail."""
from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from .base import bigint_pk, created_at_field, updated_at_field


class AppSetting(SQLModel, table=True):
    """Settings that aren't secret: email "from" name, portal URL for links, retention days,
    polling interval, stranger-match threshold, ..."""
    __tablename__ = "app_settings"

    key: str = Field(sa_type=String(100), primary_key=True)
    value: dict | list | str | int | float | bool | None = Field(default=None, sa_type=JSONB)
    updated_at: datetime = updated_at_field()
    updated_by: str | None = Field(default=None, sa_type=String(100))


class AuditLog(SQLModel, table=True):
    """Who changed rules, recipients or settings, and who acknowledged incidents."""
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id", "at"),)

    id: int | None = bigint_pk()
    at: datetime = created_at_field()
    actor: str | None = Field(default=None, sa_type=String(100))   # a user FK once auth exists
    action: str = Field(sa_type=String(50))                        # create / update / delete / acknowledge
    entity_type: str = Field(sa_type=String(50))
    entity_id: str = Field(sa_type=String(64))
    before: dict | None = Field(default=None, sa_type=JSONB)
    after: dict | None = Field(default=None, sa_type=JSONB)
