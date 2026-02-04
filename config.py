# Code by DHT@Matthew

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

load_dotenv("./.env")


def config_factory(env_prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=env_prefix,
        env_file="./.env",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
    )


class Config:
    """Centralized configuration for SIP server"""

    # SIP Configuration
    SIP_LOCAL_IP: str = os.getenv("SIP_LOCAL_IP", "192.168.1.102")
    SIP_LOCAL_PORT: int = int(os.getenv("SIP_LOCAL_PORT", "5062"))
    SIP_TRANSFER_PORT: int = int(os.getenv("SIP_TRANSFER_PORT", "5060"))
    SIP_SERVER_IP: str = os.getenv("SIP_SERVER_IP", "192.168.1.170")

    # WebSocket Configuration
    WS_HOST: str = os.getenv("WS_HOST", "192.168.1.102")
    WS_PORT: int = int(os.getenv("WS_PORT", "8080"))
    WS_URL: str = os.getenv("WS_URL", f"ws://{WS_HOST}:{WS_PORT}")

    # RTP Configuration
    RTP_PORT_START: int = int(os.getenv("RTP_PORT_START", "31000"))
    RTP_PORT_END: int = int(os.getenv("RTP_PORT_END", "31010"))

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SIP_LOG_FILE: str = os.getenv("SIP_LOG_FILE", "sip_server.log")
    CALL_CENTER_LOG_FILE: str = os.getenv("CALL_CENTER_LOG_FILE", "call_center.log")

    # File Management
    RECORDING_DIR: Path = Path(os.getenv("RECORDING_DIR", "./recording"))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./output"))
    MAX_RECORDING_AGE_DAYS: int = int(os.getenv("MAX_RECORDING_AGE_DAYS", "7"))

    # Call Center Configuration
    CALL_CENTER_BUFFER_SIZE: int = int(os.getenv("CALL_CENTER_BUFFER_SIZE", "120"))

    # Queue Limits (prevent unbounded memory growth)
    WS_SEND_QUEUE_MAX: int = int(os.getenv("WS_SEND_QUEUE_MAX", "1000"))
    WS_RECV_QUEUE_MAX: int = int(os.getenv("WS_RECV_QUEUE_MAX", "1000"))
    RTP_SEND_QUEUE_MAX: int = int(os.getenv("RTP_SEND_QUEUE_MAX", "500"))
    RTP_RECV_QUEUE_MAX: int = int(os.getenv("RTP_RECV_QUEUE_MAX", "500"))

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")

        # Create required directories
        cls.RECORDING_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (cls.OUTPUT_DIR / "convented").mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "response").mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "transcode").mkdir(exist_ok=True)


class SIPConfig(BaseSettings):
    sip_local_ip: str = "192.168.1.102"
    sip_local_port: int = 5062
    sip_transfer_port: int = 5060
    sip_server_port: str = "192.168.1.170"

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


class LoggingConfing(BaseSettings):
    log_level: str = "INFO"
    sip_log_file: str = "./sip_server.log"
    call_center_log_file: str = "./call_center.log"

    model_config = config_factory("LOGGING_")


class FileConfig(BaseSettings):
    recording_dir: Path = Path("./recoding")
    output_dir: Path = Path("./output")
    max_recording_age_day: int = 7

    model_config = config_factory("FILE_")
    
    @field_validator("output_dir", "recording_dir", mode="after")
    @classmethod
    def ensure_dir_exists(cls, dir_name: Path) -> Path:
        dir_name.mkdir(parents=True, exist_ok=True) 
        return dir_name
        
