import re
from typing import Optional, Sequence, Set, Union

from sqlalchemy.orm import Session
from telegram import Chat, User
from telegram.constants import InputMediaType

from src import constants
from src.constants import LEVELS
from src.models import (
    AcademicYear,
    Assignment,
    Course,
    Enrollment,
    File,
    HasNumber,
    Material,
    MaterialType,
    Program,
    Review,
    RoleName,
    Semester,
    SingleFile,
)
from src.models.access_request import AccessRequest
from src.models.department import Department
from src.utils import user_mode


def your_enrollments():
    return "Your enrollments"


def courses():
    return "courses"


def departments():
    return "Departments"


def success():
    return "Success!"


def course_management():
    return "Course Management"


def programs():
    return "Programs"


def carriculam():
    return "Carriculam"


def already_linked():
    return "Course is already linked in Semester"


def academic_years():
    return "Academic years"


def year():
    return "year"


def none_department():
    return "N/A department"


def no_editor():
    return (
        "\n\n[there is no one with upload access for this program,"
        " you can become one here /editor.]"
    )


def editor_menu():
    return "<u>Editor Menu</u>\n\n"


def select_optionals():
    return "These courses are optional. Select one or more to add to your /courses menu"


def semesters():
    return "Semesters"


def semester():
    return "Semester"


def editor_accesses():
    return "Editor Accesses"


def content_management():
    return "Content Management"


def new_editor_introduction(enrollment_text: str):
    return f"Hi! I'd like to have access and upload materials in\n\n{enrollment_text}"


def send_editor_proof():
    return "Alright. send me your id (photo)"


def is_pending():
    return "\nYou're request is pending. We'll get back to you soon. Thanks"


def new_editor_instructions():
    return (
        "\nThanks for helping update course materials!\n\n"
        "In order to give you access over content we need to verify that you're"
        " actually enrolled in this program, or at least that you are a student at our"
        " faculty.\n\n"
        "To do that there are two options. You could either send us <i>any</i> document"
        " that proves this. Or if you don't have any, please reach out to support.\n\n"
        "Your contribution is truly appreciated!"
    )


def number():
    return "Number"


def credits():
    return "Credits"


def empty_current(text: str):
    return f"Type /empty to remove current {text}"


def select(text: str):
    return f"Select {text}"


def already_enrolled(text: str):
    return "Oops, seems like you are already enrolled."


def pending_requests():
    return "Pending Access Requests"


def new_request(request: AccessRequest, chat: Union[Chat, User]):
    mention = chat.mention_html(chat.full_name or "User")
    return (
        f"Editor Access re-Request: {mention}\n\n"
        f"{chat.full_name} is requesting editor access for\n"
        f"{enrollment_text(enrollment=request.enrollment)}"
    )


def request_received():
    return (
        "Thanks for taking the time."
        " We have recieved your request and will get back to you soon.\n\n"
        "Meanwhile your can check your request status in /editor."
    )


def successfull_request_action(request: AccessRequest, chat: Chat):
    mention = chat.mention_html(chat.full_name or "User")
    return (
        f"Success! {request.status.capitalize()} "
        f"Editor Access to {mention} for\n\n"
        f"{enrollment_text(enrollment=request.enrollment)}"
    )


def access_granted():
    return (
        "Congratulations 🎉! Now you have access to update materials. "
        "We appreciate your contributions."
    )


def updated_commands():
    return "Here is your updated list of commands\n"


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


def help(user_roles: Set[RoleName], new: Optional[RoleName] = None):
    message: str
    if user_roles == {RoleName.USER}:
        message = "<b>Commands</b>\n\n/enrollments - enroll yourself to a program."
    elif user_roles == {RoleName.USER, RoleName.ROOT}:
        message = (
            "<b>Commands</b>\n\n"
            "• /requestmanagement - grant or reject pending requests from users\n"
            "• /coursemanagement - update course info.\n"
            "• /contentmanagement - moderate materials that users are uploading.\n"
            "• /departments - update department info.\n"
            "• /programs - update programs info, manage carriculams.\n"
            "• /semesters - update semester info\n"
            "• /academicyears - update academic years\n"
        )
    elif user_roles == {RoleName.USER, RoleName.STUDENT}:
        message = (
            "• <b>Commands</b>\n\n"
            f"•{' [<i><u>new</u></i>] ' if new==RoleName.STUDENT else ' '}"
            "/courses - list current courses.\n"
            f"•{' [<i><u>new</u></i>] ' if new==RoleName.STUDENT else ' '}"
            f"/settings - customize bot settings.\n"
            "• /enrollments - update your enrollments.\n"
            f"•{' [<i><u>new</u></i>] ' if new==RoleName.STUDENT else ' '}"
            f"/editor - apply for access to upload content."
        )
    elif user_roles == {RoleName.USER, RoleName.STUDENT, RoleName.EDITOR}:
        message = (
            "<b>Commands</b>\n\n"
            "• /courses - list current courses.\n"
            f"•{' [<i><u>new</u></i>] ' if new==RoleName.EDITOR else ' '}"
            "/updatematerials - update current courses.\n"
            "• /settings - tweak bot settings.\n"
            "• /enrollments - update your enrollments.\n"
            "• /editor - control, revoke your access rights."
        )

    return message


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
            + program.get_name(constants.EN)
            + "\n"
            + f"Semester {semester.number}"
            + "\n"
            + f"{year.start} - {year.end}"
            + "\n"
        )
    return text


def course_name(course: Course):
    return course.en_name if True else course.ar_name


def localized_name(model: Union[Course, Department, Program]):
    for local_name in ["ar_name", "en_name"]:
        if not hasattr(model, local_name):
            raise ValueError(
                f"cannot get localized name for object {model}. "
                f"object is missing attribute {local_name}"
            )

    return model.en_name if True else model.ar_name


def course_text(match: re.Match, session: Session):
    course_id = int(match.group("course_id"))
    course = session.get(Course, course_id)
    return first_list_level(course.get_name(constants.EN))


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
            material.get_name(constants.EN)
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
        return (
            m_type.capitalize()
            + " "
            + str(material.get_name(constants.EN))
            + (" " + str(d.year) if (d := material.date) else "")
        )
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
