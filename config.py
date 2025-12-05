# Code by DHT@Matthew

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("./.env")


class Config:
    """Centralized configuration for SIP server"""

    # SIP Configuration
    SIP_LOCAL_IP: str = os.getenv("SIP_LOCAL_IP", "192.168.1.101")
    SIP_LOCAL_PORT: int = int(os.getenv("SIP_LOCAL_PORT", "5062"))
    SIP_TRANSFER_PORT: int = int(os.getenv("SIP_TRANSFER_PORT", "5060"))
    SIP_SERVER_IP: str = os.getenv("SIP_SERVER_IP", "192.168.1.170")

    # WebSocket Configuration
    WS_HOST: str = os.getenv("WS_HOST", "192.168.1.101")
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
