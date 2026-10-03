"""Reader comments on published BD pages, held for moderation."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from extensions import db


class BdComment(db.Model):
    __tablename__ = "bd_comments"

    id = Column(Integer, primary_key=True)
    bd_slug = Column(String(220), nullable=False, index=True)
    author = Column(String(60), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="pending", index=True)
    ip_digest = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
