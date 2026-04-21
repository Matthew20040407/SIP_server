# Code by DHT@Matthew

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class SIPMethod(StrEnum):
    """SIP request methods"""

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
    method: SIPMethod
    uri: str
    version: str = "SIP/2.0"


class SIPStatusLine(BaseModel):
    version: str = "SIP/2.0"
    status_code: int
    reason_phrase: str


class SIPHeaders(BaseModel):
    model_config = ConfigDict(extra="allow")

    via: str | None = Field(default=None, alias="Via")
    call_id: str | None = Field(default=None, alias="Call-ID")
    from_: str | None = Field(default=None, alias="From")
    to: str | None = Field(default=None, alias="To")
    cseq: str | None = Field(default=None, alias="CSeq")
    content_type: str | None = Field(default=None, alias="Content-Type")
    content_length: int | None = Field(default=None, alias="Content-Length")


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


class SIPRequest(BaseModel):
    request_line: SIPRequestLine
    headers: SIPHeaders
    body: str | SDPMessage = ""


class SIPResponse(BaseModel):
    status_line: SIPStatusLine
    headers: SIPHeaders
    body: str | SDPMessage = ""


class SIPMessage(BaseModel):
    request_line: SIPRequestLine
    headers: SIPHeaders
    body: str | SDPMessage


class SIPMessageStatus(StrEnum):
    type: SIPMethod
