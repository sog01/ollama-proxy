import uuid

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    proxy_ws_url: str = "ws://localhost:8080/ws"
    node_api_key: str = "change-me-shared-secret"
    node_id: str = ""
    ollama_base_url: str = "http://localhost:11434"
    reconnect_max_backoff: float = 30.0
    heartbeat_interval: float = 20.0
    log_level: str = "info"

    def resolved_node_id(self) -> str:
        return self.node_id or f"node-{uuid.uuid4().hex[:8]}"


settings = Settings()
