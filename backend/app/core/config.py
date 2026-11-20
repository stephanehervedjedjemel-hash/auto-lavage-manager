from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./auto_lavage.db"
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str = "CHANGE_ME_BEFORE_DEPLOYMENT"
    jwt_expiration_minutes: int = 720
    bootstrap_secret: str = "CHANGE_ME_BOOTSTRAP_SECRET"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def cors_origin_list(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
settings = Settings()
