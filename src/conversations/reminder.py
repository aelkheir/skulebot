"""Contains callbacks and handlers for the NOTIFICATION_ conversaion"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from babel.dates import format_timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ConversationHandler

from src import constants, messages
from src.conversations.material import files, sendall
from src.customcontext import CustomContext
from src.models import File, MaterialType
from src.models.material import Assignment
from src.utils import build_menu, session

# ------------------------- Callbacks -----------------------------

URLPREFIX = constants.REMINDER_


@session
async def assignment(
    update: Update,
    context: CustomContext,
    session: Session,
):
    """
    Runs on callback_data
    ^{URLPREFIX}/(?P<material_type>{TYPES})/(?P<material_id>\d+)$
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    material_id = context.match.group("material_id")
    material = session.get(Assignment, material_id)

    keyboard: list[list] = []

    menu_files = session.scalars(
        select(File).where(File.material_id == material.id).order_by(File.name)
    ).all()
    files_menu = context.buttons.files_list(f"{url}/{constants.FILES}", menu_files)
    keyboard += build_menu(files_menu, 1)

    if len(material.files) > 1:
        keyboard += [[context.buttons.send_all(url)]]

    keyboard += [[context.buttons.show_less(url + "?collapse=1")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext

    message = (
        "⏰ "
        + _("Reminder")
        + "\n\n"
        + _("t-symbol")
        + "─ "
        + material.course.get_name(context.language_code)
        + "\n│ "
        + _("corner-symbol")
        + " "
        + messages.material_message_text(url, context, material)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def collapse_material(
    update: Update,
    context: CustomContext,
    session: Session,
):
    """
    Runs on callback_data
    ^{URLPREFIX}/(?P<material_type>{COLLAPSABLES})/(?P<material_id>\d+)?collapse=1$
    """

    query = update.callback_query

    assignment_id = context.match.group("material_id")
    assignment = session.get(Assignment, assignment_id)
    zone = ZoneInfo("Africa/Khartoum")
    delta = assignment.deadline.astimezone(zone) - datetime.now(zone)
    seconds = delta.total_seconds()
    _ = context.gettext

    if seconds < 0:
        await query.answer(_("Deadline passed"), show_alert=True)
        return

    await query.answer()
    course_name = assignment.course.get_name(context.language_code)
    assignment_title = _(assignment.type) + f" {assignment.number}"

    days = seconds // (24 * 60 * 60)
    hours = (seconds // (60 * 60)) % 24
    minutes = (seconds // (60)) % 60
    parts = []
    if days:
        part = format_timedelta(
            timedelta(days=days),
            granularity="days",
            format="long",
            threshold=1,
            locale=context.language_code,
        )
        parts.append(part)
    if hours:
        part = format_timedelta(
            timedelta(hours=hours),
            granularity="hours",
            format="long",
            threshold=1,
            locale=context.language_code,
        )
        parts.append(part)
    if minutes and not days:
        part = format_timedelta(
            timedelta(minutes=minutes),
            granularity="minutes",
            format="long",
            threshold=1,
            locale=context.language_code,
        )
        parts.append(part)

    remaining = (
        _("time remaining {} {}").format(*parts)
        if len(parts) > 1
        else _("time remaining {}").format(*parts)
    )

    message = (
        "⏰ "
        + _("Reminder")
        + "\n\n"
        + _("{} of {} is due in {}").format(assignment_title, course_name, remaining)
    )
    keyboard = [
        [context.buttons.show_more(f"{URLPREFIX}/{assignment.type}/{assignment.id}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=message, reply_markup=reply_markup)


# ------------------------- ConversationHander -----------------------------

TYPES = MaterialType.ASSIGNMENT

reminder_ = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            assignment,
            pattern=f"^{URLPREFIX}/(?P<material_type>{TYPES})/(?P<material_id>\d+)$",
        ),
    ],
    states={
        constants.ONE: [
            CallbackQueryHandler(
                files.display,
                pattern=f"^{URLPREFIX}/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
                f"/{constants.FILES}/(?P<file_id>\d+)$",
            ),
            CallbackQueryHandler(
                sendall.send,
                pattern=f"^{URLPREFIX}/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
                f"/{constants.ALL}$",
            ),
            CallbackQueryHandler(
                collapse_material,
                pattern=f"^{URLPREFIX}/(?P<material_type>{TYPES})"
                "/(?P<material_id>\d+)\?collapse=1$",
            ),
        ]
    },
    fallbacks=[],
    name=constants.REMINDER_,
    per_message=True,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
