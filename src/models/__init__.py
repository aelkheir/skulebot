__all__ = (
    "AcademicYear",
    "AccessRequest",
    "Assignment",
    "Base",
    "ChatData",
    "Conversation",
    "Course",
    "Department",
    "Enrollment",
    "File",
    "HasNumber",
    "Lab",
    "Lecture",
    "Material",
    "MaterialType",
    "Program",
    "ProgramSemester",
    "ProgramSemesterCourse",
    "Reference",
    "Review",
    "Role",
    "RoleName",
    "Semester",
    "Setting",
    "SettingKey",
    "Sheet",
    "SingleFile",
    "Status",
    "Tool",
    "Tutorial",
    "User",
    "UserData",
    "UserOptionalCourse",
    "user_role",
)

from .academic_year import AcademicYear
from .access_request import AccessRequest, Status
from .base import Base
from .course import Course
from .department import Department
from .enrollment import Enrollment
from .file import File
from .material import (
    Assignment,
    HasNumber,
    Lab,
    Lecture,
    Material,
    MaterialType,
    Reference,
    Review,
    Sheet,
    SingleFile,
    Tool,
    Tutorial,
)
from .persistence import ChatData, Conversation, UserData
from .program import Program
from .program_semester import ProgramSemester
from .program_semester_course import ProgramSemesterCourse
from .role import Role, RoleName
from .semester import Semester
from .setting import Setting, SettingKey
from .user import User
from .user_optional_course import UserOptionalCourse
from .user_role import user_role
