# Code by DHT@Matthew

from enum import StrEnum

from pydantic import (  # pyright: ignore[reportMissingImports]
    BaseModel,
    ConfigDict,
    Field,
)


class SIPMessageType(StrEnum):
    REGISTER = "REGISTER"
    INVITE = "INVITE"
    ACK = "ACK"
    BYE = "BYE"
    CANCEL = "CANCEL"
    UPDATE = "UPDATE"
    REFER = "REFER"
    PRACK = "PRACK"
    SUBSCRIBE = "SUBSCRIBE"
    NOTIFY = "NOTIFY"
    PUBLISH = "PUBLISH"
    MESSAGE = "MESSAGE"
    INFO = "INFO"
    OPTIONS = "OPTIONS"


class SIPRequestLine(BaseModel):
    method: SIPMessageType
    uri: str
    version: str


class TimeDescription(BaseModel):
    """Represents one time description block: 't=' and optional 'r=' lines."""

    active_times: str = Field(..., alias="t")
    repeat_times: list[str] | None = Field(default=None, alias="r")


class MediaDescription(BaseModel):
    """Represents one media description block: 'm=' through optional attributes."""

    media: str = Field(..., alias="m")
    title: str | None = Field(default=None, alias="i")
    connection_info: str | None = Field(default=None, alias="c")
    bandwidth_info: list[str] | None = Field(default=None, alias="b")
    encryption_key: str | None = Field(default=None, alias="k")
    attributes: list[str] | None = Field(default=None, alias="a")


class SDPMessage(BaseModel):
    """Top-level SDP session description model."""

    model_config = ConfigDict(populate_by_name=True)

    version: int = Field(default=0, alias="v")
    origin: str = Field(..., alias="o")
    session_name: str = Field(default="-", alias="s")

    title: str | None = Field(default=None, alias="i")
    uri: str | None = Field(default=None, alias="u")
    email: list[str] | None = Field(default=None, alias="e")
    phone: list[str] | None = Field(default=None, alias="p")
    connection_info: str | None = Field(default=None, alias="c")
    bandwidth_info: list[str] | None = Field(default=None, alias="b")
    time_descriptions: list[TimeDescription] = Field(..., alias="t")
    timezone_adjustments: str | None = Field(default=None, alias="z")
    encryption_key: str | None = Field(default=None, alias="k")
    attributes: list[str] | None = Field(default=None, alias="a")
    media_descriptions: list[MediaDescription] | None = Field(default=None, alias="m")


class SIPMessage(BaseModel):
    request_line: SIPRequestLine
    headers: dict[str, str]
    body: str | SDPMessage


class SIPMessageStatus(StrEnum):
    type: SIPMessageType
