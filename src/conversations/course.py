import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from babel.dates import format_datetime
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ConversationHandler

from src import commands, constants, messages, queries
from src.conversations.material import files, material, sendall
from src.customcontext import CustomContext
from src.models import (
    Assignment,
    MaterialType,
    ProgramSemesterCourse,
    Semester,
    UserOptionalCourse,
)
from src.utils import build_menu, session, time_remaining

# ------------------------------- entry_points ---------------------------


@session
async def course(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data `{PREFIX}/{constants.COURSES}/(?P<course_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    match = re.search(
        PREFIX,
        context.match.group(),
    )
    url = match.group()

    course_id = context.match.group("course_id")
    enrollment_id = context.match.group("enrollment_id")
    enrollment = queries.enrollment(session, enrollment_id)
    material_groups = queries.course_material_types(
        session, course_id=course_id, year_id=enrollment.academic_year_id
    )
    course = queries.course(session, course_id)

    lectures = (
        queries.lectures(
            session, course_id=course_id, year_id=enrollment.academic_year_id
        )
        if MaterialType.LECTURE in material_groups
        else []
    )
    menu = context.buttons.material_list(f"{url}/{MaterialType.LECTURE}", lectures)
    keyboard = build_menu(menu, 3, reverse=context.language_code == constants.AR)

    keyboard.extend(
        context.buttons.material_groups(
            url,
            groups=[m for m in material_groups if m != MaterialType.LECTURE],
        )
    )

    keyboard += [[context.buttons.back(url, "/(\d+)$")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = (
        messages.title(context.match, session, context=context)
        + "\n"
        + _("t-symbol")
        + "─ "
        + course.get_name(context.language_code)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def deadlines(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data `{PREFIX}/{constants.COURSES}/(?P<course_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    if constants.IGNORE in url:
        return constants.ONE

    enrollment_id = context.match.group("enrollment_id")
    enrollment = queries.enrollment(session, enrollment_id)
    semester_number = enrollment.semester.number
    semester_numbers = [
        enrollment.semester.number,
        semester_number + (1 if semester_number % 2 == 1 else -1),
    ]
    _ = context.gettext

    assignments = session.scalars(
        select(Assignment)
        .join(
            ProgramSemesterCourse,
            and_(
                ProgramSemesterCourse.course_id == Assignment.course_id,
                ProgramSemesterCourse.program_id == enrollment.program.id,
            ),
        )
        .join(Semester)
        .filter(
            Assignment.published,
            Assignment.deadline >= datetime.now(UTC),
            Semester.number.in_(semester_numbers),
        )
        .order_by(Assignment.deadline.asc())
    ).all()
    collapsed = bool(int(c)) if (c := context.match.group("collapsed")) else None
    collapsed = True if collapsed is None and len(assignments) > 2 else collapsed

    picker = context.buttons.datepicker(
        context.match,
        selected=[a.deadline.date() for a in assignments] or None,
        emoji="📌",
        min=assignments[0].deadline.date() if assignments else datetime.now(UTC).date(),
        max=(
            assignments[-1].deadline.date() if assignments else datetime.now(UTC).date()
        ),
    )
    back_url = re.sub(f"/{constants.DEADLINE}.*", f"/{constants.COURSES}", url)
    keyboard = picker.keyboard
    keyboard += [[context.buttons.back(absolute_url=back_url)]]
    if collapsed is not None:
        more_url = re.sub("\?c=\d", "", url)
        more_url = re.sub(
            f"/{constants.DEADLINE}",
            f"?c={int(not collapsed)}/{constants.DEADLINE}",
            more_url,
        )
        func = context.buttons.show_more if collapsed else context.buttons.show_less
        keyboard.insert(0, [func(more_url)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = ""
    for i, assignment in enumerate(assignments):
        if collapsed and i == 2:
            ngettext = context.ngettext
            message += f"+{len(assignments) - 2} " + ngettext(
                "more item", "more items", len(assignments) - 2
            )
            break
        language_code = context.user_data["language_code"]
        message += messages.bold(
            f"{i+1}. {_(assignment.type)} {assignment.number}"
            f" {assignment.course.get_name(language_code)}\n"
        )
        message += "   " + (
            format_datetime(
                assignment.deadline.astimezone(ZoneInfo("Africa/Khartoum")),
                "E d MMM hh:mm a ZZZZ",
                locale=context.language_code,
            )
            + "\n"
        )
        delta = assignment.deadline - datetime.now(UTC)
        parts = time_remaining(delta, language_code)
        remaining = "{} {}".format(*parts) if len(parts) > 1 else "{}".format(*parts)
        message += "   " + remaining + "\n\n"

    if len(assignments) == 0:
        message = _("Nothing coming soon")

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def assignments(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data `{PREFIX}/{constants.COURSES}/(?P<course_id>\d+)$`
    """

    query = update.callback_query

    url = re.search(r".*&d=\d+", context.match.group()).group()

    year, month, day = (
        int(context.match.group("y")),
        int(context.match.group("m")),
        int(context.match.group("d")),
    )

    enrollment_id = context.match.group("enrollment_id")
    enrollment = queries.enrollment(session, enrollment_id)
    semester_number = enrollment.semester.number
    semester_numbers = [
        enrollment.semester.number,
        semester_number + (1 if semester_number % 2 == 1 else -1),
    ]
    _ = context.gettext

    assignments = session.scalars(
        select(Assignment)
        .join(
            ProgramSemesterCourse,
            and_(
                ProgramSemesterCourse.course_id == Assignment.course_id,
                ProgramSemesterCourse.program_id == enrollment.program.id,
            ),
        )
        .join(Semester)
        .filter(
            Semester.number.in_(semester_numbers),
            Assignment.published,
            Assignment.deadline >= datetime(year=year, month=month, day=day, hour=0),
            Assignment.deadline
            <= datetime(year=year, month=month, day=day, hour=23, minute=59, second=59),
        )
        .order_by(Assignment.deadline.asc())
    ).all()

    if len(assignments) == 0:
        await query.answer(_("Nothing for this day!"))
        return constants.ONE

    await query.answer()

    buttons = [
        InlineKeyboardButton(
            text=_(a.type) + f" {a.number} {a.course.get_name(context.language_code)}",
            callback_data=f"{url}/{a.type}/{a.id}",
        )
        for a in assignments
    ]

    keyboard = build_menu(
        buttons, 1, footer_buttons=context.buttons.back(url, pattern="&d=.*")
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "📌 " + format_datetime(
        datetime(year=year, month=month, day=day, tzinfo=ZoneInfo("Africa/Khartoum")),
        "E d MMM",
        locale=context.language_code,
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


@session
async def optional_list(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `"({constants.COURSES_}|{constants.ENROLLMENT_})/{constants.ENROLLMENTS}
    /(?P<enrollment_id>\d+)/{constants.COURSES}/{constants.OPTIONAL}
    (?:\?psc_id=(?P<psc_id>\d+)&s=(?P<selected>0|1))?`
    """

    query = update.callback_query

    # url here is calculated because this handler reenter with query params
    match = re.search(
        rf"({constants.COURSES_}|{constants.ENROLLMENT_})"
        rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.COURSES}"
        f"/{constants.OPTIONAL}",
        context.match.group(),
    )
    url = match.group()

    enrollment_id = context.match.group("enrollment_id")
    psc_id = context.match.group("psc_id")
    selected = bool(int(o)) if (o := context.match.group("selected")) else None

    _ = context.gettext

    if psc_id is not None and selected is not None:
        if selected:
            user_course = UserOptionalCourse(
                user=queries.user(session, context.user_data["id"]),
                program_semester_course=queries.program_semester_course(
                    session, program_semester_course_id=psc_id
                ),
            )
            session.add(user_course)
            await query.answer(_("Success! {} added").format(_("Course")))
        elif not selected:
            user_course = queries.user_optional_course(
                session,
                user_id=context.user_data["id"],
                programs_semester_course_id=psc_id,
            )
            session.delete(user_course)
            await query.answer(_("Success! {} removed").format(_("Course")))

    await query.answer()
    enrollment_id = context.match.group("enrollment_id")
    enrollment = queries.enrollment(session, enrollment_id)

    program_optional_courses = queries.program_semester_courses(
        session,
        program_id=enrollment.program.id,
        semester_id=enrollment.semester.id,
        optional=True,
    )
    user_optional_courses = queries.user_optional_courses(
        session, user_id=context.user_data["id"]
    )
    selected_ids = [
        optional.program_semester_course_id for optional in user_optional_courses
    ]
    menu = context.buttons.program_semester_courses_list(
        program_optional_courses,
        url=url,
        sep="?psc_id=",
        end=lambda psc: "&s=" + str(int(psc.id not in selected_ids)),
        selected_ids=selected_ids,
    )
    menu += [
        context.buttons.back(url, pattern=rf"/{constants.OPTIONAL}$"),
    ]

    keyboard = build_menu(menu, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = _("Select optional courses")
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


async def ignore(update: Update, context: CustomContext):
    """
    Runs on callback_data `{IGNORE}`
    """
    query = update.callback_query
    await query.answer()
    return constants.ONE


# ------------------------- ConversationHander -----------------------------

PREFIX = (
    rf"({constants.COURSES_}|{constants.ENROLLMENT_})"
    rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
    rf"/{constants.COURSES}/(?P<course_id>\d+)"
)
"""Used as a prefix for all `callback data` in this conversation"""

entry_points = [
    CallbackQueryHandler(course, pattern=f"{PREFIX}$"),
    CallbackQueryHandler(
        optional_list,
        pattern=rf"({constants.COURSES_}|{constants.ENROLLMENT_})"
        rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.COURSES}"
        f"/{constants.OPTIONAL}(?:\?psc_id=(?P<psc_id>\d+)&s=(?P<selected>0|1))?",
    ),
    CallbackQueryHandler(
        deadlines,
        pattern=rf"{constants.COURSES_}"
        rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)(?:\?c=(?P<collapsed>\d))?/{constants.DEADLINE}"
        f"(?:\?y=(?P<y>\d+)(?:&m=(?P<m>\d+))?(?:&d=(?P<d>\D+))?)?(?:/{constants.IGNORE})?$",
    ),
    CallbackQueryHandler(ignore, pattern=f"^{constants.IGNORE}$"),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            commands.user_course_list,
            pattern=rf"{constants.COURSES_}"
            rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+).*"
            rf"/{constants.COURSES}$",
        ),
        CallbackQueryHandler(
            assignments,
            pattern=rf"{constants.COURSES_}"
            rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+).*/{constants.DEADLINE}(?:\?y=(?P<y>\d+)"
            f"(?:&m=(?P<m>\d+))?(?:&d=(?P<d>\d+))?)?(/{MaterialType.ASSIGNMENT})?$",
        ),
        CallbackQueryHandler(
            material.material,
            pattern=rf"{constants.COURSES_}"
            rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+).*/{constants.DEADLINE}.+"
            f"/(?P<material_type>{MaterialType.ASSIGNMENT})/(?P<material_id>\d+)$",
        ),
        CallbackQueryHandler(
            files.file,
            pattern=rf"{constants.COURSES_}"
            rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+).*/{constants.DEADLINE}.+"
            f"/(?P<material_type>{MaterialType.ASSIGNMENT})/(?P<material_id>\d+)"
            f"/{constants.FILES}/(?P<file_id>\d+)$",
        ),
        CallbackQueryHandler(
            sendall.send,
            pattern=rf"{constants.COURSES_}"
            rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+).*/{constants.DEADLINE}.+"
            f"/(?P<material_type>{MaterialType.ASSIGNMENT})/(?P<material_id>\d+)"
            f"/{constants.ALL}$",
        ),
        material.conversation(PREFIX),
    ]
}


usercourses_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.COURSES_,
    per_message=True,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
