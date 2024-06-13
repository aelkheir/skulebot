import gettext as pygettext
import re
from typing import Optional
from zoneinfo import ZoneInfo

from babel.dates import format_datetime
from sqlalchemy.orm import Session
from telegram import Chat

from src import constants, queries
from src.constants import LEVELS
from src.customcontext import CustomContext
from src.models import (
    AccessRequest,
    Assignment,
    Enrollment,
    File,
    HasNumber,
    Material,
    MaterialType,
    Review,
    RoleName,
    SingleFile,
)
from src.utils import user_locale, user_mode


def successfull_request_action(
    request: AccessRequest, chat: Chat, context: CustomContext
):
    mention = chat.mention_html(chat.full_name or "User")
    return (
        f"Success! {request.status.capitalize()} "
        f"Editor Access to {mention} for\n\n"
        f"{enrollment_text(enrollment=request.enrollment, context=context)}"
    )


def bold(text):
    return f"<b>{text}</b>"


def italic(text):
    return f"<i>{text}</i>"


def underline(text):
    return f"<u>{text}</u>"


def help(
    user_roles: set[RoleName],
    language_code: str,
    new: Optional[RoleName] = None,
):
    message: str
    _ = user_locale(language_code).gettext
    cmds = constants.Commands(_)

    message = bold(_("Commands")) + "\n\n"

    if user_roles == {RoleName.USER}:
        cells = sorted(
            [f"/{cmds.enrollments1.command}", cmds.enrollments1.description],
            reverse=language_code == constants.AR,
        )
        message += f"• {' - '.join(cells)}\n"

    elif user_roles == {RoleName.USER, RoleName.ROOT}:
        for cmd in cmds.root_commands():
            cells = sorted(
                [f"/{cmd.command}", cmd.description],
                reverse=language_code == constants.AR,
            )
            message += f"• {' - '.join(cells)}\n"

    elif user_roles == {RoleName.USER, RoleName.STUDENT}:
        for cmd in cmds.student_commands():
            cells = sorted(
                [f"/{cmd.command}", cmd.description],
                reverse=language_code == constants.AR,
            )
            pre = (
                "[" + italic(underline(_("new"))) + "]"
                if new == RoleName.STUDENT
                and cmd in [cmds.courses, cmds.settings, cmds.editor1]
                else ""
            )
            message += f"• {pre} {' - '.join(cells)}\n"

    elif user_roles == {RoleName.USER, RoleName.STUDENT, RoleName.EDITOR}:
        for cmd in cmds.editor_commands():
            cells = sorted(
                [f"/{cmd.command}", cmd.description],
                reverse=language_code == constants.AR,
            )
            pre = (
                "[" + italic(underline(_("new"))) + "]"
                if new == RoleName.EDITOR and cmd in [cmds.updatematerials]
                else ""
            )
            message += f"• {pre} {' - '.join(cells)}\n"

    return message


def title(match: re.Match, session: Session, context: CustomContext):
    _ = context.gettext
    url: str = match.group()

    if url.startswith(constants.COURSES_):
        return ""

    text = ""

    if url.startswith(constants.UPDATE_MATERIALS_):
        text += underline(_("Editor Menu"))
    elif url.startswith(constants.EDITOR_):
        text += underline(_("Editor Access"))
    elif url.startswith(constants.CONETENT_MANAGEMENT_):
        text += underline(_("Content Management"))

    if match.group("enrollment_id"):
        text += "\n\n" + enrollment_text(match, session, context=context)
    elif match.group("year_id"):
        year_id = match.group("year_id")
        program_id = match.group("program_id")
        semester_id = match.group("semester_id")
        program = queries.program(session, program_id)
        semester = queries.semester(session, semester_id)
        year = queries.academic_year(session, year_id)
        text += (
            "\n\n"
            + program.get_name(context.language_code)
            + "\n"
            + _("Semester {}").format(semester.number)
            + "\n"
            + _("Year {} - {}").format(year.start, year.end)
            + "\n"
        )
    return text


def material_type_text(match: re.Match, context: CustomContext):
    material_type: str = match.group("material_type")
    if user_mode(match.group()) and material_type == MaterialType.LECTURE:
        return ""
    _ = context.gettext
    type_name = f"{material_type}s"
    return "│ " + _("corner-symbol") + "── " + _(type_name) + "\n"


def material_message_text(
    url: str,
    context: CustomContext,
    material: Material,
):
    language_code = context.language_code
    _ = context.gettext

    is_published = ""
    if not user_mode(url):
        is_published = (
            italic(_("Published true"))
            if material.published
            else italic(_("Published false"))
        )

    material_type = _(material.type)
    if isinstance(material, Assignment):
        datestr = (
            (
                "<b>"
                + format_datetime(
                    d.astimezone(ZoneInfo("Africa/Khartoum")),
                    "E d MMM hh:mm a ZZZZ",
                    locale=context.language_code,
                )
                + "</b>"
            )
            if (d := material.deadline)
            else "[" + _("No value") + "]"
        )
        text = f"{material_type} {material.number} " + _("due by") + f" {datestr}"
        message = text
    elif isinstance(material, HasNumber):
        text = f"{material_type} {material.number}"
        message = text
    elif isinstance(material, SingleFile):
        file = material.file
        return file_text(file, context) + " " + is_published
    elif isinstance(material, Review):
        text = material.get_name(language_code) + (
            " " + str(d.year) if (d := material.date) else ""
        )
        message = text

    message += " " + is_published
    return message


def material_title_text(
    match: Optional[re.Match] = None,
    material: Material = None,
    language_code: Optional[str] = None,
):
    _ = user_locale(language_code).gettext
    if not material:
        m_type: str = _(match.group("material_type"))
    else:
        m_type = material.type
    m_type = _(m_type)

    if isinstance(material, HasNumber):
        return m_type + " " + str(material.number)
    if isinstance(material, SingleFile):
        return m_type + " " + str(material.file.name)
    if isinstance(material, Review):
        return +str(material.get_name(language_code)) + (
            " " + str(d.year) if (d := material.date) else ""
        )
    return None


def file_text(file: File, context: CustomContext):
    _ = context.gettext
    return (
        file.name
        + " "
        + _("Source")
        + " "
        + (f'[<a href="{s}">url</a>]' if (s := file.source) else _("No value"))
    )


def enrollment_text(
    match: Optional[re.Match] = None,
    session: Session = None,
    enrollment: Enrollment = None,
    context: CustomContext = None,
):
    _ = context.gettext if context else pygettext.gettext

    if match and enrollment is None:
        enrollment_id = int(id) if (id := match.group("enrollment_id")) else None
        enrollment = session.get(Enrollment, enrollment_id)

    program = enrollment.program
    semester = enrollment.semester
    year = enrollment.academic_year

    level = (semester.number // 2 + (semester.number % 2)) - 1
    level_name = _(LEVELS[level])

    program_name = (
        program.en_name
        if context.user_data["language_code"] == constants.EN
        else program.ar_name
    )

    return (
        _("Year {} - {}").format(year.start, year.end)
        + f"\n{program_name}\n{level_name}\n"
    )
