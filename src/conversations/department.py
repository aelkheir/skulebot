import re

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
from src.messages import bold
from src.models import Department, RoleName
from src.utils import build_menu, roles, session

URLPREFIX = constants.DEPARTMENT_
"""Used as a prefix for all `callback_data` s in this conversation module"""

DATA_KEY = constants.DEPARTMENT_
"""Used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------


@roles(RoleName.ROOT)
@session
async def department_list(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text `/semesters`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url: str = f"{URLPREFIX}/{constants.DEPARTMENTS}"

    departments = queries.departments(session)
    department_button_list = context.buttons.departments_list(
        departments,
        url=url,
        include_none_department=False,
    )
    keyboard = build_menu(
        department_button_list,
        1,
        footer_buttons=context.buttons.add(url, "Department"),
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = _("Departments")
    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def department(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    ^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)$
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    department_id = context.match.group("department_id")
    department = queries.department(session, department_id)

    keyboard = [
        [
            context.buttons.edit(url, "Arabic Name", end=f"/{constants.AR}"),
            context.buttons.edit(url, "English Name", end=f"/{constants.EN}"),
        ],
        [context.buttons.delete(url, "Department")],
        [context.buttons.back(url, "/\d+")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = _("Name in Arabic {} and English {}").format(
        department.ar_name, department.en_name
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


async def department_add(update: Update, context: CustomContext):
    """Runs on callback_data ^{URLPREFIX}/{constants.DEPARTMENTS}/({constants.ADD})$"""
    query = update.callback_query
    await query.answer()

    message = context.gettext("Type multilingual name")
    await query.message.reply_text(message, parse_mode=ParseMode.HTML)

    return constants.ADD


@session
async def receive_name_new(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text matching
    `^(?P<en_name>(?:.)+?)\s*-\s*(?P<ar_name>(?:.)+?)$`
    """

    en_name, ar_name = context.match.group("en_name"), context.match.group("ar_name")

    department = Department(ar_name=ar_name, en_name=en_name)
    session.add(department)
    session.flush()

    keyboard = [
        [
            context.buttons.view_added(
                "Department",
                absolute_url=f"{URLPREFIX}/{constants.DEPARTMENTS}/{department.id}",
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = _("Success! {} created").format(_("Department"))
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


async def department_edit_name(update: Update, context: CustomContext):
    """Runs on callback_data
    ^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)/{constants.EDIT}/
    (?P<lang_code>{constants.AR}|{constants.EN})$
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

    return constants.EDIT


@session
async def receive_name_edit(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text matching `^(.+)$`"""

    name = context.match.groups()[0].strip()

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
        f"/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$",
        url,
    )

    department_id = int(match.group("department_id"))
    department = queries.department(session, department_id)

    lang_code = match.group("lang_code")
    setattr(department, f"{lang_code}_name", name)

    keyboard = [
        [
            context.buttons.back(
                url, pattern=rf"/{constants.EDIT}.*", text="to Department"
            ),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    language = _("Arabic") if lang_code == constants.AR else _("English")
    message = _("Success! {} updated").format(_("Name in {}")).format(language)
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def department_delete(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    ^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)
    /{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    department_id = context.match.group("department_id")
    department = queries.department(session, department_id)
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: list
    message: str
    _ = context.gettext

    department_name = department.get_name(context.language_code)

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message = _("Delete warning {}").format(
            bold(_("Department {}").format(department_name))
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message = _("Confirm delete warning {}").format(
            bold(_("Department {}").format(department_name))
        )
    elif has_confirmed == "1":
        session.delete(department)
        menu_buttons = [
            context.buttons.back(
                url, text="to Departments", pattern=rf"/\d+/{constants.DELETE}"
            )
        ]
        message = _("Success! {} deleted").format(department_name)

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# ------------------------- ConversationHander -----------------------------

cmd = constants.COMMANDS
entry_points = [
    CommandHandler(cmd.departments.command, department_list),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            department,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)$",
        ),
        CallbackQueryHandler(
            department_add,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/({constants.ADD})$",
        ),
        CallbackQueryHandler(
            department_list, pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}$"
        ),
        CallbackQueryHandler(
            department_edit_name,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$",
        ),
        CallbackQueryHandler(
            department_delete,
            pattern=f"^{URLPREFIX}/{constants.DEPARTMENTS}/(?P<department_id>\d+)"
            f"/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
    ],
}

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
states.update(
    {
        constants.EDIT: states[constants.ONE]
        + [
            MessageHandler(filters.Regex(r"^(.+)$"), receive_name_edit),
        ]
    }
)

department_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.DEPARTMENT_,
    persistent=True,
    # allow_reentry must be set to true for the conversation to work
    # after pressing going back to an entry point
    allow_reentry=True,
)
