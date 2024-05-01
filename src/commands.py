from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from src import buttons, constants, messages, queries
from src.models import RoleName, Status
from src.utils import build_menu, roles, session

# ------------------------------- Callbacks ---------------------------


@roles(RoleName.USER)
@session
async def list_enrollments(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
) -> None:
    """Runs with Message.text `/enrollments`. This is an entry point to
    `constans.ENROLLMENT_` conversation"""

    URLPREFIX = constants.ENROLLMENT_

    query: None | CallbackQuery = None
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    enrollments = queries.user_enrollments(session, user_id=context.user_data["id"])
    most_recent_year = queries.academic_year(session, most_recent=True)
    most_recent_enrollment_year = enrollments[0].academic_year if enrollments else None

    menu = []
    if most_recent_year and most_recent_enrollment_year != most_recent_year:
        menu.append(
            buttons.new_enrollment(
                most_recent_year,
                f"{URLPREFIX}/{constants.ENROLLMENTS}"
                f"/{constants.ADD}?year_id={most_recent_year.id}",
            ),
        )

    menu += buttons.enrollments_list(
        enrollments, f"{URLPREFIX}/{constants.ENROLLMENTS}"
    )
    keyboard = build_menu(menu, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "Your enrollments"

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_markdown_v2(message, reply_markup=reply_markup)


@roles(RoleName.STUDENT)
@session
async def user_course_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text `/courses`. This is an entry point to
    `constans.COURSES_` conversation"""

    URLPREFIX = constants.COURSES_

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    user = queries.user(session, context.user_data["id"])
    if len(user.enrollments) == 0:
        return await update.message.reply_html(
            "Oops. It seems like you have no current enrollment."
            " Use /enrollments to enroll in a Program"
        )

    enrollment = queries.user_most_recent_enrollment(
        session, user_id=context.user_data["id"]
    )

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
    message = "Good morning, " + update.effective_user.mention_html(
        name=update.effective_user.first_name
    )
    if not queries.all_have_editors(
        session,
        course_ids=[u.id for u in user_courses],
        academic_year=enrollment.academic_year,
    ):
        message += (
            "\n\n[there is no one with upload access for this program,"
            " you can become one here /editor.]"
        )
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)
    return None


@roles(RoleName.STUDENT)
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs with Message.text `/settings`. This is an entry point to
    `constans.SETTINGS_` conversation"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    URLPREFIX = constants.SETTINGS_

    menu = [
        buttons.notifications(f"{URLPREFIX}/{constants.NOTIFICATIONS}"),
        buttons.language(f"{URLPREFIX}/{constants.LANGUAGE}"),
    ]
    keyboard = build_menu(menu, 2)

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = messages.bot_settings()
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)


@roles(RoleName.ROOT)
@session
async def request_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text `/requestmanagement`. This is an entry point to
    `constans.REQUEST_MANAGEMENT_` conversation"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    URLPREFIX = constants.REQUEST_MANAGEMENT_

    requests = queries.access_requests(session, status=Status.PENDING)
    menu = await buttons.access_requests_list_chat_name(
        requests, url=f"{URLPREFIX}/{constants.ACCESSREQUSTS}", context=context
    )

    keyboard = build_menu(
        menu,
        1,
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Pending Access Requests"

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)


@roles(RoleName.USER)
@session
async def help(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
) -> None:
    """Runs with Message.text `/help`."""

    user = queries.user(session, user_id=context.user_data["id"])
    user_roles = {r.name for r in user.roles}

    message = messages.help(user_roles)

    await update.message.reply_html(message)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


# ------------------------------- CommandHandlers ---------------------------

handlers = [
    CommandHandler(["enrollments"], list_enrollments),
    CommandHandler("courses", user_course_list),
    CommandHandler(["settings"], settings),
    CommandHandler(["requestmanagement"], request_list),
    CommandHandler(["help", "start"], help),
]
