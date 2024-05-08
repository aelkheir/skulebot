import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from telegram import Document, InlineKeyboardMarkup, Update, Video
from telegram.constants import ParseMode

from src import constants, messages, queries
from src.customcontext import CustomContext
from src.models import (
    Enrollment,
    File,
    HasNumber,
    MaterialType,
    Review,
    SingleFile,
    User,
)
from src.models.material import REVIEW_TYPES, get_material_class
from src.utils import build_menu, session


@session
async def handler(update: Update, context: CustomContext, session: Session, back):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/{constants.ADD}$`
    """
    query = update.callback_query

    material_type = context.match.group("material_type")
    if enrollment_id := context.match.group("enrollment_id"):
        enrollment = session.get(Enrollment, enrollment_id)
        academic_year_id = enrollment.academic_year_id
    elif year_id := context.match.group("year_id"):
        academic_year_id = year_id
    course_id = int(context.match.group("course_id"))
    course = queries.course(session, course_id)

    _ = context.gettext
    MaterialClass = get_material_class(material_type)
    if issubclass(MaterialClass, HasNumber):
        max = session.scalar(
            select(func.max(MaterialClass.number)).filter(
                MaterialClass.course_id == course_id,
                MaterialClass.academic_year_id == academic_year_id,
            )
        )
        max = max if max else 0
        session.add(
            MaterialClass(
                course_id=course_id,
                academic_year_id=academic_year_id,
                published=False,
                number=max + 1,
            )
        )
        session.flush()

        await query.answer(
            _("Success! {} added").format(_(material_type) + f" {max + 1}")
        )

        return await back.__wrapped__(update, context, session)

    if issubclass(MaterialClass, SingleFile):
        await query.answer()
        context.chat_data["url"] = context.match.group()

        message = _("Send files ({})").format(", ".join(MaterialClass.MEDIA_TYPES))
        await query.message.reply_text(message)
        return f"{constants.ADD} {constants.MATERIALS}"

    if issubclass(MaterialClass, Review):
        type_key = context.match.groupdict().get("type_key")
        if type_key:
            t = REVIEW_TYPES[type_key]
            review = MaterialClass(
                course_id=course_id,
                academic_year_id=academic_year_id,
                published=False,
                en_name=t["en_name"],
                ar_name=t["ar_name"],
            )
            session.add(review)
            session.flush()
            await query.answer(_("Success! {} created").format(_(review.type)))

            return await back.__wrapped__(
                update, context, session, material_id=review.id
            )

        await query.answer()
        menu = context.buttons.review_types(context.match.group())

        keyboard = build_menu(
            menu,
            2,
            footer_buttons=context.buttons.back(
                context.match.group(), rf"/{constants.ADD}.*"
            ),
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            messages.title(context.match, session, context=context)
            + "\n"
            + _("t-symbol")
            + "─ "
            + course.get_name(context.language_code)
            + "\n"
            + messages.material_type_text(context.match, context=context)
            + "\n"
            + _("Select {}").format(_("Type"))
        )
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )

        return constants.ONE
    return None


ALLTYPES = "|".join([t.value for t in MaterialType])


@session
async def receive_material_file(
    update: Update, context: CustomContext, session: Session, url_prefix
):
    message = update.message

    url: str = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"{url_prefix}/(?P<material_type>{ALLTYPES})",
        url,
    )
    material_type = match.group("material_type")
    MaterialClass = get_material_class(material_type)
    media_type = None
    for type_ in MaterialClass.MEDIA_TYPES:
        if getattr(message, type_, None) is not None:
            media_type = type_
            break
    if media_type is None:
        return None

    attachement = message.effective_attachment

    file_name = (
        attachement.file_name if isinstance(attachement, (Document, Video)) else None
    )
    file_id = (
        attachement.file_id if isinstance(attachement, (Document, Video)) else None
    )

    _ = context.gettext
    course_id = int(match.group("course_id"))
    if enrollment_id := match.group("enrollment_id"):
        enrollment = session.get(Enrollment, enrollment_id)
        academic_year_id = enrollment.academic_year_id
    elif year_id := match.group("year_id"):
        academic_year_id = year_id

    if issubclass(MaterialClass, SingleFile):
        file = File(
            telegram_id=file_id,
            name=file_name,
            type=media_type,
            source=None,
            uploader=session.get(User, context.user_data["id"]),
        )
        session.add(file)
        material = MaterialClass(
            academic_year_id=academic_year_id,
            course_id=course_id,
            published=False,
            file=file,
        )
        session.add(material)
        session.flush()

        file_url = re.sub(
            f"/{constants.ADD}",
            f"/{material.id}/{constants.FILES}/{file.id}",
            url,
        )
        menu = [
            context.buttons.edit(f"{file_url}/{constants.SOURCE}", _("Source")),
        ]
        if not url.startswith(constants.CONETENT_MANAGEMENT_):
            menu.insert(
                1,
                context.buttons.publish(
                    callback_data=re.sub(rf"/{constants.ADD}", f"/{material.id}", url)
                ),
            )
        keyboard = build_menu(
            menu,
            2,
            footer_buttons=context.buttons.back(
                url, rf"/{constants.ADD}", text=_(f"{material.type}s")
            ),
            reverse=context.language_code == constants.AR,
        )
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = _("Success! {} added").format(file_name)
        await update.message.reply_text(message, reply_markup=reply_markup)

        return f"{constants.ADD} {constants.MATERIALS}"
    return None
