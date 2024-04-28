import re
from itertools import groupby
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, InputMedia, Update
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import HasNumber
from src.models.enrollment import Enrollment
from src.models.file import File
from src.models.material import (
    Material,
    RefFilesMixin,
    SingleFile,
    __classes__,
    get_material_class,
)
from src.utils import build_media_group, session

TYPES = "|".join(
    [
        cls.__mapper_args__.get("polymorphic_identity")
        for cls in __classes__
        if issubclass(cls, HasNumber)
    ]
)


@session
async def send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    material_type: Optional[str] = None,
):
    """
    {url_prefix}/{constants.COURSES}/(?P<course_id>\d+)
    /(?P<material_type>{ALLTYPES})/$
    """
    query = update.callback_query
    await query.answer()

    material_type = material_type or context.match.group("material_type")
    MaterialClass = get_material_class(material_type)

    files = []

    if issubclass(MaterialClass, RefFilesMixin):
        material_id = context.match.group("material_id")
        files = session.scalars(
            select(File)
            .join(MaterialClass, MaterialClass.id == File.material_id)
            .where(MaterialClass.id == material_id)
            .order_by(File.type, File.id)
        ).all()

    elif issubclass(MaterialClass, SingleFile):
        enrollment_id = context.match.group("enrollment_id")
        course_id = context.match.group("course_id")
        enrollment = session.get(Enrollment, enrollment_id)
        files = session.scalars(
            select(File)
            .join(MaterialClass, MaterialClass.file_id == File.id)
            .where(
                MaterialClass.course_id == course_id,
                MaterialClass.academic_year_id == enrollment.academic_year_id,
            )
            .order_by(File.type, File.id)
        ).all()

    def keygetter(f: File):
        if f.type in ["photo", "video"]:
            return "media"
        return "document"

    for _, group in groupby(files, key=keygetter):
        albums = build_media_group(
            [InputMedia(file.type, file.telegram_id) for file in group]
        )
        for album in albums:
            await query.message.reply_media_group(media=album)

    return constants.ONE


@session
async def receive(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    material_number = int(context.match.groups()[0])

    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
        f"/{constants.EDIT}/{constants.NUMBER}$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Material, material_id)
    if isinstance(material, HasNumber):
        material.number = material_number

        keyboard = [
            [
                buttons.back(
                    url,
                    pattern=rf"/{constants.EDIT}.*$",
                    text=f"to {material.type.capitalize()}",
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = messages.success_updated(f"{material.type.capitalize()} number")
        await update.message.reply_text(message, reply_markup=reply_markup)

        return constants.ONE
    return None
