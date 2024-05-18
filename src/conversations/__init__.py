# ruff: noqa: E402

from warnings import filterwarnings

from telegram.warnings import PTBUserWarning

filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)

from .academicyear import academicyear_
from .contentmanagement import contentmanagement_
from .course import usercourses_
from .coursemanagement import coursemanagement_
from .department import department_
from .editor import editor_
from .enrollment import enrolments_
from .notification import notifications_
from .program import program_
from .requestmanagement import requestmanagement_
from .semester import semester_
from .setting import settings_
from .updatematerial import updatematerials_

handlers = [
    usercourses_,
    enrolments_,
    settings_,
    notifications_,
    updatematerials_,
    editor_,
    academicyear_,
    program_,
    department_,
    semester_,
    coursemanagement_,
    requestmanagement_,
    contentmanagement_,
]
