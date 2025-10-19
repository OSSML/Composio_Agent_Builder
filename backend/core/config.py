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
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path(__file__).resolve().parents[2].as_posix()}/composio.db"
    AGENT_BUILDER_MODEL: str = "google_genai/gemini-2.5-flash"
    AGENT_TEMPLATE_MODEL: str = "openai/gpt-5-mini-2025-08-07"

    # Temporary User Credentials
    USER_ID: str = "hey@example.com"

    model_config = SettingsConfigDict(env_file = ".env", env_file_encoding = "utf-8", extra = "allow")


settings = Settings()
