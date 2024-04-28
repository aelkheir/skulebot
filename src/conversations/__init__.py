from .academicyear import academicyear_
from .contentmanagement import contentmanagement_
from .course import usercourses_
from .coursemanagement import coursemanagement_
from .department import department_
from .editor import editor_
from .enrollment import enrolments_
from .program import program_
from .requestmanagement import requestmanagement_
from .semester import semester_
from .setting import settings_
from .updatematerial import updatematerials_

handlers = [
    academicyear_,
    program_,
    department_,
    semester_,
    enrolments_,
    settings_,
    coursemanagement_,
    requestmanagement_,
    usercourses_,
    updatematerials_,
    editor_,
    contentmanagement_,
]
