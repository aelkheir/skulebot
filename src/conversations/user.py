"""Contains callbacks and handlers for the /users conversaion"""

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
from src.constants import COMMANDS, EDIT, ONE, SEMESTERS
from src.customcontext import CustomContext
from src.messages import bold
from src.models import RoleName
from src.models.user import User
from src.utils import Pager, build_menu, roles, session

URLPREFIX = constants.USER_
"""used as a prefix for all `callback data` in this conversation"""

DATA_KEY = constants.USER_
"""used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------
@roles(RoleName.ROOT)
@session
async def user_list(update: Update, context: CustomContext, session: Session):
    """Runs with messages.test `'/users'` or on callback_data
    `^{URLPREFIX}/{constants.USERS}/(?:\?p=(?P<page>\d+))?$`
    """

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = f"{URLPREFIX}/{constants.USERS}"

    offset = 0
    if context.match:
        if context.match.group().endswith(constants.IGNORE):
            return constants.ONE

        offset = int(page) if (page := context.match.group("page")) else 0
    users = queries.users(session)
    users = [user for user in users for i in range(200)]
    pager = Pager[User](users, offset, 30)

    user_button_list = await context.buttons.user_list(pager.items, url, context)
    keyboard = build_menu(
        user_button_list,
        3,
        reverse=context.language_code == constants.AR,
    )
    if pager.has_next or pager.has_previous:
        pager_keyboard = []
        keyboard.append(pager_keyboard)
        if pager.has_previous:
            pager_keyboard.append(
                context.buttons.previous_page(f"{url}?p={pager.previous_offset}")
            )
        pager_keyboard.append(
            context.buttons.current_page(
                pager.current_page, pager.number_of_pages, f"{url}/{constants.IGNORE}"
            )
        )
        if pager.has_next:
            pager_keyboard.append(
                context.buttons.next_page(f"{url}?p={pager.next_offset}")
            )
        if context.language_code == constants.AR:
            pager_keyboard.reverse()
    keyboard += [[context.buttons.search(f"{url}/{constants.SEARCH}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = _("Users") + f" [{len(users)}]"

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def semester(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data ^{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)$"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = context.match.group()
    semester_id = context.match.group("semester_id")
    semester = queries.semester(session, semester_id)

    keyboard = [
        [context.buttons.edit(url, "Number"), context.buttons.delete(url, "Semester")],
        [context.buttons.back(url, "/\d+")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = bold(_("Number")) + f": {semester.number}"

    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

    return ONE


async def search(update: Update, context: CustomContext):
    """Runs on callback_data `^{URLPREFIX}/{constants.USERS}/{constants.SEARCH}$`"""

    query = update.callback_query
    await query.answer()

    _ = context.gettext
    message = _("Search user")
    await query.message.reply_text(
        message,
    )

    return constants.SEARCH


@session
async def receive_search(update: Update, context: CustomContext, session: Session):
    """Runs on `Message.text` matching ^(\d+)$"""

    semester_number = int(context.match.groups()[0])

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"^{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)/{EDIT}$",
        url,
    )

    semester_id = int(match.group("semester_id"))
    semester = queries.semester(session, semester_id)
    semester.number = int(semester_number)

    keyboard = [[context.buttons.back(match.group(), f"/{EDIT}", "to Semester")]]
    _ = context.gettext
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = _("Success! {} updated").format(_("Semester number"))
    await update.message.reply_text(message, reply_markup=reply_markup)

    return ONE


# ------------------------- ConversationHander -----------------------------

cmd = COMMANDS
entry_points = [
    CommandHandler(cmd.users.command, user_list),
    CallbackQueryHandler(
        user_list,
        pattern=f"^{URLPREFIX}/{constants.USERS}"
        f"(?:\?p=(?P<page>\d+))?(?:/{constants.IGNORE})?$",
    ),
]

states = {
    ONE: [
        CallbackQueryHandler(
            search, pattern=f"^{URLPREFIX}/{constants.USERS}/{constants.SEARCH}$"
        ),
        CallbackQueryHandler(
            semester,
            pattern=f"^{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)$",
        ),
    ]
}
states.update(
    {
        constants.SEARCH: states[ONE]
        + [
            MessageHandler(filters.TEXT, receive_search),
        ]
    }
)

user_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.USER_,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
