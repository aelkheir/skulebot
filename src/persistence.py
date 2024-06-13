import json
from collections import defaultdict
from logging import getLogger
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import scoped_session, sessionmaker
from telegram.ext import DictPersistence, PersistenceInput

from src import queries
from src.database import engine
from src.models import ChatData, Conversation, User, UserData


class SQLPersistence(DictPersistence):
    def __init__(
        self,
    ) -> None:

        self.logger = getLogger(__name__)

        self.session = scoped_session(sessionmaker(bind=engine, autoflush=False))
        chat_data_json = json.dumps(self._load_chat_data())
        user_data_json = json.dumps(self._load_user_data())
        conversations_json = json.dumps(self._load_conversations())
        self.logger.info("Database loaded successfully!")

        super().__init__(
            chat_data_json=chat_data_json,
            user_data_json=user_data_json,
            conversations_json=conversations_json,
            store_data=PersistenceInput(
                user_data=True, chat_data=True, bot_data=False, callback_data=False
            ),
        )

    def _load_user_data(self) -> dict:
        data = {}
        user_datas = self.session.query(UserData).all()
        for user_data in user_datas:
            data[user_data.user.telegram_id] = user_data.data
        return data

    def _load_chat_data(self) -> dict:
        data = {}
        chat_datas = self.session.query(ChatData).all()
        for chat_data in chat_datas:
            data[chat_data.user.chat_id] = chat_data.data
        return data

    def _load_conversations(self) -> dict:
        data = defaultdict(dict)
        conversations = (
            self.session.query(Conversation).order_by(Conversation.name).all()
        )
        for conversation in conversations:
            data[conversation.name][conversation.key] = json.loads(
                conversation.new_state
            )
        return data

    async def update_user_data(self, user_id: int, data: dict) -> None:
        """Will update the user_data (if changed).
        Args:
            user_id (:obj:`int`): The user the data might have been changed for.
            data (:obj:`dict`): The :attr:`telegram.ext.Dispatcher.user_data`
            ``[user_id]``.
        """
        await super().update_user_data(user_id, data)
        user_data = self.session.scalar(
            select(UserData).join(User).filter(User.telegram_id == user_id)
        )

        if user_data is None:
            user_data = UserData(
                user=queries.user(self.session, telegram_id=user_id),
                data={},
            )
            self.session.add(user_data)

        if user_data.data == data:
            return

        user_data.data = data
        self.session.commit()

    async def update_chat_data(self, chat_id: int, data: dict) -> None:
        """Will update the chat_data (if changed).
        Args:
            chat_id (:obj:`int`): The chat the data might have been changed for.
            data (:obj:`dict`): The :attr:`telegram.ext.Dispatcher.chat_data`
            ``[chat_id]``.
        """
        await super().update_chat_data(chat_id, data)
        chat_data = self.session.scalar(
            select(ChatData).join(User).filter(User.chat_id == chat_id)
        )

        if chat_data is None:
            chat_data = ChatData(
                user=self.session.scalar(select(User).where(User.chat_id == chat_id)),
                data={},
            )
            self.session.add(chat_data)

        if chat_data.data == data:
            return

        chat_data.data = data
        self.session.commit()

    async def update_conversation(
        self, name: str, key: tuple[int, ...], new_state: Optional[object]
    ) -> None:
        """Will update the conversations for the given handler.
        Args:
            name (:obj:`str`): The handler's name.
            key (:obj:`tuple`): The key the state is changed for.
            new_state (:obj:`tuple` | :obj:`any`): The new state for the given key.
        """
        await super().update_conversation(name, key, new_state)
        key_json = json.dumps(key)
        new_state_json = json.dumps(new_state)
        conv = self.session.scalar(
            select(Conversation).filter(
                (Conversation.name == name) & (Conversation.key == key_json)
            )
        )

        if conv is None:
            conv = Conversation(name=name, key=key_json)
            self.session.add(conv)

        if conv.new_state == new_state_json:
            return

        conv.new_state = new_state_json

        self.session.commit()
