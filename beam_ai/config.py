from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # database
    database_url: str = (
        "postgresql+psycopg://beam_ai:beam_ai_dev@localhost:5432/beam_ai"
    )

    # environment
    env: str = "development"

    # image storage
    image_store_path: str = "./data/images"

    # calibration — assumption: 90 days, confirm with FSE/hardware team
    default_calibration_validity_days: int = 90

    # ml
    ai_model_version: str = "rf_baseline_v0"


# single shared instance — import this everywhere
settings = Settings()