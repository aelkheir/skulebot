import re

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from src import buttons, commands, constants, messages, queries
from src.conversations.material import material
from src.models import MaterialType
from src.models.user_optional_course import UserOptionalCourse
from src.utils import build_menu, session

# ------------------------------- entry_points ---------------------------


@session
async def course(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
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

    lectures = (
        queries.lectures(
            session, course_id=course_id, year_id=enrollment.academic_year_id
        )
        if MaterialType.LECTURE in material_groups
        else []
    )
    menu = buttons.material_list(f"{url}/{MaterialType.LECTURE}", lectures)
    keyboard = build_menu(menu, 3)

    keyboard.extend(
        buttons.material_groups(
            url,
            groups=[m for m in material_groups if m != MaterialType.LECTURE],
        )
    )

    keyboard += [[buttons.back(url, "/(\d+)$")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        messages.title(context.match, session)
        + "\n"
        + messages.course_text(context.match, session)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def optional_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
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

    if psc_id is not None and selected is not None:
        if selected:
            user_course = UserOptionalCourse(
                user=queries.user(session, context.user_data["id"]),
                program_semester_course=queries.program_semester_course(
                    session, program_semester_course_id=psc_id
                ),
            )
            session.add(user_course)
            await query.answer("Course added")
        elif not selected:
            user_course = queries.user_optional_course(
                session,
                user_id=context.user_data["id"],
                programs_semester_course_id=psc_id,
            )
            session.delete(user_course)
            await query.answer("Course removed")

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
    menu = buttons.program_semester_courses_list(
        program_optional_courses,
        url=url,
        sep="?psc_id=",
        end=lambda psc: "&s=" + str(int(psc.id not in selected_ids)),
        selected_ids=selected_ids,
    )
    menu += [
        buttons.back(url, pattern=rf"/{constants.OPTIONAL}$"),
    ]

    keyboard = build_menu(menu, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        "These courses are optional. Select one or more to add to your /courses menu"
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


async def ignore(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    CallbackQueryHandler(ignore, pattern=f"^{constants.IGNORE}$"),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            commands.user_course_list,
            pattern=rf"{constants.COURSES_}"
            rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
            rf"/{constants.COURSES}$",
        ),
        material.conversation(PREFIX),
    ]
}


usercourses_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.COURSES_,
    per_user=True,
    per_chat=True,
    per_message=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
