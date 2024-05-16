import os
import re

if os.getenv("ENV") != "production":
    from dotenv import load_dotenv

    load_dotenv(override=True)


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = (
        os.getenv("DATABASE_URL")
        if os.getenv("ENV") != "production"
        else re.sub(r"^postgres", "postgresql+psycopg2", os.getenv("DATABASE_URL"))
    )
    ROOTIDS = tuple(
        (int(id_.strip()) for id_ in ids.split(","))
        if (ids := os.getenv("ROOTIDS"))
        else None
    )
    ERROR_CHANNEL_CHAT_ID = (
        int(id) if (id := os.getenv("ERROR_CHANNEL_CHAT_ID")) else None
    )

    @classmethod
    def validate(cls):
        required_vars = ["BOT_TOKEN", "DATABASE_URL", "ROOTIDS"]
        missing_vars = [key for key in required_vars if getattr(cls, key) is None]

        if missing_vars:
            raise ValueError(
                f"Required environment variables are missing: {', '.join(missing_vars)}"
            )


class ProductionConfig(Config):
    PORT = int(port) if (port := os.getenv("PORT")) else 8443
    WEBHOOK_SERCRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    @classmethod
    def validate(cls):
        super().validate()
        required_vars = ["PORT", "WEBHOOK_SERCRET_TOKEN", "WEBHOOK_URL"]
        missing_vars = [key for key in required_vars if getattr(cls, key) is None]

        if missing_vars:
            raise ValueError(
                f"Required environment variables are missing: {', '.join(missing_vars)}"
            )


env_config = ProductionConfig if os.getenv("ENV") == "production" else Config
env_config.validate()
