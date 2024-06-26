from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler

from src import constants, queries
from src.conversations.updatematerial import updatematerials_
from src.customcontext import CustomContext
from src.messages import underline
from src.models import RoleName
from src.utils import build_menu, roles, session

URLPREFIX = constants.CONETENT_MANAGEMENT_
"""Used as a prefix for all `callback_data` s in this conversation module"""

# ------------------------------- entry_points ---------------------------


@roles(RoleName.ROOT)
@session
async def program_list(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text `contentmanagement`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = f"{URLPREFIX}/{constants.PROGRAMS}"

    programs = queries.programs(session)
    menu = context.buttons.programs_list(programs, url)
    keyboard = build_menu(menu, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = underline(_("Content Management"))
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def program_semester_list(
    update: Update, context: CustomContext, session: Session
):
    """Runs on callback_data ^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\\d+)$"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    program_id = int(context.match.group("program_id"))
    program = queries.program(session, program_id)
    semesters = queries.semesters(session, program_id)

    menu = context.buttons.semester_list(semesters, url + f"/{constants.SEMESTERS}")
    keyboard = build_menu(menu, 2, footer_buttons=context.buttons.back(url, r"/\d+"))
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = (
        underline(_("Content Management"))
        + "\n\n"
        + program.get_name(context.language_code)
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def semester_course_list(
    update: Update, context: CustomContext, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}/(?P<semester_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    program_id = int(context.match.group("program_id"))
    program = queries.program(session, program_id)
    semester_id = int(context.match.group("semester_id"))
    semester = queries.semester(session, semester_id)

    courses = queries.program_semester_courses(
        session, program_id=program_id, semester_id=semester_id
    )
    menu = context.buttons.courses_list(
        [psc.course for psc in courses],
        f"{url}/{constants.COURSES}",
        end=f"/{constants.ACADEMICYEARS}",
    )
    keyboard = build_menu(
        menu, 1, footer_buttons=context.buttons.back(url, rf"/{constants.SEMESTERS}.*")
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    _ = context.gettext

    message = (
        underline(_("Content Management"))
        + "\n\n"
        + program.get_name(context.language_code)
        + "\n"
        + _("Semester {}").format(semester.number)
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def course_year_list(update: Update, context: CustomContext, session: Session):
    """^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)
    /{constants.SEMESTERS}/(?P<semester_id>\d+)
    /{constants.COURSES}/(?P<course_id>\d+)/{constants.ACADEMICYEARS}$
    """
    query = update.callback_query
    await query.answer()

    url = context.match.group()
    program_id = context.match.group("program_id")
    program = queries.program(session, program_id)
    semester_id = context.match.group("semester_id")
    semester = queries.semester(session, semester_id)
    course_id = context.match.group("course_id")
    course = queries.course(session, course_id)

    academic_years = queries.academic_years(session)
    menu = context.buttons.years_list(academic_years, url)
    keyboard = build_menu(menu, 2)
    keyboard.extend([[context.buttons.back(url, rf"/{constants.COURSES}.*")]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = (
        underline(_("Content Management"))
        + "\n\n"
        + program.get_name(context.language_code)
        + "\n"
        + _("Semester {}").format(semester.number)
        + "\n\n"
        + _("t-symbol")
        + "─ "
        + course.get_name(context.language_code)
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# ------------------------- ConversationHander -----------------------------

cmd = constants.COMMANDS
entry_points = [
    CommandHandler(cmd.contentmanagement.command, program_list),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            program_list, pattern=f"^{URLPREFIX}/{constants.PROGRAMS}$"
        ),
        CallbackQueryHandler(
            program_semester_list,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)$",
        ),
        CallbackQueryHandler(
            semester_course_list,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}/(?P<semester_id>\d+)$",
        ),
        CallbackQueryHandler(
            course_year_list,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.ACADEMICYEARS}$",
        ),
        updatematerials_,
    ],
}


contentmanagement_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.CONETENT_MANAGEMENT_,
    persistent=True,
    # allow_reentry must be set to true for the conversation to work
    # after pressing going back to an entry point
    allow_reentry=True,
)
