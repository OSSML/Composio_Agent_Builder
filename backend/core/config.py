from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    # API Settings
    API_TITLE: str = "Composio Agent Builder"
    API_DESCRIPTION: str = "Composio Agent Builder API"
    ENVIRONMENT: str = "development"

    # Database Settings
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path(__file__).resolve().parents[1].as_posix()}/composio.db"
    AGENT_BUILDER_MODEL: str = "openai/gpt-4.1-mini-2025-04-14"
    AGENT_TEMPLATE_MODEL: str = "openai/gpt-4.1-mini-2025-04-14"

    # Temporary User Credentials
    USER_ID: str = "hey@example.com"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="allow"
    )

    # Env settings for logging customization
    ENV_MODE: str = "LOCAL"
    LOG_LEVEL: str = "INFO"


settings = Settings()
