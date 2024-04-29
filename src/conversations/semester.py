"""Contains callbacks and handlers for the /semesters conversaion"""

import re
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
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

from src import buttons, messages, queries
from src.constants import ADD, DELETE, EDIT, NUMBER, ONE, SEMESTER_, SEMESTERS
from src.models import RoleName, Semester
from src.utils import build_menu, roles, session

URLPREFIX = SEMESTER_
"""used as a prefix for all `callback data` in this conversation"""

DATA_KEY = SEMESTER_
"""used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------
@roles(RoleName.ROOT)
@session
async def semester_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text `/semesters`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = f"{URLPREFIX}/{SEMESTERS}"

    semesters = queries.semesters(session)
    semester_button_list = buttons.semester_list(semesters, url=url)
    keyboard = build_menu(
        semester_button_list, 2, footer_buttons=buttons.add(url, "Semester")
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Semesters"

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return ONE


# -------------------------- states callbacks ---------------------------
@session
async def semester(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data ^{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)$"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = context.match.group()
    semester_id = context.match.group("semester_id")
    semester = queries.semester(session, semester_id)

    keyboard = [
        [buttons.edit(url, "Number"), buttons.delete(url, "Semester")],
        [buttons.back(url, "/\d+")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"*Number*: {semester.number}"

    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_markdown_v2(message, reply_markup=reply_markup)

    return ONE


@session
async def semester_add(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data ^{URLPREFIX}/{SEMESTERS}/{constants.ADD}$"""

    query = update.callback_query

    max = session.query(func.max(Semester.number)).one_or_none()
    max = max[0] if max[0] is not None else 0

    session.add(Semester(number=max + 1))
    session.flush()
    await query.answer(messages.success_added(f"Semester {max + 1}"))

    return await semester_list.__wrapped__.__wrapped__(update, context, session)


async def semester_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on callback_data {URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)/{EDIT}$"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    message = messages.type_number()
    await query.message.reply_text(
        message,
    )

    return f"{EDIT} {NUMBER}"


@session
async def receive_number(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
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

    keyboard = [[buttons.back(match.group(), f"/{EDIT}", "to Semester")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = messages.success_updated("Semester number")
    await update.message.reply_text(message, reply_markup=reply_markup)

    return ONE


@session
async def semester_delete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data
    {URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)/{DELETE}(?:\?c=(?P<has_confirmed>1|0))?$
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{DELETE}", context.match.group()).group()

    semester_id = context.match.group("semester_id")
    semester = queries.semester(session, semester_id)
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: List
    message: str

    if has_confirmed is None:
        menu_buttons = buttons.delete_group(url=url)
        message = messages.delete_confirm(f"Semester {semester.number}")
    elif has_confirmed == "0":
        menu_buttons = buttons.confirm_delete_group(url=url)
        message = messages.delete_reconfirm(f"Semester {semester.number}")
    elif has_confirmed == "1":
        session.delete(semester)
        menu_buttons = [
            buttons.back(url, text="to Semesters", pattern=rf"/\d+/{DELETE}")
        ]
        message = messages.success_deleted(f"Semester {semester.number}")

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return ONE


# ------------------------- ConversationHander -----------------------------

entry_points = [
    CommandHandler("semesters", semester_list),
]

states = {
    ONE: [
        CallbackQueryHandler(
            semester,
            pattern=f"^{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)$",
        ),
        CallbackQueryHandler(
            semester_add,
            pattern=f"^{URLPREFIX}/{SEMESTERS}/{ADD}$",
        ),
        CallbackQueryHandler(semester_list, pattern=f"^{URLPREFIX}/{SEMESTERS}$"),
        CallbackQueryHandler(
            semester_edit,
            pattern=f"{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)/{EDIT}$",
        ),
        CallbackQueryHandler(
            semester_delete,
            pattern=f"{URLPREFIX}/{SEMESTERS}/(?P<semester_id>\d+)"
            f"/{DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
    ]
}
states.update(
    {
        f"{EDIT} {NUMBER}": states[ONE]
        + [
            MessageHandler(filters.Regex(r"^(\d+)$"), receive_number),
        ]
    }
)

semester_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=SEMESTER_,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
