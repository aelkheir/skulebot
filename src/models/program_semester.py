from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .program import Program
    from .semester import Semester


class ProgramSemester(Base):
    __tablename__ = "program_semester"

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)

    program_id: Mapped[int] = mapped_column(ForeignKey("program.id"), default=None)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"), default=None)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    program: Mapped["Program"] = relationship(
        back_populates="program_semester_associations", default=None
    )
    semester: Mapped["Semester"] = relationship(default=None)

    __table_args__ = (
        UniqueConstraint("program_id", "semester_id", name="_program_semester_uc"),
    )
