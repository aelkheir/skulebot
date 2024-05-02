# Callback data
PROGRAMS = "pr"
SEMESTERS = "sm"
ACADEMICYEARS = "ys"
DEPARTMENTS = "dp"
COURSES = "cr"
OPTIONAL = "op"
CREDITS = "ct"
NAME = "name"
DEADLINE = "dl"
NUMBER = "numb"
DATE = "date"
ACADEMICYEAR = "yr"
TYPE = "type"
ENROLLMENTS = "el"
ACCESSREQUSTS = "ar"
MATERIALS = "ma"
ALL = "all"
FILES = "fl"
SOURCE = "so"
ID = "id"
NOTIFICATIONS = "ntf"
LANGUAGE = "lan"
ACTIVATE = "act"
ADD = "add"
EDIT = "edit"
DELETE = "delete"
REVOKE = "revoke"
CONFIRM = "confirm"
PUBLISH = "publish"
DISPLAY = "display"
IGNORE = "ignore"
AR = "ar"
EN = "en"

# Conversation States
ONE, TWO, THREE, FOURE, FIVE = range(5)

# Conversation Names
ENROLLMENT_ = "enr"
EDITOR_ = "edp"
SEMESTER_ = "smr"
REQUEST_MANAGEMENT_ = "rqm"
ACADEMICYEAR_ = "ayr"
DEPARTMENT_ = "dep"
PROGRAM_ = "prg"
CONETENT_MANAGEMENT_ = "ctm"
COURSE_MANAGEMENT_ = "crm"
COURSES_ = "cos"
UPDATE_MATERIALS_ = "uma"
MATERIALS_ = "mat"
SETTINGS_ = "stg"
NOTIFICATION_ = "ntf"

LEVELS = {
    1: {"en_name": "First Year", "ar_name": "المستوى الأولى"},
    2: {"en_name": "Second Year", "ar_name": "المستوى الثاني"},
    3: {"en_name": "Third Year", "ar_name": "المستوى الثالث"},
    4: {"en_name": "Fourth Year", "ar_name": "المستوى الرابع"},
    5: {"en_name": "Fifth Year", "ar_name": "المستوى الخامس"},
}


def get_level_name(level: dict, language_code: str):
    return level["ar_name"] if language_code == AR else level["en_name"]
