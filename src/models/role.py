from enum import unique
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enum import StringEnum

from .base import Base
from .user_role import user_role

if TYPE_CHECKING:
    from src.models import User


@unique
class RoleName(StringEnum):
    USER = "user"
    STUDENT = "student"
    EDITOR = "editor"
    ROOT = "root"

    def __str__(self):
        return self.value


class Role(Base):
    __tablename__ = "role"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

    users: Mapped[list["User"]] = relationship(
        default_factory=list, secondary=user_role, back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"Role(id={self.id!r}, name={self.name!r})"
