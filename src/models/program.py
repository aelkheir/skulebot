from sqlalchemy import Boolean, Integer, String
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src import constants

from .base import Base
from .program_semester import ProgramSemester
from .semester import Semester


class Program(Base):
    __tablename__ = "program"
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    en_name: Mapped[str] = mapped_column(String(50), nullable=False)
    ar_name: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[int] = mapped_column(Boolean, nullable=False, default=True)

    program_semester_associations: Mapped[list["ProgramSemester"]] = relationship(
        init=False,
        back_populates="program",
        cascade="all, delete-orphan",
    )

    semesters: AssociationProxy[list[Semester]] = association_proxy(
        "program_semester_associations",
        "semester",
        creator=lambda semester_obj: ProgramSemester(
            semester=semester_obj, available=True
        ),
        init=False,
    )

    def get_name(self, language_code: str):
        return self.ar_name if language_code == constants.AR else self.en_name

    def __repr__(self) -> str:
        return (
            f"Program(id={self.id!r}, en_name={self.en_name!r},"
            f" number_of_semester={self.duration!r})"
        )
