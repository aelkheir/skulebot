from typing import Optional

from telegram.ext import Application, CallbackContext, ExtBot

from src import constants
from src.buttons import Buttons, ar_buttons, en_buttons


class CustomContext(CallbackContext[ExtBot, dict, dict, dict]):
    """Custom class for context."""

    def __init__(
        self,
        application: Application,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        super().__init__(application=application, chat_id=chat_id, user_id=user_id)
        self._message_id: Optional[int] = None

    @property
    def buttons(self) -> Buttons:
        """Custom shortcut to access a value stored in the bot_data dict"""
        user_lang = self.user_data.get("language_code")
        buttons: Buttons = ar_buttons if user_lang == constants.AR else en_buttons
        return buttons
