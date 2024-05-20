from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class File(Base):
    __tablename__ = "file"

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    telegram_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=True, default=None)

    material_id: Mapped[int] = mapped_column(
        ForeignKey("material.id"),
        default=None,
        nullable=True,
    )
    uploader_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        default=None,
        nullable=False,
    )

    uploader: Mapped["User"] = relationship(default=None)

    def __repr__(self) -> str:
        return f"File(id={self.id!r}, type={self.type!r}, name={self.name!r}) "
