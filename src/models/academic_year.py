from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AcademicYear(Base):
    __tablename__ = "academic_year"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"AcademicYear(id={self.id!r}, start={self.start!r}, end={self.end!r})"
