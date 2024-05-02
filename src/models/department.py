from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src import constants

from .base import Base

if TYPE_CHECKING:
    from .course import Course


class Department(Base):
    __tablename__ = "department"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    en_name: Mapped[str] = mapped_column(String(50), nullable=False)
    ar_name: Mapped[str] = mapped_column(String(50), nullable=False)

    courses: Mapped[list["Course"]] = relationship(
        init=False, default_factory=list, back_populates="department"
    )

    def get_name(self, language_code: str):
        return self.ar_name if language_code == constants.AR else self.en_name

    def __repr__(self) -> str:
        return f"Department(id={self.id!r}, en_name={self.en_name!r})"
