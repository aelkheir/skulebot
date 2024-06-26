"""Contains callbacks and handlers for the NOTIFICATION_ conversaion"""

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ConversationHandler

from src import constants, messages
from src.conversations.material import files, sendall
from src.customcontext import CustomContext
from src.models import File, Material, MaterialType, RefFilesMixin, Review, SingleFile
from src.utils import build_menu, session

# ------------------------- Callbacks -----------------------------

URLPREFIX = constants.NOTIFICATION_


@session
async def material(
    update: Update,
    context: CustomContext,
    session: Session,
):
    """
    Runs on callback_data
    ^{URLPREFIX}/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)$
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    material_id = context.match.group("material_id")
    material = session.get(Material, material_id)

    # here we reply directly with the files.
    if isinstance(material, Review):
        return await sendall.send.__wrapped__(update, context, session)
    if isinstance(material, SingleFile):
        return await files.display.__wrapped__(
            update, context, session, file_id=material.file_id
        )

    keyboard: list[list] = []

    if isinstance(material, RefFilesMixin):
        menu_files = session.scalars(
            select(File).where(File.material_id == material.id)
            # hack to have the order as document, photo, video then by file name
            .order_by(File.type.asc(), File.name)
        ).all()
        files_menu = context.buttons.files_list(f"{url}/{constants.FILES}", menu_files)
        keyboard += build_menu(files_menu, 1)

    if isinstance(material, RefFilesMixin) and len(material.files) > 1:
        keyboard += [[context.buttons.send_all(url)]]

    keyboard += [[context.buttons.show_less(url + "?collapse=1")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = (
        _("t-symbol")
        + "─ 🔔 "
        + material.course.get_name(context.language_code)
        + "\n│ "
        + _("corner-symbol")
        + "── "
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
    await query.answer()

    url = context.match.group()
    material_id = context.match.group("material_id")
    material = session.get(Material, material_id)
    _ = context.gettext

    message = (
        _("t-symbol")
        + "─ 🔔 "
        + material.course.get_name(context.language_code)
        + "\n│ "
        + _("corner-symbol")
        + "── "
        + messages.material_message_text(url, context, material)
    )
    keyboard = [
        [context.buttons.show_more(f"{URLPREFIX}/{material.type}/{material.id}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )


# ------------------------- ConversationHander -----------------------------

ALLTYPES = "|".join([t.value for t in MaterialType])
COLLAPSABLES = "|".join(
    [
        t.value
        for t in MaterialType
        if t
        in [
            MaterialType.ASSIGNMENT,
            MaterialType.LECTURE,
            MaterialType.TUTORIAL,
            MaterialType.LAB,
        ]
    ]
)

notifications_ = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            material,
            pattern=f"^{URLPREFIX}/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)$",
        ),
    ],
    states={
        constants.ONE: [
            CallbackQueryHandler(
                files.display,
                pattern=f"^{URLPREFIX}/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                f"/{constants.FILES}/(?P<file_id>\d+)$",
            ),
            CallbackQueryHandler(
                sendall.send,
                pattern=f"^{URLPREFIX}/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                f"/{constants.ALL}$",
            ),
            CallbackQueryHandler(
                collapse_material,
                pattern=f"^{URLPREFIX}/(?P<material_type>{COLLAPSABLES})"
                "/(?P<material_id>\d+)\?collapse=1$",
            ),
        ]
    },
    fallbacks=[],
    name=constants.NOTIFICATION_,
    per_message=True,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
