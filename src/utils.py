from functools import wraps
from typing import Generic, List, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session as SessionType
from telegram import Bot, BotCommand, BotCommandScopeChat, InlineKeyboardButton, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src import constants
from src.database import Session
from src.models import Role, RoleName, SettingKey, User, user_role
from src.models.setting import Setting


def send_action(action):
    def decorator(func):
        @wraps(func)
        async def wrapped(
            update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
        ):
            await context.bot.send_chat_action(
                chat_id=update.effective_message.chat_id, action=action
            )
            return await func(update, context, *args, **kwargs)

        return wrapped

    return decorator


send_typing_action = send_action(ChatAction.TYPING)


def session(callback):
    @wraps(callback)
    async def wrapped(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        with Session.begin() as session:
            return await callback(update, context, *args, **kwargs, session=session)

    return wrapped


def roles(roles: RoleName):
    _roles = None
    if isinstance(roles, RoleName):
        _roles = (roles,)
    if isinstance(roles, (list, tuple)):
        _roles = (r for r in roles)
    if not _roles:
        raise ValueError("roles must either be a string or iterable")

    def decoroator(callback):
        @wraps(callback)
        async def wrapped(
            update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
        ):
            with Session.begin() as session:
                roles = get_user_roles(context.user_data["id"], session)
                if any(user_role in _roles for user_role in roles):
                    return await callback(update, context, *args, **kwargs)
                return None

        return wrapped

    return decoroator


def user_mode(url: str):
    return url.startswith((constants.COURSES_, constants.ENROLLMENT_))


def get_user_roles(user_id: int, session: SessionType):
    return session.scalars(
        select(Role.name).join(user_role).join(User).where(User.id == user_id)
    ).all()


def get_setting_value(session: SessionType, user_id: int, setting_key: SettingKey):
    value = session.scalar(
        select(Setting.value).where(
            Setting.user_id == user_id, Setting.key == setting_key.key
        )
    )
    return value if value is not None else setting_key.default


def set_setting_value(
    session: SessionType, user_id: int, setting_key: SettingKey, value
):
    setting = session.scalar(
        select(Setting).where(
            Setting.user_id == user_id, Setting.key == setting_key.key
        )
    )
    if setting:
        setting.value = value
    else:
        user = session.get(User, user_id)
        setting = Setting(
            user_id=user.id,
            key=setting_key.key,
            value=value,
        )
        user.settings.append(setting)
    return setting


def build_menu(
    buttons: List[InlineKeyboardButton],
    n_cols: int,
    header_buttons: InlineKeyboardButton | list[InlineKeyboardButton] = None,
    footer_buttons: InlineKeyboardButton | list[InlineKeyboardButton] = None,
) -> list[list[InlineKeyboardButton]]:
    menu = [buttons[i : i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(
            0, header_buttons if isinstance(header_buttons, list) else [header_buttons]
        )
    if footer_buttons:
        menu.append(
            footer_buttons if isinstance(footer_buttons, list) else [footer_buttons]
        )
    return menu


def build_media_group(
    media: List,
) -> list[list]:
    return [media[i : i + 10] for i in range(0, len(media), 10)]


async def set_user_commands(bot: Bot, user: User):
    commands = [
        BotCommand("enrollments", "start by enrolling to your program"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(user.chat_id))


async def set_student_commands(bot: Bot, user: User):
    commands = [
        BotCommand("courses", "courses you're currently studying"),
        BotCommand("settings", "bot settings"),
        BotCommand("enrollments", "manage your enrollments"),
        BotCommand("editor", "gain access to upload materials"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(user.chat_id))


async def set_editor_commands(bot: Bot, user: User):
    commands = [
        BotCommand("courses", "courses you're currently studying"),
        BotCommand("updatematerials", "update courses materials"),
        BotCommand("settings", "bot settings"),
        BotCommand("enrollments", "manage your enrollments"),
        BotCommand("editor", "manage your editor accesses"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(user.chat_id))


async def set_root_commands(bot: Bot, user: User):
    commands = [
        BotCommand("courses", "courses you're currently studying"),
        BotCommand("updatematerials", "update courses materials"),
        BotCommand("settings", "bot settings"),
        BotCommand("enrollments", "manage your enrollments"),
        BotCommand("editor", "manage you editor accesses"),
        BotCommand("requestmanagement", "manage pending access request"),
        BotCommand("coursemanagement", "course management"),
        BotCommand("contentmanagement", "content management"),
        BotCommand("departments", "department management"),
        BotCommand("programs", "program management"),
        BotCommand("semesters", "semester management"),
        BotCommand("academicyears", "academic year management"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(user.chat_id))


async def set_my_commands(bot: Bot, user: User):
    role_names = [r.name for r in user.roles]
    if RoleName.USER in role_names and len(role_names) == 1:
        await set_user_commands(bot, user)
    elif RoleName.STUDENT in role_names and len(role_names) == 2:
        await set_student_commands(bot, user)
    elif RoleName.EDITOR.value in role_names and RoleName.ROOT not in role_names:
        await set_editor_commands(bot, user)
    elif RoleName.ROOT in role_names:
        await set_root_commands(bot, user)


T = TypeVar("T")


class Pager(Generic[T]):
    def __init__(self, i_list: List[T], offset: int, size: int):
        self.items: List[T] = i_list[offset : offset + size]
        self.has_next: bool = (offset + size) < len(i_list)
        self.next_offset = offset + size if self.has_next else None

        self.has_previous = offset > 0
        self.previous_offset = offset - size if self.has_previous else None


def paginate(item_list: List[T], offset: int, size: int) -> Pager:
    items: List[T] = item_list[offset : offset + size]

    has_next: bool = (offset + size) < len(item_list)
    next_offset = offset + size if has_next else None

    has_previous = offset > 0
    previous_offset = offset - size if has_previous else None

    return Pager(
        items=items,
        has_next=has_next,
        next_offset=next_offset,
        has_previous=has_previous,
        previous_offset=previous_offset,
    )
