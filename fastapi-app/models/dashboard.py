"""Dashboard: per-day numbers that can't be added up from 15-minute buckets (distinct counts)."""
from datetime import date, datetime

from sqlalchemy import Date
from sqlmodel import Field, SQLModel

from .base import updated_at_field


class DailyStat(SQLModel, table=True):
    """One box-local day, recounted from events so distinct dashboard numbers cannot drift."""
    __tablename__ = "daily_stats"

    box_id: int = Field(foreign_key="boxes.id", ondelete="CASCADE", primary_key=True)
    local_date: date = Field(sa_type=Date, primary_key=True)
    tracked_encounters: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    face_encounters: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    body_encounters: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    recognized_encounters: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    stranger_encounters: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    recognized_capture_tracks: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    unique_recognized_people: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    updated_at: datetime = updated_at_field()
