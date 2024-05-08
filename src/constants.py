import gettext as pygettext
from gettext import translation
from pathlib import Path
from typing import Callable, Optional

from telegram import BotCommand

ar_ = translation("base", localedir=Path("src", "locales"), languages=["ar"])
ar_.install()

en_ = translation("base", localedir=Path("src", "locales"), languages=["en"])
en_.install()

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


class _Levels:
    levels = (
        pygettext.gettext("First Year"),
        pygettext.gettext("Second Year"),
        pygettext.gettext("Third Year"),
        pygettext.gettext("Fourth Year"),
        pygettext.gettext("Fifth Year"),
    )

    def __getitem__(self, index):
        return _Levels.levels[index]


LEVELS = _Levels()


class Commands:
    def __init__(self, gettext: Optional[Callable[[str], str]] = None) -> None:
        self._ = gettext or pygettext.gettext

    def user_commands(self):
        return (self.enrollments1,)

    def root_commands(self):
        return (
            self.pending,
            self.coursemanagement,
            self.contentmanagement,
            self.departments,
            self.programs,
            self.semesters,
            self.years,
        )

    def student_commands(self):
        return (
            self.courses,
            self.settings,
            self.enrollments2,
            self.editor1,
        )

    def editor_commands(self):
        return (
            self.courses,
            self.updatematerials,
            self.settings,
            self.enrollments2,
            self.editor2,
        )

    @property
    def pending(self):
        return BotCommand("pending", self._("/pending description"))

    @property
    def coursemanagement(self):
        return BotCommand("coursemanagement", self._("/coursemanagement description"))

    @property
    def contentmanagement(self):
        return BotCommand("contentmanagement", self._("/contentmanagement description"))

    @property
    def departments(self):
        return BotCommand("departments", self._("/departments description"))

    @property
    def programs(self):
        return BotCommand("programs", self._("/programs description"))

    @property
    def semesters(self):
        return BotCommand("semesters", self._("/semesters description"))

    @property
    def years(self):
        return BotCommand("years", self._("/academicyears description"))

    @property
    def enrollments1(self):
        return BotCommand("enrollments", self._("/enrollments1 description"))

    @property
    def courses(self):
        return BotCommand("courses", self._("/courses description"))

    @property
    def settings(self):
        return BotCommand("settings", self._("/settings description"))

    @property
    def enrollments2(self):
        return BotCommand("enrollments", self._("/enrollments2 description"))

    @property
    def editor1(self):
        return BotCommand("publish", self._("/editor1 description"))

    @property
    def updatematerials(self):
        return BotCommand("updatematerials", self._("/updatematerials description"))

    @property
    def editor2(self):
        return BotCommand("publish", self._("/editor2 description"))


COMMANDS = Commands()
