from typing import TYPE_CHECKING

from sqlalchemy import DDL, Boolean, ForeignKey, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .course import Course
    from .program import Program
    from .semester import Semester


class ProgramSemesterCourse(Base):
    __tablename__ = "program_semester_course"
    __table_args__ = (UniqueConstraint("program_id", "course_id"),)
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("program.id"),
        nullable=False,
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semester.id"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id"),
        nullable=False,
    )
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    program: Mapped["Program"] = relationship(init=False)
    semester: Mapped["Semester"] = relationship(init=False)
    course: Mapped["Course"] = relationship(init=False)

    def __repr__(self) -> str:
        return (
            f"ProgramSemesterCourse(id={self.id!r}, semester={self.semester!r},"
            f" course={self.course!r})"
        )


check_semester_number = DDL(
    "CREATE OR REPLACE FUNCTION check_semester_number() "
    "RETURNS TRIGGER AS $$ "
    "DECLARE "
    "duration INT; "
    "semester_number INT; "
    "BEGIN "
    "SELECT program.duration INTO duration FROM program WHERE id = NEW.program_id; "
    "SELECT semester.number INTO semester_number FROM semester"
    " WHERE id = NEW.semester_id; "
    "IF semester_number > duration THEN "
    "RAISE EXCEPTION 'Cannot insert: Semester number is greater"
    " than program duration'; "
    "END IF;"
    "RETURN NEW; "
    "END; $$ LANGUAGE PLPGSQL"
)
before_course_insert = DDL(
    "CREATE TRIGGER before_course_insert BEFORE INSERT ON program_semester_course "
    "FOR EACH ROW EXECUTE PROCEDURE check_semester_number();"
)

event.listen(
    ProgramSemesterCourse.__table__,
    "after_create",
    check_semester_number.execute_if(dialect="postgresql"),
)
event.listen(
    ProgramSemesterCourse.__table__,
    "after_create",
    before_course_insert.execute_if(dialect="postgresql"),
)
