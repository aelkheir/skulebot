"""Contains callbacks and handlers for the /updatematerials conversation"""

import re

from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from src import buttons, constants, messages, queries
from src.conversations.material import material
from src.models import MaterialType, RoleName
from src.models.user_optional_course import UserOptionalCourse
from src.utils import build_menu, roles, session

URLPREFIX = constants.UPDATE_MATERIALS_
"""Used as a prefix for all `callback data` in this conversation"""


# helpers
def title(match: re.Match, session: Session):
    url: str = match.group()
    text = ""
    if url.startswith(constants.UPDATE_MATERIALS_):
        text += "<u>Editor Menu</u>"
    elif url.startswith(constants.EDITOR_):
        text += "<u>Editor Access</u>"
    elif url.startswith(constants.CONETENT_MANAGEMENT_):
        text += "<u>Content Management</u>"

    if match.group("enrollment_id"):
        text += "\n\n" + messages.enrollment_text(match, session)
    elif match.group("year_id"):
        program_id = match.group("program_id")
        program = queries.program(session, program_id)
        semester_id = match.group("semester_id")
        semester = queries.semester(session, semester_id)
        year_id = match.group("year_id")
        year = queries.academic_year(session, year_id)
        text += (
            "\n\n"
            + program.get_name()
            + "\n"
            + f"Semester {semester.number}"
            + "\n"
            + f"{year.start} - {year.end}"
            + "\n"
        )
    return text


# ------------------------------- entry_points ---------------------------


@roles(RoleName.EDITOR)
@session
async def update_materials(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text `updatematerials`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    access = queries.user_most_recent_access(session, context.user_data["id"])

    if not access:
        return

    enrollment = access.enrollment

    user_courses = queries.user_courses(
        session,
        program_id=enrollment.program.id,
        semester_id=enrollment.semester.id,
        user_id=context.user_data["id"],
    )

    url = f"{URLPREFIX}/{constants.ENROLLMENTS}/{enrollment.id}/{constants.COURSES}"
    menu = buttons.courses_list(
        user_courses,
        url=url,
    )
    has_optional_courses = queries.has_optional_courses(
        session,
        program_id=enrollment.program.id,
        semester_id=enrollment.semester.id,
    )
    menu = (
        [*menu, buttons.optional_courses(f"{url}/{constants.OPTIONAL}")]
        if has_optional_courses
        else menu
    )
    keyboard = build_menu(menu, 1)

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "<u>Editor Menu</u>\n\n" + messages.enrollment_text(
        context.match, session, enrollment=enrollment
    )
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)


@session
async def course(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    """
    Runs on callback_data `^{PREFIXES}`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    keyboard = buttons.material_groups(url=url, groups=list(MaterialType))
    keyboard.append([buttons.back(url, "/(\d+)$")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        title(context.match, session)
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
    `({constants.UPDATE_MATERIALS_}|{constants.EDITOR_})/{constants.ENROLLMENTS}
    /(?P<enrollment_id>\d+)/{constants.COURSES}/{constants.OPTIONAL}
    (?:\?psc_id=(?P<psc_id>\d+)&s=(?P<selected>0|1))?`
    """
    query = update.callback_query

    # url here is calculated because this handler reenter with query params
    match = re.search(
        rf"({constants.UPDATE_MATERIALS_}|{constants.EDITOR_})"
        rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.COURSES}"
        f"/{constants.OPTIONAL}",
        context.match.group(),
    )
    url = match.group()

    psc_id = context.match.group("psc_id")
    selected = bool(int(o)) if (o := context.match.group("selected")) else None

    if psc_id is not None and selected is not None:
        if selected:
            user_course = UserOptionalCourse(
                user=queries.user(session, context.user_data["id"]),
                program_semester_course=queries.program_semester_course(
                    session, psc_id
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


# ------------------------- ConversationHander -----------------------------


PREFIXES = (
    # conversation that lead to here
    rf"({constants.UPDATE_MATERIALS_}"
    f"|{constants.EDITOR_}"
    f"|{constants.CONETENT_MANAGEMENT_})"
    # Optional. When in MATERIALS_ or EDITORSHIP_
    rf"(/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+))?"
    # Optional. When in CONETENTMANAGEMENT_
    rf"(/{constants.PROGRAMS}/(?P<program_id>\d+)"
    rf"/{constants.SEMESTERS}/(?P<semester_id>\d+))?"
    # Must have for all converstaions that lead to here
    rf"/{constants.COURSES}/(?P<course_id>\d+)"
    # Optional. When in CONETENTMANAGEMENT_
    rf"(/{constants.ACADEMICYEARS}/(?P<year_id>\d+))?"
)


entry_points = [
    CommandHandler("updatematerials", update_materials),
    CallbackQueryHandler(course, pattern=f"^{PREFIXES}$"),
    CallbackQueryHandler(
        optional_list,
        pattern=rf"({constants.UPDATE_MATERIALS_}|{constants.EDITOR_})"
        rf"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.COURSES}"
        f"/{constants.OPTIONAL}(?:\?psc_id=(?P<psc_id>\d+)&s=(?P<selected>0|1))?",
    ),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            course,
            pattern=f"^{constants.UPDATE_MATERIALS_}"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)$",
        ),
        CallbackQueryHandler(
            update_materials,
            pattern=f"{constants.UPDATE_MATERIALS_}"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.COURSES}$",
        ),
        material.conversation(PREFIXES),
    ]
}

updatematerials_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.UPDATE_MATERIALS_,
    per_user=True,
    per_chat=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
