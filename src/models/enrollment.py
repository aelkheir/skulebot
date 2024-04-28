from typing import TYPE_CHECKING

from sqlalchemy import DDL, ForeignKey, UniqueConstraint, event
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .program_semester import ProgramSemester

if TYPE_CHECKING:
    from .academic_year import AcademicYear
    from .access_request import AccessRequest
    from .program import Program
    from .semester import Semester
    from .user import User


class Enrollment(Base):
    __tablename__ = "enrollment"
    __table_args__ = (
        UniqueConstraint("user_id", "academic_year_id", name="_user_academic_year_uc"),
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        nullable=False,
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_year.id"),
        nullable=False,
    )
    program_semester_id: Mapped[int] = mapped_column(
        ForeignKey("program_semester.id"), nullable=False
    )

    user: Mapped["User"] = relationship(init=False, back_populates="enrollments")
    access_request: Mapped["AccessRequest"] = relationship(
        init=False,
        back_populates="enrollment",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    academic_year: Mapped["AcademicYear"] = relationship(init=False)
    program_semester: Mapped["ProgramSemester"] = relationship(init=False)

    program: AssociationProxy["Program"] = association_proxy(
        "program_semester",
        "program",
        creator=lambda program_obj: ProgramSemester(program=program_obj),
        init=False,
    )

    semester: AssociationProxy["Semester"] = association_proxy(
        "program_semester",
        "semester",
        creator=lambda semester_obj: ProgramSemester(semester=semester_obj),
        init=False,
    )

    def __repr__(self) -> str:
        return (
            f"Enrolment(id={self.id!r}, user={self.user.id!r},"
            f" program={self.program.en_name!r}, semeser={self.semester!r},"
            f" academic_year={self.academic_year!r})"
        )


check_odd_semester = DDL(
    "CREATE OR REPLACE FUNCTION check_odd_semester() "
    "RETURNS TRIGGER AS $$ "
    "DECLARE "
    "semester_number INT; "
    "BEGIN "
    "SELECT s.number INTO semester_number FROM program_semester AS ps "
    "INNER JOIN semester as s ON ps.semester_id = s.id "
    "WHERE ps.id = NEW.program_semester_id; "
    "IF MOD(semester_number, 2) = 0 THEN "
    "RAISE EXCEPTION 'Cannot insert: Semester number must be odd'; "
    "END IF;"
    "RETURN NEW; "
    "END; $$ LANGUAGE PLPGSQL"
)
odd_semester = DDL(
    "CREATE TRIGGER odd_semester BEFORE INSERT ON enrollment "
    "FOR EACH ROW EXECUTE PROCEDURE check_odd_semester();"
)


check_semester_sequence = DDL(
    "CREATE OR REPLACE FUNCTION check_semester_sequence() "
    "RETURNS TRIGGER AS $$ "
    "DECLARE "
    "old_semester_number INT; "
    "new_semester_number INT; "
    "BEGIN "
    "SELECT s.number INTO old_semester_number FROM program_semester AS ps "
    "INNER JOIN semester as s ON ps.semester_id = s.id "
    "WHERE ps.id = OLD.program_semester_id; "
    "SELECT s.number INTO new_semester_number FROM program_semester AS ps "
    "INNER JOIN semester as s ON ps.semester_id = s.id "
    "WHERE ps.id = NEW.program_semester_id; "
    "IF NOT ("
    "(new_semester_number = old_semester_number + 1 "
    "AND MOD(new_semester_number, 2) = 0) OR "
    "(new_semester_number = old_semester_number - 1 "
    "AND MOD(new_semester_number, 2) = 1) OR "
    "(new_semester_number = old_semester_number) "
    ") THEN "
    "RAISE EXCEPTION 'Cannot update: New semester must be "
    "either the next or the previous semester within the same academic year'; "
    "END IF;"
    "RETURN NEW; "
    "END; $$ LANGUAGE PLPGSQL"
)
semester_sequence = DDL(
    "CREATE TRIGGER semester_sequence BEFORE UPDATE ON enrollment "
    "FOR EACH ROW EXECUTE PROCEDURE check_semester_sequence();"
)

check_program_change = DDL(
    "CREATE OR REPLACE FUNCTION check_program_change() "
    "RETURNS TRIGGER AS $$ "
    "DECLARE "
    "old_program_id INT; "
    "new_program_id INT; "
    "BEGIN "
    "SELECT program_id INTO old_program_id FROM program_semester AS ps "
    "WHERE ps.id = OLD.program_semester_id; "
    "SELECT program_id INTO new_program_id FROM program_semester AS ps "
    "WHERE ps.id = NEW.program_semester_id; "
    "IF ("
    "(new_program_id != old_program_id) "
    ") THEN "
    "RAISE EXCEPTION 'Cannot update: different program_id detected'; "
    "END IF;"
    "RETURN NEW; "
    "END; $$ LANGUAGE PLPGSQL"
)
program_change = DDL(
    "CREATE TRIGGER program_change BEFORE UPDATE ON enrollment "
    "FOR EACH ROW EXECUTE PROCEDURE check_program_change();"
)

event.listen(
    Enrollment.__table__,
    "after_create",
    check_odd_semester.execute_if(dialect="postgresql"),
)
event.listen(
    Enrollment.__table__,
    "after_create",
    odd_semester.execute_if(dialect="postgresql"),
)

event.listen(
    Enrollment.__table__,
    "after_create",
    check_semester_sequence.execute_if(dialect="postgresql"),
)
event.listen(
    Enrollment.__table__,
    "after_create",
    semester_sequence.execute_if(dialect="postgresql"),
)

event.listen(
    Enrollment.__table__,
    "after_create",
    check_program_change.execute_if(dialect="postgresql"),
)
event.listen(
    Enrollment.__table__,
    "after_create",
    program_change.execute_if(dialect="postgresql"),
)
