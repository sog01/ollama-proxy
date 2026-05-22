from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8080
    proxy_node_api_key: str = "change-me-shared-secret"
    proxy_ws_path: str = "/ws"
    proxy_request_timeout: int = 300
    proxy_heartbeat_interval: int = 20
    log_level: str = "info"

    proxy_version: str = "0.1.0-ollama-proxy"


settings = Settings()
