import re
from typing import List

from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import constants, queries
from src.customcontext import CustomContext
from src.messages import bold, underline
from src.models import Course, RoleName
from src.utils import Pager, build_menu, roles, session

URLPREFIX = constants.COURSE_MANAGEMENT_
"""Used as a prefix for all `callback_data` s in this conversation module"""

DATA_KEY = constants.COURSE_MANAGEMENT_
"""Used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------


@session
@roles(RoleName.ROOT)
async def department_list(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text `/coursemanaement`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url: str = f"{URLPREFIX}/{constants.DEPARTMENTS}"

    departments = queries.departments(session)
    button_list = context.buttons.departments_list(
        departments,
        url=url,
    )
    button_list += [
        context.buttons.add(url + f"/0/{constants.COURSES}", "Course"),
    ]
    keyboard = build_menu(button_list, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = underline(_("Course Management"))
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def course_list(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)(?:/{constants.COURSES})?(?:\?p=(\d+))?$`
    """

    query = update.callback_query
    await query.answer()

    department_id = int(context.match.group("department_id"))
    department = queries.department(session, department_id) if department_id else None
    courses = queries.department_courses(
        session, department_id if department_id else None
    )

    offset = int(page) if (page := context.match.group("page")) else 0
    pager = Pager[Course](courses, offset, 12)

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DEPARTMENTS}/\d+", context.match.group()).group()
    menu = context.buttons.courses_list(pager.items, url + f"/{constants.COURSES}")

    keyboard = build_menu(menu, 2)

    if pager.has_next or pager.has_previous:
        pager_keyboard = []
        keyboard.append(pager_keyboard)
        if pager.has_previous:
            pager_keyboard.append(
                context.buttons.previous_page(f"{url}?p={pager.previous_offset}")
            )
        if pager.has_next:
            pager_keyboard.append(
                context.buttons.next_page(f"{url}?p={pager.next_offset}")
            )

    keyboard.extend(
        [
            [context.buttons.add(f"{url}/{constants.COURSES}", "Course")],
            [context.buttons.back(url, r"/\d+")],
        ]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = (
        underline(_("Course Management"))
        + "\n\n"
        + _("t-symbol")
        + "─ "
        + (
            department.get_name(context.language_code)
            if department
            else _("General Department")
        )
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def course(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)
    /{constants.COURSES}/(?P<course_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    department_id = int(context.match.group("department_id"))
    department = queries.department(session, department_id) if department_id else None
    course_id = context.match.group("course_id")
    course = queries.course(session, course_id)

    menu = [
        context.buttons.edit(url, end="/" + constants.AR, text="Arabic Name"),
        context.buttons.edit(url, end="/" + constants.EN, text="English Name"),
        context.buttons.edit(url, end="/" + constants.DEPARTMENTS, text="Department"),
        context.buttons.edit(url, end="/" + constants.CREDITS, text="Credits"),
    ]
    keyboard = build_menu(menu, 2)
    keyboard.extend(
        [
            [context.buttons.delete(url, "Course")],
            [context.buttons.back(url, rf"/{constants.COURSES}/\d+$")],
        ]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = (
        underline(_("Course Management"))
        + "\n\n"
        + _("t-symbol")
        + "─ "
        + (
            department.get_name(context.language_code)
            if department
            else _("General Department")
        )
        + "\n│ "
        + _("corner-symbol")
        + "── "
        + course.get_name(context.language_code)
        + "\n\n"
        + _("Name in Arabic {} and English {}").format(course.ar_name, course.en_name)
        + "\n"
        + _("Credits: {}").format(course.credits or "")
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


async def course_add(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(\d+)/{constants.COURSES}/{constants.ADD}$`
    """
    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    _ = context.gettext
    message = _("Type multilingual name")
    await query.message.reply_text(message, parse_mode=ParseMode.HTML)

    return constants.ADD


@session
async def receive_name_new(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text matching
    `^(?P<en_name>(?:.)+?)\s*-\s*(?P<ar_name>(?:.)+?)$`
    """

    en_name, ar_name = context.match.group("en_name"), context.match.group("ar_name")

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"/{constants.DEPARTMENTS}/(?P<department_id>\d+)",
        url,
    )

    department_id = int(match.group("department_id"))
    department = queries.department(session, department_id) if department_id else None

    course = Course(en_name=en_name, ar_name=ar_name, department=department)
    session.add(course)
    session.flush()

    keyboard = [[context.buttons.view_added(course.id, url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = _("Success! {} created").format(_("Course"))
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


async def course_edit_name(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)/{constants.COURSES}
    /(?P<course_id>\d+)/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    lang_code = context.match.group("lang_code")

    context.chat_data.setdefault(DATA_KEY, {})["url"] = url
    _ = context.gettext

    language = _("Arabic") if lang_code == constants.AR else _("English")
    message = _("Type name in {}").format(language)
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.NAME}"


@session
async def receive_name_edit(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text matching `^([^\d].+)$`"""

    name = context.match.groups()[0].strip()

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}"
        f"/(?P<lang_code>{constants.AR}|{constants.EN})",
        url,
    )

    course_id = int(match.group("course_id"))
    course = queries.course(session, course_id)

    lang_code = match.group("lang_code")
    setattr(course, f"{lang_code}_name", name)

    keyboard = [
        [
            context.buttons.back(
                url, pattern=rf"/{constants.EDIT}.*", text="to Course"
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    language = _("Arabic") if lang_code == constants.AR else _("English")
    message = _("Success! {} updated").format(_("Name in {}")).format(language)
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


async def course_edit_credits(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)
    /{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.CREDITS}$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url
    _ = context.gettext

    message = _("Type number") + _("/empty to clear {}").format(_("Credits"))
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.CREDITS}"


@session
async def receive_credits_edit(
    update: Update, context: CustomContext, session: Session
):
    """Runs with Message.text mathcing either `^(?P<credits>\d+)$` or `/empty`"""
    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.CREDITS}",
        url,
    )

    course_id = int(match.group("course_id"))
    course = queries.course(session, course_id)

    keyboard = [
        [context.buttons.back(url, pattern=rf"/{constants.EDIT}.*", text="to Course")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    if update.message.text == "/empty":
        course.credits = None
        message = _("Success! {} deleted").format(_("Credits"))
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE

    credits = context.match.group("credits").strip()
    course.credits = int(credits)

    keyboard = [
        [context.buttons.back(url, pattern=rf"/{constants.EDIT}.*", text="to Course")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = _("Success! {} updated").format(_("Credits"))
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def course_change_department(
    update: Update, context: CustomContext, session: Session
):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)
    /{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.DEPARTMENTS}$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    department_id = context.match.group("department_id")
    department = queries.department(session, department_id) if department_id else None

    course_id = context.match.group("course_id")
    course = queries.course(session, course_id)

    departments = queries.departments(session)
    menu = context.buttons.departments_list(
        departments, url, selected_id=int(department_id)
    )
    menu += [context.buttons.back(url, pattern=rf"/{constants.DEPARTMENTS}$")]
    keyboard = build_menu(menu, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = (
        underline(_("Course Management"))
        + "\n\n"
        + _("t-symbol")
        + "─ "
        + (
            department.get_name(context.language_code)
            if department
            else _("General Department")
        )
        + "\n│ "
        + _("corner-symbol")
        + "── "
        + course.get_name(context.language_code)
        + "\n\n"
        + _("Select {}").format(_("Department"))
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def course_set_department(
    update: Update, context: CustomContext, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)/{constants.COURSES}
    /(?P<course_id>\d+)/{constants.EDIT}/{constants.DEPARTMENTS}/(?P<new_department_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    course_id = int(context.match.group("course_id"))
    old_department_id = context.match.group("department_id")
    new_department_id = int(context.match.group("new_department_id"))

    course = queries.course(session, course_id)
    course.department_id = new_department_id if new_department_id else None

    course_url = url.replace(f"/{old_department_id}/", f"/{new_department_id}/")

    keyboard = [[context.buttons.back(course_url, f"/{constants.EDIT}.*", "to Course")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = _("Success! {} updated").format(_("Department"))
    await query.edit_message_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def course_delete(update: Update, context: CustomContext, session: Session):
    """Runs on
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)/{constants.COURSES}
    /(?P<course_id>\d+)/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    department_id = context.match.group("department_id")
    department = queries.department(session, department_id)
    course_id = context.match.group("course_id")
    course = queries.course(session, course_id)
    has_confirmed = context.match.group("has_confirmed")

    course_name = course.get_name(context.language_code)

    menu_buttons: List
    _ = context.gettext
    message = (
        underline(_("Course Management"))
        + "\n\n"
        + _("t-symbol")
        + "─ "
        + (
            department.get_name(context.language_code)
            if department
            else _("General Department")
        )
        + "\n│ "
        + _("corner-symbol")
        + "── "
        + course_name
        + "\n\n"
    )

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message = _("Delete warning {}").format(
            bold(_("Course {}").format(course_name))
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message = _("Confirm delete warning {}").format(
            bold(_("Course {}").format(course_name))
        )
    elif has_confirmed == "1":
        session.delete(course)
        menu_buttons = [
            context.buttons.back(
                url, text="to Courses", pattern=rf"/\d+/{constants.DELETE}"
            )
        ]
        message = _("Success! {} deleted").format(course_name)

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# ------------------------- ConversationHander -----------------------------

cmd = constants.COMMANDS
entry_points = [
    CommandHandler(cmd.coursemanagement.command, department_list),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            course_list,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"(?:/{constants.COURSES})?(?:\?p=(?P<page>\d+))?$",
        ),
        CallbackQueryHandler(
            course,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)$",
        ),
        CallbackQueryHandler(
            course_add,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(\d+)/{constants.COURSES}/{constants.ADD}$",
        ),
        CallbackQueryHandler(
            course_edit_name,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)"
            f"/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$",
        ),
        CallbackQueryHandler(
            course_edit_credits,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.CREDITS}$",
        ),
        CallbackQueryHandler(
            department_list, pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}$"
        ),
        CallbackQueryHandler(
            course_delete,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
        CallbackQueryHandler(
            course_change_department,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.DEPARTMENTS}$",
        ),
        CallbackQueryHandler(
            course_set_department,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}"
            f"/{constants.DEPARTMENTS}/(?P<new_department_id>\d+)$",
        ),
    ],
}

states.update(
    {
        f"{constants.EDIT} {constants.CREDITS}": states[constants.ONE]
        + [
            MessageHandler(
                filters.Regex(r"^(?P<credits>\d+)$")
                | (filters.Command(only_start=True) & (filters.Text("/empty"))),
                receive_credits_edit,
            ),
        ],
        f"{constants.EDIT} {constants.NAME}": states[constants.ONE]
        + [
            MessageHandler(
                filters.Regex(r"^([^\d].+)$"),
                receive_name_edit,
            )
        ],
    }
)
states.update(
    {
        constants.ADD: states[constants.ONE]
        + [
            MessageHandler(
                filters.Regex(r"^(?P<en_name>(?:.)+?)\s*-\s*(?P<ar_name>(?:.)+?)$"),
                receive_name_new,
            ),
        ]
    }
)

coursemanagement_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.COURSE_MANAGEMENT_,
    persistent=True,
    # allow_reentry must be set to true for the conversation to work
    # after pressing going back to an entry point
    allow_reentry=True,
)
