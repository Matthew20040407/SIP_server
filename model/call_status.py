import time
from enum import StrEnum

from pydantic import BaseModel, Field

from helper.sip_session import SIPRTPSession
from model.sip_message import SDPMessage, SIPRequest


class CallDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class CallState(StrEnum):
    CALLING = "CALLING"
    RINGING = "RINGING"
    EARLY = "EARLY"

    ANSWERED = "ANSWERED"
    ESTABLISHED = "ESTABLISHED"
    TERMINATING = "TERMINATING"
    TERMINATED = "TERMINATED"


class CallSession(BaseModel):
    call_id: str
    direction: CallDirection
    state: CallState

    local_addr: tuple[str, int]
    remote_addr: tuple[str, int]

    from_tag: str
    to_tag: str | None = None
    cseq: int = 1

    rtp_session: SIPRTPSession | None = None

    created_at: float = Field(default_factory=time.time)
    answered_at: float | None = None
    terminated_at: float | None = None


class InboundCall(CallSession):
    direction: CallDirection = Field(default=CallDirection.INBOUND, init=False)

    original_invite: SIPRequest | None = None

    remote_sdp: SDPMessage | None = None
    local_sdp: SDPMessage | None = None


class OutboundCall(CallSession):
    direction: CallDirection = Field(default=CallDirection.OUTBOUND, init=False)

    target_uri: str = ""

    local_sdp: SDPMessage | None = None
    remote_sdp: SDPMessage | None = None

    invite_branch: str = ""
    ack_sent: bool = False

    last_invite_time: float = Field(default_factory=time.time)
    invite_timeout: float = 32.0
