from typing import List, Optional, Sequence, Union

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.models import (
    AcademicYear,
    Department,
    Enrollment,
    Program,
    ProgramSemester,
    Role,
    RoleName,
    Semester,
    User,
)
from src.models.access_request import AccessRequest, Status
from src.models.course import Course
from src.models.material import Lecture, Material
from src.models.program_semester_course import ProgramSemesterCourse
from src.models.user_optional_course import UserOptionalCourse


def semesters(
    session: Session, program_id: Optional[int] = None, level: Optional[int] = None
) -> list[Semester]:
    """
    Query multiple :class:`Semester`s.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        program_id (:obj:`int`, optional): If present, will return the semesters whose
            numbers falls within this program's duration.
        level (:obj:`int`, optional): An integer denoting the range of semesters
            to return.

    Examples:
        * `level` set to `2` will return `Semester 3` and `Semester 4`
        * `level` set to `4` will return `Semester 7` and `Semester 8`

    Raises:
        `ValueError` when providing :paramref:`level` without specifing
          a :paramref:`program_id`


    Returns:
        List[:obj:`Semester`]

    """

    if level is not None and program_id is None:
        raise ValueError("cannot specify a level without specifing a `program_id`")

    if level is not None and program_id is not None:
        semesters = (
            session.query(Semester)
            .where(
                and_(
                    Program.id == program_id,
                    or_(Semester.number == level * 2, Semester.number == level * 2 - 1),
                )
            )
            .order_by(Semester.number)
            .all()
        )
    elif program_id is not None:
        semesters = (
            session.query(Semester)
            .where(Program.id == program_id, Semester.number <= Program.duration)
            .order_by(Semester.number)
            .all()
        )
    else:
        semesters = session.query(Semester).order_by(Semester.number).all()
    return semesters


def semester(
    session: Session,
    semester_id: Optional[int] = None,
    semester_number: Optional[int] = None,
) -> Semester:
    """
    Query a single :class:`Semester`

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        semester_id (:obj:`int`, optional): Filter with semester id. Mutally exclusive
            with :paramref:`semester_number`
        semester_number (:obj:`int`, optional): Filter with semester number. Mutally
            exclusive with :paramref:`semester_id`

    Raises:
        `ValueError` when providing both :paramref:`semester_id` and
          :paramref:`semester_number`

    Returns:
        :obj:`Semester`

    """
    return (
        session.query(Semester)
        .where(or_(Semester.id == semester_id, Semester.number == semester_number))
        .one()
    )


def user(
    session: Session,
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> Union[User, None]:
    """
    Query a single :obj:`User`

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`): The user id.
        telegram_id (:obj:`int`): The user telegram id.

    Returns:
        :obj:`User`
    """
    if user_id is None and telegram_id is None:
        raise ValueError("must provide either `user_id` or `telegram_id`.")
    if user_id and telegram_id is not None:
        raise ValueError("user_id and `telegram_id` are mutally exclusive.")

    if user_id:
        return session.query(User).where(User.id == user_id).one()

    return session.scalar(select(User).where(User.telegram_id == telegram_id))


def role(session: Session, role_name: RoleName) -> Role:
    """
    Query a single :obj:`Role`

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        role_name (:obj:`RoleName`): The role name.

    Returns:
        :obj:`User`
    """
    return session.scalar(select(Role).where(Role.name == role_name))


def access_requests(
    session: Session,
    status: Optional[Union[Status, Sequence[Status]]] = None,
) -> List[AccessRequest]:
    """
    Query all :obj:`AccessRequest`s.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        status (Union[Status, Sequence[Status]], optional): `AccessRequest.status` to
            filter against

    Returns:
        List[:obj:`AccessRequest`]
    """
    if status and isinstance(status, Status):
        status = (status,)
    filters = []
    if status is not None:
        filters.append(AccessRequest.status.in_(status))

    return session.scalars(select(AccessRequest).filter(*filters)).all()


def access_request(
    session: Session,
    access_request_id: int,
) -> AccessRequest:
    """
    Query a single :obj:`AccessRequest`s.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        access_request_id (:obj:`int`): The id of the access_request.

    Returns:
        :obj:`AccessRequest`
    """
    return session.get(AccessRequest, access_request_id)


def user_access_requests(
    session: Session,
    user_id: int,
    status: Optional[Union[Status, Sequence[Status]]] = None,
) -> List[AccessRequest]:
    """
    Query muliple :obj:`AccessRequest`s of a specific user.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`): The user id.
        status (Union[Status, Sequence[Status]], optional): `AccessRequest.status` to
            filter against

    Returns:
        List[:obj:`AccessRequest`]
    """
    if status and isinstance(status, Status):
        status = (status,)
    filters = []
    if status is not None:
        filters.append(AccessRequest.status.in_(status))

    return session.scalars(
        select(AccessRequest)
        .join(Enrollment, AccessRequest.enrollment_id == Enrollment.id)
        .where(Enrollment.user_id == user_id)
        .filter(*filters)
    ).all()


def user_most_recent_access(
    session: Session,
    user_id: int,
) -> AccessRequest:
    """
    Query a single :obj:`AccessRequest`

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`): The user id.

    Returns:
        :obj:`AccessRequest`
    """
    return session.scalar(
        select(AccessRequest)
        .join(Enrollment)
        .join(ProgramSemester)
        .join(Semester)
        .join(AcademicYear)
        .where(Enrollment.user_id == user_id)
        .filter(AccessRequest.status == Status.GRANTED)
        .order_by(AcademicYear.start.desc(), Semester.number.desc())
    )


def programs(session: Session):
    """
    Query all :obj:`Program`s

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.

    Returns:
        List[:obj:`Program`]
    """
    return session.query(Program).all()


def program(session: Session, program_id: int) -> Program:
    """
    Query a single :obj:`Program`

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        program_id (:obj:`int`): The program id.

    Returns:
        :obj:`Program`
    """
    return session.get(Program, program_id)


def departments(session: Session) -> list[Department]:
    """
    Query all :obj:`Departments`s

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.

    Returns:
        list[:obj:`Department`]

    """
    return session.query(Department).all()


def department(session: Session, department_id: int) -> Department:
    """
    Query a single :obj:`Department`

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        department_id (:obj:`int`): The department id.

    Returns:
        :obj:`Department`

    """
    return session.get(Department, department_id)


def course(session: Session, course_id: int) -> Course:
    """
    Query a single :obj:`Course`

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        course_id (:obj:`int`): The course id.

    Returns:
        :obj:`Course`

    """
    return session.get(Course, course_id)


def user_courses(
    session: Session, program_id: int, semester_id: int, user_id: int
) -> List[Course]:
    """
    Query multiple :obj:`Course`s that are relevant to user in a specific program
    and smemster. This will  include all required courses plus optional courses that
    user has selected.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        program_id (:obj:`int`): The program id.
        semester_id (:obj:`int`): The semester id.
        user_id (:obj:`int`): The user id.

    Returns:
        :obj:`Course`

    """
    return session.scalars(
        select(Course)
        .select_from(ProgramSemesterCourse)
        .outerjoin(
            UserOptionalCourse,
            (UserOptionalCourse.program_semester_course_id == ProgramSemesterCourse.id)
            & (UserOptionalCourse.user_id == user_id),
        )
        .join(Course)
        .where(
            and_(
                ProgramSemesterCourse.program_id == program_id,
                ProgramSemesterCourse.semester_id == semester_id,
                or_(
                    ProgramSemesterCourse.optional == False,  # noqa: E712
                    and_(
                        (ProgramSemesterCourse.optional == True),  # noqa: E712
                        (
                            UserOptionalCourse.program_semester_course_id
                            == ProgramSemesterCourse.id
                        ),
                    ),
                ),
            ),
        )
        .order_by(ProgramSemesterCourse.optional, Course.en_name)
    ).all()


def academic_years(session: Session) -> List[AcademicYear]:
    """
    Query all :obj:`AcademicYear`s

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.

    Returns:
        List[:obj:`AcademicYear`]

    """
    return session.query(AcademicYear).order_by(AcademicYear.start.desc()).all()


def academic_year(
    session: Session, year_id: Optional[int] = None, most_recent: Optional[bool] = None
) -> AcademicYear:
    """
    Query a single :class:`AcademicYear`

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        year_id (:obj:`int`, optional): Filter with academ year id. Mutally exclusive
            with :paramref:`most_recent`
        most_recent (:obj:`bool`, optional): Get the most recent year. Mutally
            exclusive with :paramref:`year_id`

    Raises:
        `ValueError` when providing both or neither of :paramref:`year_id` and
          :paramref:`most_recent`

    Returns:
        :obj:`AcademicYear`

    """
    if year_id is None and most_recent is None:
        raise ValueError("must provide either `year_id` or `most_recent`.")
    if year_id and most_recent is not None:
        raise ValueError("year_id and `most_recent` are mutally exclusive.")

    if year_id is not None:
        return session.get(AcademicYear, year_id)

    return session.query(AcademicYear).order_by(AcademicYear.start.desc()).first()


def user_enrollments(session: Session, user_id: int) -> List[Enrollment]:
    """
    Query :class:`Enrollment`s of a particular user sorted descendingly by
    `academic_year.start`.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`, optional): Filter with user id.r_id`

    Returns:
        List[:obj:`Enrollment`:

    """
    return (
        session.query(Enrollment)
        .join(AcademicYear)
        .where(Enrollment.user_id == user_id)
        .order_by(AcademicYear.start.desc())
        .all()
    )


def user_most_recent_enrollment(session: Session, user_id: int) -> Enrollment:
    """
    Query the most recent :class:`Enrollment`.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`, optional): Filter with user id.r_id`

    Returns:
        :obj:`Enrollment`:

    """
    return (
        session.query(Enrollment)
        .join(AcademicYear)
        .where(Enrollment.user_id == user_id)
        .order_by(AcademicYear.start.desc())
        .first()
    )


def enrollment(session: Session, enrollment_id: int) -> Enrollment:
    """
    Query a single :obj:`Enrollment` by id.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        enrollment_id (:obj:`int`): The enrollment id.

    Returns:
        :obj:`Enrollment`
    """
    return session.get(Enrollment, enrollment_id)


def department_courses(
    session: Session, department_id: Optional[int] = None
) -> List[Course]:
    """
    Query multiple :obj:`Course`s of a particular `Department` sorted descendingly by
    `Course.en_name`.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        department_id (:obj:`int`, optional): The department id to filter against`

    Returns:
        List[:obj:`Course`]:

    """
    return session.scalars(
        select(Course)
        .where(Course.department_id == department_id)
        .order_by(Course.en_name)
    ).all()


def has_optional_courses(
    session: Session,
    program_id: int,
    semester_id: int,
) -> bool:
    """
    Return wheather a program has at least one optional course in a given semester.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        program_id (:obj:`int`, optional): The id of the program.
        semester_id (:obj:`int`, optional): The id of the semester.

    Returns:
        :obj:`bool`:

    """
    return session.query(
        session.query(ProgramSemesterCourse)
        .filter(
            and_(
                ProgramSemesterCourse.program_id == program_id,
                ProgramSemesterCourse.semester_id == semester_id,
                ProgramSemesterCourse.optional == True,  # noqa: E712
            )
        )
        .exists()
    ).scalar()


def program_semester_courses(
    session: Session,
    program_id: int,
    semester_id: Optional[int] = None,
    optional: Optional[bool] = None,
) -> List[ProgramSemesterCourse]:
    """
    Query multiple :obj:`ProgramSemesterCourse`s of a particular `Program` and
    in a particular `Semester`.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        program_id (:obj:`int`, optional): The program id to filter against`
        semester_id (:obj:`int`, optional): The semester id to filter against`

    Returns:
        List[:obj:`ProgramSemesterCourse`]:

    """
    filters = []
    if optional is not None:
        filters.append(ProgramSemesterCourse.optional == optional)
    if program_id is not None and semester_id is None:
        filters.append(
            ProgramSemesterCourse.program_id == program_id,
        )
    if program_id is not None and semester_id is not None:
        filters.append(
            and_(
                ProgramSemesterCourse.program_id == program_id,
                ProgramSemesterCourse.semester_id == semester_id,
            )
        )

    return session.query(ProgramSemesterCourse).filter(*filters)


def program_semester_course(
    session: Session,
    program_semester_course_id: Optional[int] = None,
    program_id: Optional[int] = None,
    course_id: Optional[int] = None,
) -> ProgramSemesterCourse:
    """
    Query a single :obj:`ProgramSemesterCourse` by id.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        program_semester_course_id (:obj:`int`, optional): The id to filter against.

    Returns:
        List[:obj:`ProgramSemesterCourse`]:

    """
    if program_semester_course_id is not None and any([program_id, course_id]):
        raise ValueError("id is mutally exclusive with with other parameters")
    if program_semester_course_id is None and not all([program_id, course_id]):
        raise ValueError("must provide all of program_id and course_id")

    if program_semester_course_id:
        return session.get(ProgramSemesterCourse, program_semester_course_id)

    return session.scalar(
        select(ProgramSemesterCourse).filter(
            ProgramSemesterCourse.program_id == program_id,
            ProgramSemesterCourse.course_id == course_id,
        )
    )


def program_semesters(
    session: Session,
    program_id: int,
    available: Optional[bool] = None,
    level: Optional[int] = None,
) -> List[ProgramSemester]:
    """
    Query multiple :obj:`ProgramSemester`s.

    Args:
        session (:class:`Session`): An `sqlalchemy.orm.Session` instance.
        program_id (:obj:`int`, optional): The program id to filter against.
        available (:obj:`bool`, optional): `ProgramSemester.available` value to
            filter against`
        level (:obj:`int`, optional): An integer denoting the range of semesters
            to return

    Returns:
        List[:obj:`ProgramSemester`]:

    """
    filters = []
    if available is not None:
        filters.append(ProgramSemester.available == available)
    if level is not None:
        filters.append(
            or_(Semester.number == level * 2, Semester.number == level * 2 - 1)
        )
    return (
        session.query(ProgramSemester)
        .join(Semester)
        .join(Program)
        .where(Program.id == program_id)
        .filter(*filters)
        .order_by(Semester.number)
        .all()
    )


def program_semester(
    session: Session,
    program_semester_id: Optional[int] = None,
    program_id: Optional[int] = None,
    semester_id: Optional[int] = None,
) -> ProgramSemester:
    """
    Query a single :obj:`ProgramSemester`.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        program_semester_id (:obj:`int`) The id of `ProgramSemester`. Mutally exclusive
            with other parameters.
        program_id (:obj:`int`): The program id.
        semester_id (:obj:`int`): The semester id.

    Returns:
        :obj:`ProgramSemester`
    """
    if program_semester_id is not None and any([program_id, semester_id]):
        raise ValueError(
            "program_semester_id is mutally exclusive with with other parameters"
        )
    if program_semester_id is None and not all([program_id, semester_id]):
        raise ValueError("must provide both program_id semester_id")

    if program_semester_id:
        return session.get(ProgramSemester, program_semester_id)

    return (
        session.query(ProgramSemester)
        .where(
            and_(
                ProgramSemester.program_id == program_id,
                ProgramSemester.semester_id == semester_id,
            )
        )
        .one_or_none()
    )


def course_material_types(session: Session, course_id: int, year_id: int) -> List[str]:
    """
    Query :obj:`Material.type`s of a given course in a given  year.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        course_id (:obj:`int`) The course id.
        year_id (:obj:`int`): The year id.

    Returns:
        List[:obj:`str`]
    """
    return session.scalars(
        select(Material.type)
        .where(Material.course_id == course_id, Material.academic_year_id == year_id)
        .group_by(Material.type)
    ).all()


def lectures(session: Session, course_id: int, year_id: int) -> List[str]:
    """
    Query :obj:`Lecture`s of a given course in a given  year.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        course_id (:obj:`int`) The course id.
        year_id (:obj:`int`): The year id.

    Returns:
        List[:obj:`str`]
    """
    return session.scalars(
        select(Lecture)
        .where(
            Lecture.course_id == course_id,
            Lecture.academic_year_id == year_id,
        )
        .order_by(Lecture.number)
    ).all()


def user_optional_courses(session: Session, user_id: int) -> List[UserOptionalCourse]:
    """
    Query multiple :obj:`UserOptionalCourse`s of a given user.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`) The user id.

    Returns:
        List[:obj:`UserOptionalCourse`]
    """
    return session.scalars(
        select(UserOptionalCourse).filter(UserOptionalCourse.user_id == user_id)
    ).all()


def user_optional_course(
    session: Session, user_id: int, programs_semester_course_id: int
) -> UserOptionalCourse:
    """
    Query a single :obj:`UserOptionalCourse` of a given user.

    Args:
        session (:obj:`Session`): An `sqlalchemy.orm.Session` instance.
        user_id (:obj:`int`) The user id.
        programs_semester_course_id (:obj:`int`) The ProgramSemesterCourse id.

    Returns:
        :obj:`UserOptionalCourse`
    """
    return session.scalar(
        select(UserOptionalCourse).filter(
            UserOptionalCourse.user_id == user_id,
            UserOptionalCourse.program_semester_course_id
            == programs_semester_course_id,
        )
    )
