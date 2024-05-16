# SkuleBot

### Run project locally

1. #### Create a virtual enviroment.

   [Creation of virtual environments](https://docs.python.org/3/library/venv.html)

1. #### Install requirements

   ```console
   $ python -m pip install -r requirements/dev.txt
   ```

1. #### Set environment variables

   Create a `.env` file at the project root directory and replace `<...>` with actual values

   **`skulebot/.env`**

   ```shell
   # Required
   BOT_TOKEN=<your-bot-token>
   DATABASE_URL=<SQLAlchemy-connection-url>
   # use "," to seperate ids, if there are multiple
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
│   │   ├── __init__.py
│   │   ├── a.py
│   │   ├── b.py
│   ├── commands.py # Command handlers
│   ├── messages.py
│   ├── buttons.py
│   ├── constants.py
│   ├── config.py
│   └── database.py
├── main.py
└── .env
```
