import re

from sqlalchemy.orm import Session
from telegram import Document, InlineKeyboardMarkup, Update, Video
from telegram.constants import ParseMode

from src import constants, messages
from src.customcontext import CustomContext
from src.messages import italic
from src.models import File, Material, User
from src.models.material import get_material_class
from src.utils import build_menu, session, user_mode


@session
async def file(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.FILES}}/(\d+)$`
    """
    query = update.callback_query
    await query.answer()

    url = context.match.group()

    if user_mode(url):
        return await display(update, context)

    file_id = int(context.match.group("file_id"))
    material_id = int(context.match.group("material_id"))
    file = session.get(File, file_id)
    material = session.get(Material, material_id)

    menu_buttons = [
        *context.buttons.file_menu(url=url),
        context.buttons.back(url=url, pattern=f"/{constants.FILES}/\\d+"),
    ]
    keyboard = build_menu(
        menu_buttons[1:-1],
        2,
        header_buttons=menu_buttons[0],
        footer_buttons=menu_buttons[-1],
        reverse=context.language_code == constants.AR,
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = (
        messages.title(context.match, session, context=context)
        + "\n"
        + _("t-symbol")
        + "─ "
        + material.course.get_name(context.language_code)
        + "\n"
        + messages.material_type_text(context.match, context=context)
        + "│   "
        + _("corner-symbol")
        + "── "
        + messages.material_message_text(url, context, material)
        + "\n\n"
        + messages.file_text(file, context=context)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def delete(
    update: Update,
    context: CustomContext,
    session: Session,
    back,
):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.FILES}/(\d+)/{constants.DELETE}$`
    """

    query = update.callback_query

    file_id = int(context.match.group("file_id"))
    file = session.get(File, file_id)
    file_name = file.name
    session.delete(file)
    session.flush()
    _ = context.gettext

    await query.answer(_("Success! {} deleted").format(file_name))

    return await back.__wrapped__(update, context, session)


@session
async def display(
    update: Update, context: CustomContext, session: Session, file_id=None
):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.FILES}/(\d+)/{constants.DISPLAY}$`

    Arg:
      file_id: int: file_id to display. Materials which subclass `SingleFile`
      will not reach a state where file_id is availabe via match. To display them,
      manually call this handler with file_id argument.

    """
    query = update.callback_query
    await query.answer()

    file_id = file_id or int(context.match.group("file_id"))
    file = session.get(File, file_id)

    reply_markup = None
    if source := file.source:
        keyboard = [[context.buttons.source(url=source)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    sender = (
        query.message.reply_document
        if file.type == "document"
        else (
            query.message.reply_video
            if file.type == "video"
            else query.message.reply_photo
        )
    )

    caption = italic(file.name)

    await sender(
        file.telegram_id,
        reply_markup=reply_markup,
        caption=caption,
        parse_mode=ParseMode.HTML,
    )
    return constants.ONE


async def add(update: Update, context: CustomContext):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.FILES}/{constants.ADD}$`
    """
    query = update.callback_query
    await query.answer()

    context.chat_data["url"] = context.match.group()
    material_type = context.match.group("material_type")
    MaterialClass = get_material_class(material_type)

    _ = context.gettext
    message = _("Send files ({})").format(", ".join(MaterialClass.MEDIA_TYPES))
    await query.message.reply_text(message)

    return constants.ADD


@session
async def receive_file(update: Update, context: CustomContext, session: Session):
    message = update.message

    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        "/\d+/(?P<material_type>\w+)/(?P<material_id>\d+)"
        f"/{constants.FILES}/{constants.ADD}$",
        url,
    )
    material_type = match.group("material_type")
    MaterialClass = get_material_class(material_type)
    media_type = None
    for type_ in MaterialClass.MEDIA_TYPES:
        if (attr := getattr(message, type_, None)) is not None and bool(attr):
            media_type = type_
            break
    if media_type is None:
        return None

    attachement = message.effective_attachment

    file_name = (
        attachement.file_name
        if isinstance(attachement, (Document, Video))
        else attachement[-1].file_unique_id
    )
    telegram_id = (
        attachement.file_id
        if isinstance(attachement, (Document, Video))
        else attachement[-1].file_id
    )

    material_id = int(match.group("material_id"))

    file_type = (
        "document" if message.document else "video" if message.video else "photo"
    )
    file = File(
        telegram_id=telegram_id,
        type=file_type,
        name=file_name,
        material_id=material_id,
        uploader=session.get(User, context.user_data["id"]),
    )
    session.add(file)
    session.flush()

    _ = context.gettext
    keyboard = build_menu(
        [
            context.buttons.edit(
                re.sub(f"/{constants.ADD}", f"/{file.id}", url)
                + f"/{constants.SOURCE}",
                _("Source"),
            ),
        ],
        2,
        footer_buttons=context.buttons.back(
            url, rf"/{constants.FILES}/{constants.ADD}"
        ),
        reverse=context.language_code == constants.AR,
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = _("Success! {} added").format(file_name)
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ADD


async def source_edit(update: Update, context: CustomContext):
    """
    Runs on callback_data
    `{url_prefix}/{constants.COURSES}/(?P<course_id>\d+)
    /(?P<cls>{CLS_GROUP})/(?P<item_id>\d+)/{constants.FILES}/(?P<file_id>\d+)
    /{constants.SOURCE}/{constants.EDIT}$`
    """

    query = update.callback_query
    await query.answer()

    context.chat_data["url"] = context.match.group()
    _ = context.gettext

    message = _("Type link") + " " + _("/empty to clear {}").format(_("Source"))
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.SOURCE}"


@session
async def receive_source(update: Update, context: CustomContext, session: Session):
    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(f"/{constants.FILES}/(?P<file_id>\d+)", url)
    file_id = int(match.group("file_id"))
    file = session.get(File, file_id)
    _ = context.gettext

    back_patern = (
        rf"/{constants.SOURCE}.*" if file.material_id else rf"/{constants.FILES}.*"
    )
    keyboard = [[context.buttons.back(url, pattern=back_patern)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message.text == "/empty":
        file.source = None
        message = _("Success! {} removed").format(_("Source"))
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE

    link: str
    parsed_entities = update.message.parse_entities("url")
    if len(parsed_entities) > 1:
        return None
    for entity, value in parsed_entities.items():
        if entity.offset != 0:
            return None
        link = value
    file.source = link

    message = _("Success! {} updated").format(_("Source"))
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE
