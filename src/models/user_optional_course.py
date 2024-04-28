from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .program_semester_course import ProgramSemesterCourse
    from .user import User


class UserOptionalCourse(Base):
    __tablename__ = "user_optional_course"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "program_semester_course_id",
            name="_user_program_semester_course_uc",
        ),
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, default=None
    )
    program_semester_course_id: Mapped[int] = mapped_column(
        ForeignKey("program_semester_course.id"), nullable=False, default=None
    )

    user: Mapped["User"] = relationship(default=None)
    program_semester_course: Mapped["ProgramSemesterCourse"] = relationship(
        default=None
    )
