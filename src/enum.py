import enum


# Python 3.11 and above has a different output for mixin classes for IntEnum, StrEnum
# and IntFlag see https://docs.python.org/3.11/library/enum.html#notes. We want e.g.
# str(StrEnumTest.FOO) to  return "foo" instead of "StrEnumTest.FOO", which is not
# the case < py3.11
class StringEnum(str, enum.Enum):
    """Helper class for string enums where ``str(member)`` prints the value, but
    ``repr(member)``
    gives ``EnumName.MEMBER_NAME``.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name}>"

    def __str__(self) -> str:
        return str.__str__(self)
