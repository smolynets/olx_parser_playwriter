from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    to_email: str
    from_email: str
    email_app_password: str
    mongo_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

settings = Settings()
