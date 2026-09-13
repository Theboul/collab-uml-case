from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class BackupUMLRecord(Base):
    __tablename__ = "uml_api_backupuml"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(36), unique=True, nullable=False, index=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<BackupUMLRecord(room_id='{self.room_id}')>"
