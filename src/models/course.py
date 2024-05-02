from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src import constants

from .base import Base

if TYPE_CHECKING:
    from .department import Department


class Course(Base):
    __tablename__ = "course"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    en_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ar_name: Mapped[str] = mapped_column(String(100), nullable=False)
    en_code: Mapped[str] = mapped_column(String(30), nullable=True, default=None)
    ar_code: Mapped[str] = mapped_column(String(30), nullable=True, default=None)
    credits: Mapped[int] = mapped_column(Integer, nullable=True, default=None)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id"),
        default=None,
        nullable=True,
    )
    department: Mapped["Department"] = relationship(
        back_populates="courses", default=None
    )

    def get_name(self, language_code: str):
        return self.ar_name if language_code == constants.AR else self.en_name

    def __repr__(self) -> str:
        return (
            f"Course(id={self.id!r}, en_name={self.en_name!r},"
            f" department={self.department!r})"
        )
