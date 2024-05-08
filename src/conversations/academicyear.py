"""Contains callbacks and handlers for the /years conversaion"""

import re
from datetime import date
from typing import List

from sqlalchemy import func
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

from src import queries
from src.constants import ACADEMICYEAR_, ACADEMICYEARS, ADD, COMMANDS, DELETE, EDIT, ONE
from src.customcontext import CustomContext
from src.messages import bold
from src.models import AcademicYear, RoleName
from src.utils import build_menu, roles, session

URLPREFIX = ACADEMICYEAR_
"""Used as a prefix for all `callback data` in this conversation"""

DATA_KEY = ACADEMICYEAR_
"""Used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------
@roles(RoleName.ROOT)
@session
async def year_list(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text `/years`"""
    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = f"{URLPREFIX}/{ACADEMICYEARS}"

    academic_years = queries.academic_years(session)
    menu = context.buttons.years_list(academic_years, url)
    keyboard = build_menu(menu, 2, footer_buttons=context.buttons.add(url, "Year"))
    reply_markup = InlineKeyboardMarkup(keyboard)

    _ = context.gettext
    message = _("Academic years")

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return ONE


# -------------------------- states callbacks ---------------------------
@session
async def year(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data ^{URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)$"""

    query: None | CallbackQuery = None
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = context.match.group()
    year_id = int(context.match.group("year_id"))
    year = queries.academic_year(session, year_id)

    keyboard = [
        [context.buttons.edit(url, "Year"), context.buttons.delete(url, "Year")],
        [context.buttons.back(url, "/\d+")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = bold(_("Year")) + f": {year.start} - {year.end}"
    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

    return ONE


@session
async def year_add(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data ^{URLPREFIX}/{ACADEMICYEARS}/{ADD}$"""

    query = update.callback_query

    max = session.query(func.max(AcademicYear.end)).one_or_none()
    max = max[0] if max[0] is not None else date.today().year

    session.add(AcademicYear(start=max, end=max + 1))
    session.flush()

    _ = context.gettext
    await query.answer(
        _("Success! {} created").format(_("Year {} - {}").format(max, max + 1))
    )

    return await year_list.__wrapped__.__wrapped__(update, context, session)


async def year_edit(update: Update, context: CustomContext):
    """Runs on callback_data {URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)/{EDIT}$"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    _ = context.gettext
    message = _("Type year")
    await query.message.reply_text(
        message,
    )

    return EDIT


@session
async def receive_year_edit(update: Update, context: CustomContext, session: Session):
    """Runs with Message.text matching
    `^(?P<start_year>\d{4})\s*-\s*(?P<end_year>\d{4})$`
    """

    start_year, end_year = int(context.match.group("start_year")), int(
        context.match.group("end_year")
    )

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"^{URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)/{EDIT}$",
        url,
    )

    year_id = int(match.group("year_id"))
    year = queries.academic_year(session, year_id)
    year.start = int(start_year)
    year.end = int(end_year)

    keyboard = [[context.buttons.back(url, f"/{EDIT}", "to Year")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = _("Success! {} updated").format(_("Year"))
    await update.message.reply_text(message, reply_markup=reply_markup)

    return ONE


@session
async def year_delete(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `{URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)/{DELETE}(?:\?c=(?P<has_confirmed>1|0))?$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{DELETE}", context.match.group()).group()

    year_id = context.match.group("year_id")
    year = queries.academic_year(session, year_id)
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: List
    message: str
    _ = context.gettext

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message = _("Delete warning {}").format(
            bold(_("Year {} - {}").format(year.start, year.end))
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message = _("Confirm delete warning {}").format(
            bold(_("Year {} - {}").format(year.start, year.end))
        )
    elif has_confirmed == "1":
        session.delete(year)
        menu_buttons = [
            context.buttons.back(
                url, text="to Academic Years", pattern=rf"/\d+/{DELETE}"
            )
        ]
        message = _("Success! {} deleted").format(
            _("Year {} - {}").format(year.start, year.end)
        )

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return ONE


# ------------------------- ConversationHander -----------------------------

cmd = COMMANDS
entry_points = [
    CommandHandler(cmd.years.command, year_list),
]

states = {
    ONE: [
        CallbackQueryHandler(
            year,
            pattern=f"^{URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)$",
        ),
        CallbackQueryHandler(
            year_add,
            pattern=f"^{URLPREFIX}/{ACADEMICYEARS}/{ADD}$",
        ),
        CallbackQueryHandler(year_list, pattern=f"^{URLPREFIX}/{ACADEMICYEARS}$"),
        CallbackQueryHandler(
            year_edit, pattern=f"{URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)/{EDIT}$"
        ),
        CallbackQueryHandler(
            year_delete,
            pattern=f"{URLPREFIX}/{ACADEMICYEARS}/(?P<year_id>\d+)"
            f"/{DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
    ]
}
states.update(
    {
        EDIT: states[ONE]
        + [
            MessageHandler(
                filters.Regex(r"^(?P<start_year>\d{4})\s*-\s*(?P<end_year>\d{4})$"),
                receive_year_edit,
            ),
        ]
    }
)

academicyear_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=ACADEMICYEAR_,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
