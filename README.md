# SkuleBot

### Run The Project Locally

1. #### [Recommended] Create a Virtual Enviroment.

   [Creation of virtual environments](https://docs.python.org/3/library/venv.html)

1. #### Install Requirements

   ```console
   $ python -m pip install -r requirements/dev.txt
   ```

1. #### Set Environment Variables

   Create a `.env` file at the project root directory and replace `<...>` with actual values

   **`skulebot/.env`**

   ```shell
   # Required
   ENV=development
   BOT_TOKEN=<your-bot-token>
   DATABASE_URL=<SQLAlchemy-database-url>
   # use ";" to seperate ids, if there are multiple
   ROOTIDS=<telegram-user-ids>

   # Optional
   ERROR_CHANNEL_CHAT_ID=<error-channel-chat-id>
   ```

1. #### Run the project

   ```console
   $ python main.py
   ```

### Project Structure

```bash
skulebot/
├── src/
│   ├── models/ # SQLAlchemy mappings definitions
│   │   ├── user.py
│   │   ├── course.py
│   │   ├── ....
│   ├── conversations/ # Conversation handlers
│   │   ├── a.py
│   │   ├── b.py
│   │   ├── ....
│   ├── commands.py # Command handlers
│   ├── messages.py # Text messages
│   ├── buttons.py # InlineKeyboardButtons
│   ├── constants.py
│   ├── config.py
│   ├── database.py
│   ├── ...
│   └── ...
├── main.py
└── .env
```

- The directory `src/models` contains `SQLAlchemy` class mappings.
- `src/conversations` defines `ConversationHandler`s of the bot. Each file is its own conversation, with one exception.
- The `src/messages.py` module contains message strings that are used accross callbacks.
  ```python
  def start(update: Update, context: ContextType):
    await update.message.reply_text(
      text=messages.hello(context.user_data["lang"])
    )
  ```
  Here `message.hello()` will simply return a string (e.g `Hello`) in user's locale. The reason why we're not hardcoding the strings in the callback is that we want to offload handling of localization to the `messages` module, and thus simplify code in callbacks.
- Simillar to `src/messages.py`, `src/buttons.py` contains localized `InlineKeyboardButton`s.
  ```python
  def start(update: Update, context: ContextType):
    keyboard = [
      [buttons.hello(context.user_data["lang"])]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
      text=messages.hello(),
      reply_markup=reply_markup
    )
  ```
- `src/commands.py` defines `CommandHandler`s.
