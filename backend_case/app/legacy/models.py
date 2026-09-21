import sys
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

if "backend_case.app.legacy.models" not in sys.modules:
    sys.modules["backend_case.app.legacy.models"] = sys.modules[__name__]
if "app.legacy.models" not in sys.modules:
    sys.modules["app.legacy.models"] = sys.modules[__name__]


class BackupUMLRecord(Base):
    __tablename__ = "uml_api_backupuml"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(36), unique=True, nullable=False, index=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<BackupUMLRecord(room_id='{self.room_id}')>"
