"""Contains callbacks and handlers for the /users conversaion"""

import contextlib
from typing import Optional

from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import constants, queries
from src.constants import COMMANDS
from src.customcontext import CustomContext
from src.models import RoleName
from src.models.user import User
from src.utils import Pager, build_menu, roles, session, set_my_commands

URLPREFIX = constants.USER_
"""used as a prefix for all `callback data` in this conversation"""

DATA_KEY = constants.USER_
"""used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------
@roles(RoleName.ROOT)
@session
async def user_list(
    update: Update,
    context: CustomContext,
    session: Session,
    search_query: Optional[str] = None,
):
    """Runs with messages.test `'/users'` or on callback_data
    `^{URLPREFIX}/{constants.USERS}
    (?:\?(p=(?P<page>\d+))?(?:&)?(?:q=(?P<query>\w+))?)?
    (?:/{constants.IGNORE})?$`
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
        if search_query is None:
            search_query = context.match.group("query") or None
    users = queries.users(session, query=search_query)

    pager = Pager[User](users, offset, 30)

    user_button_list = await context.buttons.user_list(
        pager.items,
        url,
        context=context,
        end=f"?q={search_query}" if search_query else None,
    )
    keyboard = build_menu(
        user_button_list,
        3,
        reverse=context.language_code == constants.AR,
    )
    if pager.has_next or pager.has_previous:
        pager_keyboard = []
        keyboard.append(pager_keyboard)
        search_param = f"&q={search_query}" if search_query else ""
        if pager.has_previous:
            pager_keyboard.append(
                context.buttons.previous_page(
                    f"{url}?p={pager.previous_offset}{search_param}"
                )
            )
        pager_keyboard.append(
            context.buttons.current_page(
                pager.current_page, pager.number_of_pages, f"{url}/{constants.IGNORE}"
            )
        )
        if pager.has_next:
            pager_keyboard.append(
                context.buttons.next_page(f"{url}?p={pager.next_offset}{search_param}")
            )
        if context.language_code == constants.AR:
            pager_keyboard.reverse()

    if search_query is None:
        keyboard += [[context.buttons.search(f"{url}/{constants.SEARCH}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = _("Results") if search_query is not None else _("Users")
    message += f" [{len(users)}]"

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def user(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)(?:\?q=(?P<query>\w+))?$`"""

    query = update.callback_query
    await query.answer()

    search_query = context.match.group("query")
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    user_data: dict = user.user_data.data
    _ = context.gettext

    search_param = ("?q=" + search_query) if search_query else ""
    keyboard = [
        [
            InlineKeyboardButton(
                _("Broadcast"),
                callback_data=f"{URLPREFIX}/{constants.USERS}/{user_id}/{constants.BROADCAST_}",
            ),
        ],
        [
            context.buttons.back(
                absolute_url=f"{URLPREFIX}/{constants.USERS}{search_param}"
            ),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = _("Full name") + f": {user_data.get('full_name')}"
    message += (
        ("\n" + _("Username") + f": @{username}")
        if (username := user_data.get("username"))
        else ""
    )
    message += "\n" + _("Telegram id") + f": {user.telegram_id}"

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


async def send(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/\d+/{constants.BROADCAST_}$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url
    _ = context.gettext

    message = _("Type message")
    await query.message.reply_text(
        message,
    )

    return constants.BROADCAST_


@session
async def receive_message(update: Update, context: CustomContext, session: Session):
    """Runs on `Message.text` matching filters.ALL"""

    url = context.chat_data[DATA_KEY]["url"]
    context.chat_data.setdefault(DATA_KEY, {})["message_id"] = update.message.id

    _ = context.gettext
    keyboard = build_menu(
        [
            InlineKeyboardButton(
                _("Send"),
                callback_data=f"{url}?o=send",
            ),
            InlineKeyboardButton(_("Preview"), callback_data=f"{url}?o=preview"),
        ],
        2,
    )
    _ = context.gettext
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = _("Select action")
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def action(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    ^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.BROADCAST_}?o=(?P<option>\w+)
    """

    query = update.callback_query
    await query.answer()

    option = context.match.group("option")
    message_id = context.chat_data[DATA_KEY]["message_id"]
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id)

    if option == "preview":
        await context.bot.copy_message(
            update.effective_chat.id,
            from_chat_id=update.effective_chat.id,
            message_id=message_id,
        )
        return

    success = await query.delete_message()
    if success:
        with contextlib.suppress(Forbidden):
            message = await context.bot.copy_message(
                user.chat_id,
                from_chat_id=update.effective_chat.id,
                message_id=message_id,
            )

            if message:
                await context.bot.send_message(
                    update.effective_chat.id,
                    text=context.gettext("Done broadcasting message"),
                )
                await set_my_commands(context.bot, user)


async def search(update: Update, context: CustomContext):
    """Runs on callback_data `^{URLPREFIX}/{constants.USERS}/{constants.SEARCH}$`"""

    query = update.callback_query
    await query.answer()

    _ = context.gettext
    message = _("Search users")
    await query.message.reply_text(
        message,
    )

    return constants.SEARCH


@session
async def receive_search(update: Update, context: CustomContext, session: Session):
    """Runs on `Message.text` matching ^(\d+)$"""

    search_query = update.message.text
    return await user_list.__wrapped__.__wrapped__(
        update, context, session, search_query
    )


# ------------------------- ConversationHander -----------------------------

cmd = COMMANDS
entry_points = [
    CommandHandler(cmd.users.command, user_list),
    CallbackQueryHandler(
        user_list,
        pattern=f"^{URLPREFIX}/{constants.USERS}"
        f"(?:\?(p=(?P<page>\d+))?(?:&)?(?:q=(?P<query>\w+))?)?(?:/{constants.IGNORE})?$",
    ),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            search, pattern=f"^{URLPREFIX}/{constants.USERS}/{constants.SEARCH}$"
        ),
        CallbackQueryHandler(
            user,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)(?:\?q=(?P<query>\w+))?$",
        ),
        CallbackQueryHandler(
            send,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.BROADCAST_}$",
        ),
        CallbackQueryHandler(
            action,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.BROADCAST_}\?o=(?P<option>\w+)$",
        ),
    ]
}
states.update(
    {
        constants.SEARCH: states[constants.ONE]
        + [
            MessageHandler(filters.TEXT, receive_search),
        ]
    }
)

states.update(
    {
        constants.BROADCAST_: states[constants.ONE]
        + [
            MessageHandler(filters.ALL, receive_message),
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
