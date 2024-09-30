import os
from datetime import datetime
from itertools import groupby

import google.generativeai as genai
from google.protobuf.struct_pb2 import Struct
from sqlalchemy import and_, select
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.orm import Session as SessionType
from telegram import InputMedia, Update

from src import messages, queries
from src.customcontext import CustomContext
from src.database import Session
from src.models import REVIEW_TYPES as RT
from src.models import Course, Material
from src.models import MaterialType as MT
from src.models.file import File
from src.models.material import RefFilesMixin, Review, SingleFile, get_material_class
from src.utils import build_media_group, session

genai.configure(api_key=os.environ["GEMINI_API_KEY"])


with Session.begin() as s:
    courses = s.scalars(select(Course)).all()
    s.expunge_all()


HAS_NUMBER = [
    MT.LECTURE,
    MT.TUTORIAL,
    MT.LAB,
    MT.ASSIGNMENT,
]

SINGLE_FILE = [
    MT.REFERENCE,
    MT.SHEET,
    MT.TOOL,
]


@session
async def query_materials(
    args: Struct, update: Update, context: CustomContext, session: SessionType
):
    course_name = args["course_name"]
    type_ = args["type_"]
    if type_ in mapper:
        type_ = mapper[type_]
    filters = {}
    if args.get("filters"):
        filters = dict(args["filters"])
        for key in tuple(filters.keys()):
            if key in mapper:
                filters[mapper[key]] = filters[key]
    should_send_result = args["should_send_result"]

    MaterialClass = get_material_class(type_)

    where = []
    for key in dir(MaterialClass):
        attr = getattr(MaterialClass, key)
        if not isinstance(attr, InstrumentedAttribute):
            continue
        if key not in filters:
            continue
        if filters[key] is None:
            continue

        if key == "date":
            where += [
                and_(
                    getattr(MaterialClass, key) >= datetime(int(filters["date"]), 1, 1),
                    getattr(MaterialClass, key)
                    <= datetime(int(filters["date"]) + 1, 1, 1),
                )
            ]
            continue

        where += [getattr(MaterialClass, key) == filters[key]]

    enrollment = queries.user_most_recent_enrollment(
        session, user_id=context.user_data["id"]
    )

    materials = session.scalars(
        select(MaterialClass)
        .join(Course)
        .where(
            Course.en_name == course_name,
            MaterialClass.academic_year_id == enrollment.academic_year_id,
            *where,
        )
    ).all()

    if should_send_result:
        for m in materials:
            await send(update, context, session, m)

    return (list(map(str, materials)), should_send_result)


async def send(
    update: Update,
    context: CustomContext,
    session: SessionType,
    material: Material,
):
    files = []
    MaterialClass = material.__class__
    if isinstance(material, RefFilesMixin):
        files = session.scalars(
            select(File)
            .join(Material, Material.id == File.material_id)
            .where(Material.id == material.id)
            .order_by(File.type, File.id)
        ).all()

    elif isinstance(material, SingleFile):
        files = session.scalars(
            select(File)
            .join(MaterialClass, MaterialClass.file_id == File.id)
            .where(
                Material.id == material.id,
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
        _ = context.gettext
        caption = None
        for i, album in enumerate(albums):
            if isinstance(material, Review):
                caption = messages.material_title_text(
                    context.match, material, context.language_code
                )
                caption += (
                    "\n" + _("{} of {}").format(i + 1, len(albums))
                    if len(albums) > 1
                    else ""
                )

            await update.message.reply_media_group(media=album, caption=caption)


Functions = {
    "query_materials": query_materials,
}

# Globals
chats: dict[int, genai.ChatSession] = {}
models: dict[tuple[int, int], genai.GenerativeModel] = {}


mapper = {"type_": "en_name", "exam": MT.REVIEW.value}


def create_decalarations(courses: list[str]):
    return genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(
                name="query_materials",
                description="Query course materials materials.",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "course_name": genai.protos.Schema(
                            type=genai.protos.Type.STRING,
                            enum=courses,
                            description="the course name of the material belongs to.",
                        ),
                        "type_": genai.protos.Schema(
                            type=genai.protos.Type.STRING,
                            enum=[
                                mt.value if mt.value != MT.REVIEW.value else "exam"
                                for mt in MT
                            ],
                            description="the type of the material.",
                        ),
                        "should_send_result": genai.protos.Schema(
                            type=genai.protos.Type.BOOLEAN,
                            description="`True` only when students want the actual"
                            " files to download. `False` when asking only about "
                            "information about the materials",
                            nullable=False,
                        ),
                        "filters": genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            description="Optional, Describes attibutes of the material",
                            nullable=True,
                            properties={
                                "number": genai.protos.Schema(
                                    type=genai.protos.Type.INTEGER,
                                    description="the order of the material. set only"
                                    " when the `type_` in ['lecture', 'tutorial',"
                                    " 'lab', 'assignment']",
                                    nullable=True,
                                ),
                                "type_": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    enum=[
                                        type_
                                        for t in RT.values()
                                        for type_ in t.values()
                                    ],
                                    description="Optional. Default None."
                                    "the type of the exam. set only"
                                    " when the `type_` property is `exam`.",
                                    nullable=True,
                                ),
                            },
                        ),
                    },
                    required=["course_name", "type_", "should_send_result"],
                ),
            ),
        ]
    )


def create_model(key: tuple[int, int], user_id: int, session: SessionType):
    courses = queries.user_courses(
        session,
        program_id=key[0],
        semester_id=key[1],
        user_id=user_id,
    )
    declarations = create_decalarations([c.en_name for c in courses])
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash-exp-0827",
        tools=[declarations],
        system_instruction="You are a student assistant to help users find course "
        "materials. Be very brief but friendly ",
        generation_config=genai.GenerationConfig(temperature=0),
    )


def get_user_chat(user_data: dict, session: SessionType) -> genai.ChatSession:
    chat = chats.get(user_data["telegram_id"])
    if chat is None:
        enrollment = queries.user_most_recent_enrollment(
            session, user_id=user_data["id"]
        )
        model = models.get((enrollment.program.id, enrollment.semester.id))
        if model is None:
            model = create_model(
                key=(enrollment.program.id, enrollment.semester.id),
                user_id=user_data["id"],
                session=session,
            )
            models[(enrollment.program.id, enrollment.semester.id)] = model
        chat = model.start_chat()
        chats[user_data["telegram_id"]] = chat
    return chat
