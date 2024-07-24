"""Contains callbacks and handlers for all material types.

This includes:
    * Lecture
    * Lab
    * Tutorial
    * Reference
    * Tool
    * Assignment
    * Review

This conversation takes care of displaying all the subsequent menus,
performing actions after pressing on any material collection.

Entry points:
    - Triggered when pressing on a material type collection such as
      a "Labs" `InlineKeyBoardButton` inside a course menu.

      Example:
      -------
      Advanced Database.

      `Lecure 1` | `Lecture 2` | `Lecture 3`

      `Labs`            |       `Tutorials`

      --------
      Pressing on any of the above buttons will trigger an entry point of this
      conversation.
"""

import re
from functools import partial
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import constants, messages, queries
from src.conversations.material import (
    add,
    date,
    deadline,
    delete,
    files,
    number,
    publish,
    sendall,
)
from src.customcontext import CustomContext
from src.models import (
    Assignment,
    Enrollment,
    File,
    HasNumber,
    Lecture,
    Material,
    MaterialType,
    RefFilesMixin,
    Review,
    SingleFile,
)
from src.models.material import get_material_class
from src.utils import build_menu, session, user_mode


# ------------------------------- entry_points ---------------------------
@session
async def material_list(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data
    `{url_prefix}/(?P<material_type>{ALLTYPES})$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler will be called from another
    # handler (`item_add`), and thus altering the url
    url = re.search(rf".*/({ALLTYPES})", context.match.group()).group()

    material_type = context.match.group("material_type")
    course_id = int(context.match.group("course_id"))
    course = queries.course(session, course_id)

    academic_year_id: int
    if enrollment_id := context.match.group("enrollment_id"):
        enrollment = session.get(Enrollment, enrollment_id)
        academic_year_id = enrollment.academic_year_id
    else:
        year_id = context.match.group("year_id")
        academic_year_id = year_id

    MaterialClass = get_material_class(material_type)
    filters = [
        MaterialClass.course_id == course_id,
        MaterialClass.academic_year_id == academic_year_id,
    ]
    if user_mode(url):
        filters.append(MaterialClass.published)
    if issubclass(MaterialClass, HasNumber):
        materials = (
            session.query(MaterialClass)
            .where(MaterialClass.type == material_type)
            .filter(*filters)
            .order_by(MaterialClass.number)
            .all()
        )
    elif issubclass(MaterialClass, SingleFile):
        materials = (
            session.query(MaterialClass)
            .join(File, File.id == MaterialClass.file_id)
            .where(MaterialClass.type == material_type)
            .filter(*filters)
            .order_by(File.name)
            .all()
        )
    elif issubclass(MaterialClass, Review):
        materials = (
            session.query(MaterialClass)
            .where(MaterialClass.type == material_type)
            .filter(*filters)
            .order_by(MaterialClass.date.desc(), MaterialClass.en_name)
            .all()
        )

    material_buttons = context.buttons.material_list(url, materials)

    n_columns = 3 if materials and isinstance(materials[0], HasNumber) else 1
    keyboard = build_menu(
        material_buttons, n_columns, reverse=context.language_code == constants.AR
    )
    _ = context.gettext

    if not user_mode(url):
        keyboard += build_menu(
            [
                context.buttons.back(url, pattern=rf"/({ALLTYPES})$"),
                context.buttons.add(url, _(material_type)),
            ],
            2,
            reverse=context.language_code == constants.AR,
        )
    else:
        if issubclass(MaterialClass, SingleFile) and len(materials) > 1:
            keyboard += [[context.buttons.send_all(url)]]
        keyboard += [
            [
                context.buttons.back(
                    url,
                    pattern=rf"/({ALLTYPES})$",
                )
            ]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        messages.title(context.match, session, context=context)
        + "\n"
        + _("t-symbol")
        + "─ "
        + course.get_name(context.language_code)
        + "\n"
        + messages.material_type_text(context.match, context=context)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# -------------------------- states callbacks ---------------------------


@session
async def material(
    update: Update,
    context: CustomContext,
    session: Session,
    material_id: Optional[int] = None,
):
    """
    {url_prefix}
    /(?P<material_type>{TYPES})/(?P<material_id>\d+)$
    """

    query = update.callback_query
    await query.answer()

    material_type = context.match.group("material_type")
    _ = context.gettext

    # url here is calculated because this handler will be called from another
    # handler (`file_delete`), and thus altering the url

    url: str
    if not material_id:
        match = re.search(rf".*/({ALLTYPES})/\d+", context.match.group())
        url = match.group()
    elif material_id:
        url = re.sub(rf"/{constants.ADD}.*$", f"/{material_id}", context.match.group())

    material_id = material_id or context.match.group("material_id")
    material = session.get(Material, material_id)

    # here we reply directly with the files.
    if user_mode(url) and isinstance(material, Review):
        return await sendall.send.__wrapped__(
            update, context, session, material_type=material.type
        )
    if user_mode(url) and isinstance(material, SingleFile):
        return await files.display.__wrapped__(
            update, context, session, file_id=material.file_id
        )

    keyboard: list[list] = []
    # First, list the files if material have them
    if isinstance(material, RefFilesMixin):
        menu_files = session.scalars(
            select(File).where(File.material_id == material.id)
            # hack to have the order as document, photo, video, voice then by file name
            .order_by(File.type.asc(), File.name)
        ).all()
        files_menu = context.buttons.files_list(f"{url}/{constants.FILES}", menu_files)
        keyboard += build_menu(files_menu, 1)
        if not user_mode(url):
            keyboard += [[context.buttons.add_file(url=f"{url}/{constants.FILES}")]]
    # handle control buttons for number
    if not user_mode(url) and isinstance(material, HasNumber):
        keyboard[-1].append(
            context.buttons.edit(url, _("Number"), end=f"/{constants.NUMBER}")
        )
    # handle control buttons for date
    if not user_mode(url) and isinstance(material, Review):
        keyboard[-1].append(
            context.buttons.edit(url, _("Date"), end=f"/{constants.DATE}")
        )
    # handle single file materials
    if not user_mode(url) and isinstance(material, SingleFile):
        menu = [
            context.buttons.display(f"{url}/{constants.FILES}/{material.file_id}"),
            context.buttons.edit(
                f"{url}/{constants.FILES}/{material.file_id}/{constants.SOURCE}",
                _("Source"),
            ),
        ]
        keyboard += build_menu(menu, 2, reverse=context.language_code == constants.AR)

    # common buttons accross material types
    if not user_mode(url):
        keyboard += build_menu(
            [
                context.buttons.publish(callback_data=url),
                context.buttons.delete(url, _(material_type)),
            ],
            2,
            reverse=context.language_code == constants.AR,
        )

    if isinstance(material, Assignment) and not user_mode(url):
        keyboard += [
            [context.buttons.edit(url, _("Deadline"), end=f"/{constants.DEADLINE}")]
        ]

    # Send all button when on user mode:
    if (
        user_mode(url)
        and isinstance(material, RefFilesMixin)
        and len(material.files) > 1
    ):
        keyboard += [[context.buttons.send_all(url)]]

    # when on lectures and on user mode, hop two steps back
    back_pattern = (
        rf"/{material.type}.*"
        if isinstance(material, Lecture) and user_mode(url)
        else r"/\d+$"
    )
    keyboard += [[context.buttons.back(url, pattern=back_pattern)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    is_publish_menu = not user_mode(url)
    spaces = " " if not is_publish_menu and isinstance(material, Lecture) else "   "
    message = (
        messages.title(context.match, session, context=context)
        + "\n"
        + _("t-symbol")
        + "─ "
        + material.course.get_name(context.language_code)
        + "\n"
        + messages.material_type_text(context.match, context=context)
        + ("\n" if isinstance(material, SingleFile) else "")
        + "│"
        + spaces
        + _("corner-symbol")
        + "── "
        + messages.material_message_text(url, context, material)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# ------------------------- ConversationHander -----------------------------


ALLTYPES = "|".join([t.value for t in MaterialType])


def conversation(url_prefix: str):
    entry_points = [
        CallbackQueryHandler(
            material_list,
            pattern=f"{url_prefix}/(?P<material_type>{ALLTYPES})$",
        ),
        # Special entry point for Lectures.
        CallbackQueryHandler(
            material,
            pattern=f"{url_prefix}"
            f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)$",
        ),
    ]

    states = {
        constants.ONE: [
            CallbackQueryHandler(
                material,
                pattern=f"{url_prefix}"
                f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)$",
            ),
            CallbackQueryHandler(
                files.file,
                pattern=f"{url_prefix}"
                f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                f"/{constants.FILES}/(?P<file_id>\d+)$",
            ),
            CallbackQueryHandler(
                sendall.send,
                pattern=f"{url_prefix}"
                f"/(?P<material_type>{ALLTYPES})(?:/(?P<material_id>\d+))?"
                f"/{constants.ALL}$",
            ),
        ]
    }

    if not user_mode(url_prefix):
        states[constants.ONE].extend(
            [
                CallbackQueryHandler(
                    partial(add.handler, back=material_list),
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})"
                    f"/{constants.ADD}$",
                ),
                CallbackQueryHandler(
                    partial(add.handler, back=material),
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})"
                    f"/{constants.ADD}(?:\?t=(?P<type_key>\w+))?$",
                ),
                CallbackQueryHandler(
                    delete.handler,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                    f"/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
                ),
                CallbackQueryHandler(
                    partial(publish.handler, back=material),
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                    f"/{constants.PUBLISH}(?:\?n=(?P<notify>1|0))?$",
                ),
                CallbackQueryHandler(
                    number.edit,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{number.TYPES})/(?P<material_id>\d+)"
                    f"/{constants.EDIT}/{constants.NUMBER}$",
                ),
                CallbackQueryHandler(
                    date.edit,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{date.TYPES})/(?P<material_id>\d+)"
                    f"/{constants.EDIT}/{constants.DATE}$",
                ),
                CallbackQueryHandler(
                    deadline.edit,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{deadline.TYPES})/(?P<material_id>\d+)"
                    f"/{constants.EDIT}/{constants.DEADLINE}(?:\?y=(?P<y>\d+)"
                    f"(?:&m=(?P<m>\d+))?(?:&d=(?P<d>\d+))?)?(?:/{constants.IGNORE})?$",
                ),
                CallbackQueryHandler(
                    files.add,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                    f"/{constants.FILES}/{constants.ADD}$",
                ),
                CallbackQueryHandler(
                    files.display,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                    f"/{constants.FILES}/(?P<file_id>\d+)/{constants.DISPLAY}$",
                ),
                CallbackQueryHandler(
                    files.source_edit,
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                    f"/{constants.FILES}/(?P<file_id>\d+)"
                    f"/{constants.SOURCE}/{constants.EDIT}$",
                ),
                CallbackQueryHandler(
                    partial(files.delete, back=material),
                    pattern=f"{url_prefix}"
                    f"/(?P<material_type>{ALLTYPES})/(?P<material_id>\d+)"
                    f"/{constants.FILES}/(?P<file_id>\d+)/{constants.DELETE}$",
                ),
            ]
        )

    if not user_mode(url_prefix):
        states.update(
            {
                f"{constants.EDIT} {constants.NUMBER}": [
                    *states[constants.ONE],
                    MessageHandler(filters.Regex(r"^(\d+)$"), number.receive),
                ],
                f"{constants.EDIT} {constants.SOURCE}": [
                    *states[constants.ONE],
                    MessageHandler(
                        filters.Entity("url")
                        | (filters.Command(only_start=True) & (filters.Text("/empty"))),
                        files.receive_source,
                    ),
                ],
                f"{constants.EDIT} {constants.DEADLINE}": [
                    *states[constants.ONE],
                    CallbackQueryHandler(
                        deadline.edit,
                        pattern=f"{url_prefix}"
                        f"/(?P<material_type>{deadline.TYPES})/(?P<material_id>\d+)"
                        f"/{constants.EDIT}/{constants.DEADLINE}(?:\?y=(?P<y>\d+)"
                        f"(?:&m=(?P<m>\d+))?(?:&d=(?P<d>\d+))?)?(?:/{constants.IGNORE})?$",
                    ),
                    MessageHandler(
                        filters.Regex(r"^((?:\d)?\d)\:((?:\d)?\d)$")
                        | (filters.Command(only_start=True) & (filters.Text("/empty"))),
                        deadline.receive_time,
                    ),
                ],
                f"{constants.EDIT} {constants.DATE}": [
                    *states[constants.ONE],
                    MessageHandler(
                        filters.Regex(
                            r"^(?P<y>(?:20)?\d{2})-(?P<m>\d{1,2})(?:-(?P<d>\d{1,2}))?$"
                        )
                        | (filters.Command(only_start=True) & (filters.Text("/empty"))),
                        date.receive,
                    ),
                ],
                constants.ADD: [
                    *states[constants.ONE],
                    MessageHandler(
                        filters.Document.ALL
                        | filters.VIDEO
                        | filters.PHOTO
                        | filters.VOICE,
                        files.receive_file,
                    ),
                ],
                f"{constants.ADD} {constants.MATERIALS}": [
                    *states[constants.ONE],
                    MessageHandler(
                        filters.Document.ALL | filters.VIDEO | filters.PHOTO,
                        partial(add.receive_material_file, url_prefix=url_prefix),
                    ),
                ],
            }
        )

    return ConversationHandler(
        entry_points=entry_points,
        states=states,
        fallbacks=[],
        persistent=True,
        name=constants.MATERIALS_,
        # allow_reentry must be set to true for the conversation
        # to work after pressing Back button
        allow_reentry=True,
    )
