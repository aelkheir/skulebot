from itertools import groupby
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InputMedia, Update

from src import constants
from src.customcontext import CustomContext
from src.models import Enrollment, File, HasNumber, RefFilesMixin, SingleFile
from src.models.material import __classes__, get_material_class
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
    context: CustomContext,
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
            .order_by(File.type.asc(), File.name)
        ).all()

    def keygetter(f: File):
        if f.type in ["photo", "video"]:
            return "media"
        if f.type == "document":
            return "document"
        return "voice"

    for group, group_files in groupby(files, key=keygetter):
        if group == "voice":
            for file in group_files:
                await update.effective_message.reply_voice(file.telegram_id)
            continue
        albums = build_media_group(
            [InputMedia(file.type, file.telegram_id) for file in group_files]
        )
        for album in albums:
            await query.message.reply_media_group(media=album)

    return constants.ONE
