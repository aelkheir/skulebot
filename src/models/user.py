from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src import constants

from .base import Base
from .user_role import user_role

if TYPE_CHECKING:
    from src.models import Role

    from .enrollment import Enrollment
    from .persistence import ChatData, UserData
    from .setting import Setting


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    language_code: Mapped[str] = mapped_column(
        String(5), nullable=False, default=constants.EN
    )

    roles: Mapped[list["Role"]] = relationship(
        default_factory=list,
        secondary=user_role,
        back_populates="users",
    )

    enrollments: Mapped[list["Enrollment"]] = relationship(
        default_factory=list, back_populates="user", cascade="all, delete-orphan"
    )

    settings: Mapped[list["Setting"]] = relationship(
        default_factory=list, cascade="all, delete-orphan", back_populates="user"
    )

    chat_data: Mapped["ChatData"] = relationship(
        init=False, back_populates="user", cascade="all"
    )
    user_data: Mapped["UserData"] = relationship(
        init=False, back_populates="user", cascade="all"
    )

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, telegram_id={self.telegram_id!r},"
            f" roles={self.roles!r})"
        )
