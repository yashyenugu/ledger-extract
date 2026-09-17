from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    minio_endpoint: str
    minio_public_endpoint: str = "localhost:9000"
    minio_root_user: str
    minio_root_password: str
    minio_bucket: str
    minio_use_ssl: bool = False


settings = Settings()
