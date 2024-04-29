import enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import MaterialType

from .base import Base

if TYPE_CHECKING:
    from .user import User


class SettingKey(enum.Enum):
    # Class variable for the notification prefix
    NOTIFICATION_PREFIX = "notification."

    # Enum members with (key, default value) as their values
    # Notification settings will automatically prepend the prefix
    LECTURE = (NOTIFICATION_PREFIX + MaterialType.LECTURE, True)
    TUTORIAL = (NOTIFICATION_PREFIX + MaterialType.TUTORIAL, True)
    LAB = (NOTIFICATION_PREFIX + MaterialType.LAB, True)
    REFERENCE = (NOTIFICATION_PREFIX + MaterialType.REFERENCE, True)
    SHEET = (NOTIFICATION_PREFIX + MaterialType.SHEET, True)
    TOOL = (NOTIFICATION_PREFIX + MaterialType.TOOL, True)
    ASSIGNMENT = (NOTIFICATION_PREFIX + MaterialType.ASSIGNMENT, True)
    REVIEW = (NOTIFICATION_PREFIX + MaterialType.REVIEW, True)

    def __init__(self, key, default=None):
        self.key: str = key
        self.default = default

    @classmethod
    def get_notification_keys(cls):
        """Return a list of keys that are for notifications."""
        return [
            setting
            for setting in cls
            if setting.key.startswith(cls.NOTIFICATION_PREFIX.key)
            and setting.key != cls.NOTIFICATION_PREFIX.key
        ]


class Setting(Base):
    __tablename__ = "setting"
    __table_args__ = (UniqueConstraint("user_id", "key", name="_user_key_uc"),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    value: Mapped = mapped_column(JSON, nullable=False)
    user: Mapped["User"] = relationship(
        init=False, back_populates="settings", default=None
    )

    def __repr__(self) -> str:
        return (
            f"Setting(id={self.id!r}, key={self.key!r},"
            f" value={self.value!r}, user={self.user!r})"
        )
