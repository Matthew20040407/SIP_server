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

    m: str = Field(default=..., alias="media")
    i: str | None = Field(default=None, alias="title")
    c: str | None = Field(default=None, alias="connection_info")
    b: list[str] | None = Field(default=None, alias="bandwidth_info")
    k: str | None = Field(default=None, alias="encryption_key")
    a: list[str] | None = Field(default=None, alias="attributes")


class SDPMessage(BaseModel):
    """Top-level SDP session description model."""

    model_config = ConfigDict(populate_by_name=True)

    v: int = Field(default=0, alias="version")
    o: str = Field(default=..., alias="origin")
    s: str = Field(default="-", alias="session_name")

    i: str | None = Field(default=None, alias="title")
    u: str | None = Field(default=None, alias="uri")
    e: list[str] | None = Field(default=None, alias="email")
    p: list[str] | None = Field(default=None, alias="phone")
    c: str | None = Field(default=None, alias="connection_info")
    b: list[str] | None = Field(default=None, alias="bandwidth_info")
    t: list[TimeDescription] = Field(default=..., alias="time_descriptions")
    z: str | None = Field(default=None, alias="timezone_adjustments")
    k: str | None = Field(default=None, alias="encryption_key")
    a: list[str] | None = Field(default=None, alias="attributes")
    m: list[MediaDescription] | None = Field(default=None, alias="media_descriptions")


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


class SIPMessageStatus(BaseModel):
    type: SIPMethod
