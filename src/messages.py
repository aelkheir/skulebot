import re
from typing import Optional, Sequence

from sqlalchemy.orm import Session
from telegram.constants import InputMediaType

from src import constants
from src.constants import LEVELS
from src.models import Enrollment
from src.models.academic_year import AcademicYear
from src.models.course import Course
from src.models.file import File
from src.models.material import (
    Assignment,
    HasNumber,
    Material,
    MaterialType,
    Review,
    SingleFile,
)
from src.models.program import Program
from src.models.semester import Semester
from src.utils import user_mode


def first_list_level(text: str):
    return f"├── {text}\n"


def second_list_level(text: str):
    return f"│ └── {text}\n"


def third_list_level(text: str):
    return f"│   └── {text}\n"


def delete_confirm(text: str):
    return f"You are about to delete <b>{text}</b>. Is that correct?"


def revoke_confirm(text: str):
    return (
        f"You are about to revoke your editor access of <b>{text}</b>."
        " If the academic year had passed, you will not be able to request it again."
        " Is that Okay?"
    )


def delete_reconfirm(text: str):
    return f"Are you <b>TOTALLY</b> sure you want to delete {text}?"


def revoke_reconfirm(text: str):
    return (
        f"Are you <b>TOTALLY</b> sure you want to revoke your editor access of {text}?"
    )


def success_deleted(text: str):
    return f"Success! {text} deleted"


def success_revoked(text: str):
    return f"Success! Editor Access of {text} revoked"


def success_added(text: str):
    return f"Success! {text} added."


def success_created(text: str):
    return f"Success! {text} created."


def success_updated(text: str):
    return f"Success! {text} updated."


def success_unlinked(text: str):
    return f"Success! {text} unlinked"


def success_linked(text: str):
    return f"Success! {text} linked"


def type_number():
    return "Type a number"


def type_date():
    return "Type date in the form yyyy-mm-dd"


def type_name():
    # this always accepts dual lang names
    return "Type name"


def type_year():
    # this always accepts dual lang names
    return "Type year range"


def type_name_in_lang(lang: str):
    return f"Type name in {lang}"


def send_link():
    return "Send me the link"


def send_files(media_types: Sequence[InputMediaType]):
    types = ", ".join(list(media_types))
    return f"Send me the files ({types})"


def multilang_names(ar: str, en: str):
    return f"Arabic Name: {ar}\nEnglish Name: {en}\n"


def bot_settings():
    return "├ ⚙️ <b>Bot Settings</b>\n"


def title(match: re.Match, session: Session):
    url: str = match.group()
    text = ""
    if url.startswith(constants.UPDATE_MATERIALS_):
        text += "<u>Editor Menu</u>"
    elif url.startswith(constants.EDITOR_):
        text += "<u>Editor Access</u>"
    elif url.startswith(constants.CONETENT_MANAGEMENT_):
        text += "<u>Content Management</u>"

    if match.group("enrollment_id"):
        if not url.startswith(constants.COURSES_):
            text += "\n\n" + enrollment_text(match, session)
    elif match.group("year_id"):
        program_id = match.group("program_id")
        program = session.get(Program, program_id)
        semester_id = match.group("semester_id")
        semester = session.get(Semester, semester_id)
        year_id = match.group("year_id")
        year = session.get(AcademicYear, year_id)
        text += (
            "\n\n"
            + program.get_name()
            + "\n"
            + f"Semester {semester.number}"
            + "\n"
            + f"{year.start} - {year.end}"
            + "\n"
        )
    return text


def course_text(match: re.Match, session: Session):
    course_id = int(match.group("course_id"))
    course = session.get(Course, course_id)
    return first_list_level(course.get_name())


def material_type_text(match: re.Match):
    material_type: str = match.group("material_type")
    message = ""
    if user_mode(match.group()) or material_type in [
        MaterialType.REFERENCE,
        MaterialType.SHEET,
        MaterialType.TOOL,
    ]:
        if material_type == MaterialType.REVIEW:
            return second_list_level(material_type.capitalize())
        return second_list_level(material_type.capitalize() + "s")
    return message


def material_message_text(
    match: Optional[re.Match] = None, session: Session = None, material: Material = None
):
    url = match.group()
    if match and material is None:
        material_id: str = match.group("material_id")
        material = session.get(Material, material_id)
    if isinstance(material, Assignment):
        datestr = d.strftime("%A %d %B %Y %H:%M") if (d := material.deadline) else "N/A"
        text = f"Assignment {material.number} due by {datestr}" + (
            f" (Published: {material.published})" if not user_mode(url) else ""
        )
        message = text
    elif isinstance(material, HasNumber):
        text = f"{material.type.capitalize()} {material.number}" + (
            f" (Published: {material.published})" if not user_mode(url) else ""
        )
        message = text
    elif isinstance(material, SingleFile):
        file = session.get(File, material.file_id)
        message = file_text(match, file).replace("\n", "") + (
            f" (Published: {material.published})\n" if not user_mode(url) else "\n"
        )
    elif isinstance(material, Review):
        text = (
            material.get_name()
            + (" " + str(d.year) if (d := material.date) else "")
            + (f" (Published: {material.published})" if not user_mode(url) else "")
        )
        message = text
    if user_mode(url) or isinstance(material, SingleFile):
        message = third_list_level(message)
    else:
        message = second_list_level(message)
    return message


def material_title_text(match: re.Match, material: Material):
    m_type: str = match.group("material_type")
    if isinstance(material, HasNumber):
        return m_type.capitalize() + " " + str(material.number)
    if isinstance(material, SingleFile):
        return m_type.capitalize() + " " + str(material.file.name)
    if isinstance(material, Review):
        return m_type.capitalize() + " " + str(material.get_name())
    return None


def file_text(match: re.Match, file: File):
    return (
        file.name
        + " "
        + (f'[<a href="{s}">Source</a>]' if (s := file.source) else "[No Source]")
    )


def enrollment_text(
    match: Optional[re.Match] = None,
    session: Session = None,
    enrollment: Enrollment = None,
):
    if match and enrollment is None:
        enrollment_id = int(id) if (id := match.group("enrollment_id")) else None
        enrollment = session.get(Enrollment, enrollment_id)

    program = enrollment.program
    semester = enrollment.semester
    year = enrollment.academic_year

    level = semester.number // 2 + (semester.number % 2)
    level_name = LEVELS[level]["en_name"]

    return (
        ""
        f"{year.start} - {year.end} Enrollment\n"
        f"{program.en_name}\n"
        f"{level_name}"
        "\n"
    )
