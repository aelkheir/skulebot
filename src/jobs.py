import contextlib
import datetime
from zoneinfo import ZoneInfo

from babel.dates import format_timedelta
from sqlalchemy import and_, select
from sqlalchemy.orm import aliased
from telegram import InlineKeyboardMarkup
from telegram.error import Forbidden

from src import constants
from src.buttons import ar_buttons, en_buttons
from src.customcontext import CustomContext
from src.database import Session
from src.models import Assignment
from src.models.course import Course
from src.models.enrollment import Enrollment
from src.models.program_semester import ProgramSemester
from src.models.program_semester_course import ProgramSemesterCourse
from src.models.semester import Semester
from src.models.user import User
from src.utils import user_locale


def remove_job_if_exists(name: str, context: CustomContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def deadline_reminder(context: CustomContext):
    job = context.job
    await context.bot.send_message(
        job.chat_id,
        text=context.gettext("Started assignment deadline reminders"),
        disable_notification=True,
    )
    current_time = datetime.datetime.now(datetime.UTC)
    with Session.begin() as session:
        assignments: list[Assignment] = session.scalars(
            select(Assignment).where(
                Assignment.published,
                Assignment.deadline is not None,
                Assignment.deadline > current_time,
                and_(
                    and_(
                        Assignment.deadline
                        >= current_time + datetime.timedelta(hours=36),
                        Assignment.deadline
                        < current_time + datetime.timedelta(hours=48),
                    ),
                ),
            )
        ).all()
        when = 2
        for i, assignment in enumerate(assignments):
            sub_semester = aliased(Semester)
            sub_program_semester = aliased(ProgramSemester)
            academic_year_id = assignment.academic_year_id
            users: list[User] = session.scalars(
                select(User)
                .select_from(Assignment)
                .join(Course)
                .join(ProgramSemesterCourse)
                .join(
                    ProgramSemester,
                    and_(
                        ProgramSemester.program_id == ProgramSemesterCourse.program_id,
                        ProgramSemester.semester_id
                        == ProgramSemesterCourse.semester_id,
                    ),
                )
                .join(Semester)
                .join(
                    Enrollment,
                    Enrollment.program_semester_id.in_(
                        select(sub_program_semester.id)
                        .join(sub_semester)
                        .where(
                            sub_program_semester.program_id
                            == ProgramSemester.program_id,
                            sub_semester.number.in_(
                                [
                                    Semester.number,
                                    Semester.number
                                    + (1 if Semester.number % 2 == 1 else -1),
                                ]
                            ),
                        )
                        .subquery()
                    ),
                )
                .join(User, Enrollment.user_id == User.id)
                .where(
                    Assignment.id == assignment.id,
                    Enrollment.academic_year_id == academic_year_id,
                )
                .group_by(User)
            ).all()
            zone = ZoneInfo("Africa/Khartoum")
            delta = assignment.deadline.astimezone(zone) - datetime.datetime.now(zone)
            session.expunge(assignment)
            for ii, user in enumerate(users):
                JOBNAME = f"REMIND_{user.telegram_id}_{assignment.id}"
                session.expunge(user)
                is_last = i == len(assignments) - 1 and ii == len(users) - 1
                remove_job_if_exists(JOBNAME, context)
                context.job_queue.run_once(
                    send_reminder,
                    when=when,
                    name=JOBNAME,
                    data={
                        "user": user,
                        "assignment": assignment,
                        "delta": delta,
                        "is_last": is_last,
                    },
                    chat_id=job.chat_id,
                    user_id=job.user_id,
                )
                when += 2.5
        if len(assignments) == 0:
            await context.bot.send_message(
                job.chat_id,
                text=context.gettext("Done! No reminders to send"),
                disable_notification=True,
            )


async def send_reminder(context: CustomContext) -> None:
    """Send the notification message."""
    job = context.job

    user: User = job.data["user"]
    assignment: Assignment = job.data["assignment"]
    delta: datetime.timedelta = job.data["delta"]
    is_last: bool = job.data["is_last"]

    # Get language for user to be notified
    translation = user_locale(user.language_code)
    gettext = translation.gettext

    seconds = delta.total_seconds()
    days = seconds // (24 * 60 * 60)
    hours = (seconds // (60 * 60)) % 24
    parts = [
        format_timedelta(
            datetime.timedelta(days=days),
            granularity="days",
            format="long",
            threshold=1,
            locale=user.language_code,
        ),
        format_timedelta(
            datetime.timedelta(hours=hours),
            granularity="hours",
            format="long",
            threshold=1,
            locale=user.language_code,
        ),
    ]

    buttons = ar_buttons if user.language_code == constants.AR else en_buttons

    with Session.begin() as session:
        session.add_all([assignment, user])
        course_name = assignment.course.get_name(user.language_code)
        assignment_title = gettext(assignment.type) + f" {assignment.number}"
        remaining = gettext("time remaining {} {}").format(*parts)

        with contextlib.suppress(Forbidden):
            message = (
                "⏰ "
                + gettext("Reminder")
                + "\n\n"
                + gettext("{} of {} is due in {}").format(
                    assignment_title, course_name, remaining
                )
            )

            keyboard = [
                [
                    buttons.show_more(
                        f"{constants.REMINDER_}/{assignment.type}/{assignment.id}",
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                user.chat_id, text=message, reply_markup=reply_markup
            )

    _ = context.gettext
    if is_last:
        await context.bot.send_message(
            job.chat_id, text=_("Done sending reminders"), disable_notification=True
        )
