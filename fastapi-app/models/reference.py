"""Reference data: the box, its cameras, and the people who receive alarm emails."""
from datetime import datetime

from sqlalchemy import CheckConstraint, SmallInteger, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from .base import TIMESTAMPTZ, created_at_field, int_pk, one_of, updated_at_field
from .enums import CountBasis


class Box(SQLModel, table=True):
    """The B4H box. One row today; having it keeps a second box from needing a schema change."""
    __tablename__ = "boxes"

    id: int | None = int_pk()
    name: str = Field(sa_type=String(100))
    base_url: str = Field(sa_type=String(255), unique=True)      # e.g. https://192.168.90.200
    timezone: str = Field(default="Asia/Dhaka", sa_type=String(64))
    is_active: bool = True
    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()


class Camera(SQLModel, table=True):
    """Copy of the box's devices (device_config), refreshed by a sync and created on the fly when an
    event names an unknown device. Soft-deleted so old events and counts keep their camera."""
    __tablename__ = "cameras"
    __table_args__ = (
        UniqueConstraint("box_id", "device_id"),
        one_of("count_basis", CountBasis),
    )

    id: int | None = int_pk()
    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE")
    device_id: int                                                # the box's id (additional.device_id)
    name: str = Field(sa_type=String(100))                        # device_name, e.g. IPCAM-D3
    channel_type: int | None = Field(default=None, sa_type=SmallInteger)   # 1 video, 2 picture
    count_enabled: bool = True
    count_basis: CountBasis = Field(default=CountBasis.MERGED, sa_type=String(10))
    last_synced_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
    deleted_at: datetime | None = Field(default=None, sa_type=TIMESTAMPTZ)
    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()


class Contact(SQLModel, table=True):
    """People who receive alarm emails. Separate from login users: a recipient needs no account.
    The "up to 5 admins per rule" limit is checked in the app, so it can change without a migration."""
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("email"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),   # app stores it lower-cased
    )

    id: int | None = int_pk()
    name: str = Field(sa_type=String(100))
    email: str = Field(sa_type=String(254))
    is_active: bool = True                                        # pause without removing from rules
    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()
