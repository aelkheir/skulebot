import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from telegram import Document, InlineKeyboardMarkup, Update, Video
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import HasNumber
from src.models.enrollment import Enrollment
from src.models.file import File
from src.models.material import (
    REVIEW_TYPES,
    MaterialType,
    Review,
    SingleFile,
    get_material_class,
)
from src.models.user import User
from src.utils import build_menu, session


@session
async def handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session, back
):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/{constants.ADD}$`
    """
    query = update.callback_query

    material_type = context.match.group("material_type")
    course_id = int(context.match.group("course_id"))
    if enrollment_id := context.match.group("enrollment_id"):
        enrollment = session.get(Enrollment, enrollment_id)
        academic_year_id = enrollment.academic_year_id
    elif year_id := context.match.group("year_id"):
        academic_year_id = year_id

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
            messages.success_added(f"New {material_type.capitalize()} {max+1}")
        )

        return await back.__wrapped__(update, context, session)

    if issubclass(MaterialClass, SingleFile):
        await query.answer()
        context.chat_data["url"] = context.match.group()

        message = messages.send_files(MaterialClass.MEDIA_TYPES)
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
            await query.answer(messages.success_created("Exam"))

            return await back.__wrapped__(
                update, context, session, material_id=review.id
            )

        await query.answer()
        menu = buttons.review_types(context.match.group())

        keyboard = build_menu(
            menu,
            2,
            footer_buttons=buttons.back(context.match.group(), rf"/{constants.ADD}.*"),
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            messages.title(context.match, session)
            + "\n"
            + messages.course_text(context.match, session)
            + "\nSelect type"
        )
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )

        return constants.ONE
    return None


ALLTYPES = "|".join([t.value for t in MaterialType])


@session
async def receive_material_file(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session, url_prefix
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
            buttons.view_added(id=material.id, url=url, text="File"),
            buttons.edit(f"{file_url}/{constants.SOURCE}", "Source"),
        ]
        if not url.startswith(constants.CONETENT_MANAGEMENT_):
            menu.insert(
                1,
                buttons.publish(
                    callback_data=re.sub(rf"/{constants.ADD}", f"/{material.id}", url)
                ),
            )

        keyboard = build_menu(menu, 2)

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = messages.success_added(file_name)
        await update.message.reply_text(message, reply_markup=reply_markup)

        return f"{constants.ADD} {constants.MATERIALS}"
    return None
