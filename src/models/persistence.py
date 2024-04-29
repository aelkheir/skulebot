from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from src.models import User


class ChatData(Base):
    __tablename__ = "chat_data"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, default=None
    )
    data: Mapped[JSON] = mapped_column(JSON, nullable=False, default=None)

    user: Mapped["User"] = relationship(default=None, back_populates="chat_data")

    def __repr__(self) -> str:
        return f"ChatData(id={self.id!r}, user={self.user!r}, data={self.data!r})"


class UserData(Base):
    __tablename__ = "user_data"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, default=None
    )
    data: Mapped[JSON] = mapped_column(JSON, nullable=False, default=None)

    user: Mapped["User"] = relationship(default=None, back_populates="user_data")

    def __repr__(self) -> str:
        return f"UserData(id={self.id!r}, user={self.user!r}, data={self.data!r})"


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = (UniqueConstraint("name", "key", name="_name_key_uc"),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    new_state: Mapped[str] = mapped_column(String(100), nullable=True, default=None)

    def __repr__(self):
        return f"<Conversation (id={self.id})>"
