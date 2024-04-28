from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Semester(Base):
    __tablename__ = "semester"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"Semester(id={self.id!r}, number={self.number!r})"
