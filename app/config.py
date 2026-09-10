from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="INTEGRATION_FRAMEWORK_",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    service_name: str = "enterprise-api-integration-framework"
    github_base_url: HttpUrl = HttpUrl("http://localhost:9000/github")
    github_token: SecretStr = Field(default=SecretStr("local-development-token"))
    directory_base_url: HttpUrl = HttpUrl("http://localhost:9000/directory")
    directory_api_key: SecretStr = Field(default=SecretStr("local-development-key"))
    notification_base_url: HttpUrl = HttpUrl("http://localhost:9000/notifications")
    notification_bearer_token: SecretStr = Field(
        default=SecretStr("local-development-token")
    )
    webhook_secret: SecretStr = Field(
        default=SecretStr("local-development-webhook-secret")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
