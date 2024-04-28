import re
from typing import List

from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import buttons, constants, messages, queries
from src.models import Course, RoleName
from src.utils import Pager, build_menu, roles, session

URLPREFIX = constants.COURSE_MANAGEMENT_
"""Used as a prefix for all `callback_data` s in this conversation module"""

DATA_KEY = constants.COURSE_MANAGEMENT_
"""Used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------


@session
@roles(RoleName.ROOT)
async def department_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text `/coursemanaement`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url: str = f"{URLPREFIX}/{constants.DEPARTMENTS}"

    departments = queries.departments(session)
    button_list = buttons.departments_list(
        departments,
        url=url,
    )
    button_list += [
        buttons.add(url + f"/0/{constants.COURSES}", "Course"),
    ]
    keyboard = build_menu(button_list, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "<u>" + "Course Management" + "</u>"
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def course_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
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
    menu = buttons.courses_list(pager.items, url + f"/{constants.COURSES}")

    keyboard = build_menu(menu, 2)

    if pager.has_next or pager.has_previous:
        pager_keyboard = []
        keyboard.append(pager_keyboard)
        if pager.has_previous:
            pager_keyboard.append(
                buttons.previous_page(f"{url}?p={pager.previous_offset}")
            )
        if pager.has_next:
            pager_keyboard.append(buttons.next_page(f"{url}?p={pager.next_offset}"))

    keyboard.extend(
        [
            [buttons.add(f"{url}/{constants.COURSES}", "Course")],
            [buttons.back(url, r"/\d+")],
        ]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        "<u>"
        "Course Management"
        "</u>\n\n"
        + messages.first_list_level(
            department.get_name() if department else "N/A Department"
        )
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def course(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
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
        buttons.edit(url, end="/" + constants.AR, text="Arabic Name"),
        buttons.edit(url, end="/" + constants.EN, text="English Name"),
        buttons.edit(url, end="/" + constants.DEPARTMENTS, text="Department"),
        buttons.edit(url, end="/" + constants.CREDITS, text="Credits"),
    ]
    keyboard = build_menu(menu, 2)
    keyboard.extend(
        [
            [buttons.delete(url, "Course")],
            [buttons.back(url, rf"/{constants.COURSES}/\d+$")],
        ]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        "<u>"
        "Course Management"
        "</u>\n\n"
        + messages.first_list_level(
            department.get_name() if department else "N/A Department"
        )
        + messages.second_list_level(course.get_name())
        + "\n"
        + messages.multilang_names(ar=course.ar_name, en=course.en_name)
        + f"Credits: {course.credits or ''}"
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


async def course_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(\d+)/{constants.COURSES}/{constants.ADD}$`
    """
    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    message = "Type name"
    await query.message.reply_text(
        message,
    )

    return constants.ADD


@session
async def receive_name_new(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
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

    keyboard = [[buttons.view_added(course.id, url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "Success! Course created."
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


async def course_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)/{constants.COURSES}
    /(?P<course_id>\d+)/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    lang_code = context.match.group("lang_code")

    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    language = "Arabic" if lang_code == constants.AR else "English"
    message = messages.type_name_in_lang(language)
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.NAME}"


@session
async def receive_name_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
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
            buttons.back(url, pattern=rf"/{constants.EDIT}.*", text="to Course"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    language = "Arabic" if lang_code == constants.AR else "English"
    message = messages.success_updated(f"{language} name")
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


async def course_edit_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)
    /{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.CREDITS}$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    message = messages.type_number() + ". type /empty to remove current credits"
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.CREDITS}"


@session
async def receive_credits_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text mathcing either `^(?P<credits>\d+)$` or `/empty`"""
    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}/{constants.CREDITS}",
        url,
    )

    course_id = int(match.group("course_id"))
    course = queries.course(session, course_id)

    keyboard = [[buttons.back(url, pattern=rf"/{constants.EDIT}.*", text="to Course")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message.text == "/empty":
        course.credits = None
        message = messages.success_deleted("Credits")
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE

    credits = context.match.group("credits").strip()
    course.credits = int(credits)

    keyboard = [[buttons.back(url, pattern=rf"/{constants.EDIT}.*", text="to Course")]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = messages.success_updated("Credits")
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def course_change_department(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
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
    menu = buttons.departments_list(departments, url, selected_id=int(department_id))
    menu += [buttons.back(url, pattern=rf"/{constants.DEPARTMENTS}$")]
    keyboard = build_menu(menu, 1)

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        "<u>"
        "Course Management"
        "</u>\n\n"
        + messages.first_list_level(
            department.get_name() if department else "N/A Department"
        )
        + messages.second_list_level(course.get_name())
        + "\n"
        + "Select department"
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def course_set_department(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
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
    keyboard = [[buttons.back(course_url, f"/{constants.EDIT}.*", "to Course")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = messages.success_updated("Course department")
    await query.edit_message_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def course_delete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
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

    menu_buttons: List
    message = (
        "<u>"
        "Course Management"
        "</u>\n\n"
        + messages.first_list_level(
            department.get_name() if department else "N/A Department"
        )
        + messages.second_list_level(course.get_name())
    )

    if has_confirmed is None:
        menu_buttons = buttons.delete_group(url=url)
        message += "\n" + messages.delete_confirm(f"Course {course.get_name()}")
    elif has_confirmed == "0":
        menu_buttons = buttons.confirm_delete_group(url=url)
        message += "\n" + messages.delete_reconfirm(f"Course {course.get_name()}")
    elif has_confirmed == "1":
        session.delete(course)
        menu_buttons = [
            buttons.back(url, text="to Courses", pattern=rf"/\d+/{constants.DELETE}")
        ]
        message = messages.success_deleted(f"Course {course.get_name()}")

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# ------------------------- ConversationHander -----------------------------

entry_points = [
    CommandHandler("coursemanagement", department_list),
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
    # allow_reentry must be set to true for the conversation to work
    # after pressing going back to an entry point
    allow_reentry=True,
)
