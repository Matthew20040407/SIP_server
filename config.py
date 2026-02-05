# Code by DHT@Matthew

from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv("./.env")


def config_factory(env_prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=env_prefix,
        env_file="./.env",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
    )


class SIPConfig(BaseSettings):
    sip_local_ip: str = "192.168.1.102"
    sip_local_port: int = 5062
    sip_transfer_port: int = 5060
    sip_server_ip: str = "192.168.1.170"

    model_config = config_factory("SIP_")


class WebSocketSetting(BaseSettings):
    ws_host: str = "192.168.1.102"
    ws_port: int = 8080
    ws_send_queue_max: int = 1000
    ws_recv_queue_max: int = 1000

    @property
    def ws_url(self) -> str:
        return f"ws://{self.ws_host}:{self.ws_port}"

    model_config = config_factory("WS_")


class RTPConfig(BaseSettings):
    rtp_start_post: int = 31000
    rtp_end_post: int = 31010
    rtp_send_queue_max: int = 500
    rtp_recv_queue_max: int = 500

    model_config = config_factory("RTP_")


class LoggingConfig(BaseSettings):
    log_level: str = "INFO"
    sip_log_file: str = "./sip_server.log"
    call_center_log_file: str = "./call_center.log"

    model_config = config_factory("LOGGING_")


class FileConfig(BaseSettings):
    recording_dir: Path = Path("./recoding")
    output_dir: Path = Path("./output")
    max_recording_age_day: int = 7

    model_config = config_factory("FILE_")

    @field_validator("recording_dir", mode="after")
    @classmethod
    def ensure_dir_exists(cls, dir_name: Path) -> Path:
        dir_name.mkdir(parents=True, exist_ok=True)
        (dir_name / "convented").mkdir(exist_ok=True)
        (dir_name / "response").mkdir(exist_ok=True)
        (dir_name / "transcode").mkdir(exist_ok=True)
        return dir_name

    @field_validator("output_dir", mode="after")
    @classmethod
    def ensure_output_dir_exists(cls, dir_name: Path) -> Path:
        dir_name.mkdir(parents=True, exist_ok=True)
        return dir_name


class OpenaiConfig(BaseSettings):
    api_key: str = ""

    model_config = config_factory("OPENAI_")
