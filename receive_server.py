import logging
import socket
import sys
import threading
import time
from pathlib import Path

from helper.sip_parsers import SipMessageParser
from helper.sip_session import SIPRTPSession
from helper.ws_command import WSCommandHelper
from helper.ws_helper import ws_server
from model.sip_message import SDPMessage, SIPMessage
from model.ws_command import CommandType, WebSocketCommand


class RelayServer:
    def __init__(
        self,
        host: str = "192.168.1.101",
        transf_port: int = 5060,
        recv_port: int = 5062,
        local_ip: str = "192.168.1.101",
    ):
        self.host = host
        self.recv_port = recv_port
        self.transf_port = transf_port
        self.local_ip = local_ip

        self.logger = logging.getLogger("SIPServer")
        logging.basicConfig(
            level=logging.INFO,
            format="[%(levelname)s] - %(asctime)s - %(message)s - %(pathname)s:%(lineno)d",
            filemode="w+",
            filename="sip_server.log",
            datefmt="%y-%m-%d %H:%M:%S",
        )
        console_handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(console_handler)

        self.sip_message_parser = SipMessageParser()

        self.sessions: dict[str, SIPRTPSession] = {}

        self.ws_command_helper = WSCommandHelper()
        self._stop_flag = threading.Event()

    def setup_sip_listener(self) -> socket.socket:
        """Create and bind the UDP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.recv_port))
        self.logger.info(f"Listening for SIP messages on {self.host}:{self.recv_port}")
        return sock

    def sip_listener_loop(self, host: str, port: int) -> None:
        logger = logging.getLogger("SIPListener")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        logger.info(f"Listening for SIP messages on {host}:{port}")
        sock.bind((host, port))
        sock.setblocking(False)

        while not self._stop_flag.is_set():
            try:
                ws_message = ws_server.get_message()
                self.logger.info(ws_message)
                time.sleep(1)
                if ws_message:
                    self.logger.info(ws_message.type)
                    self.ws_message_handler(ws_message)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")

            try:
                data, addr = sock.recvfrom(4096)
                msg = data.decode(errors="ignore")
                logger.info(f"Received: {len(msg)}byte data from {addr}")
                self.message_handler(msg, addr, sock)
            except KeyboardInterrupt:
                break
            except socket.error as e:
                if e.errno == 11:
                    continue
                logger.error(f"Error: {e}")
            except Exception as e:
                logger.error(f"Error: {e}")

        sock.close()

    def start(self) -> threading.Thread:
        listener_thread = threading.Thread(
            target=self.sip_listener_loop, args=(self.host, self.recv_port), daemon=True
        )
        listener_thread.start()
        return listener_thread

    def stop(self, proc: threading.Thread) -> None:
        """Terminate the listener thread."""
        self._stop_flag.set()
        proc.join(timeout=5.0)
        if proc.is_alive():
            self.logger.warning("Thread did not stop gracefully within timeout")
        else:
            self.logger.info("SIP listener stopped.")

    def message_handler(
        self, message: str, addr: tuple[str, int], socket: socket.socket
    ) -> None:
        """
        Process incoming SIP messages.

        This is the main entry point for all SIP traffic.
        We handle: INVITE, ACK, BYE
        We ignore: OPTIONS, REGISTER, etc. (for now)
        """
        self.logger.info(f"Processing message from {addr}: {message[:20]}")
        self.logger.debug(message)

        try:
            parsed_message = self.sip_message_parser.parse_sip_message(message)
            self.logger.debug(parsed_message.model_dump_json(indent=4))
        except Exception as e:
            self.logger.error(f"Failed to parse SIP message: {e}")
            self._send_response(addr, "SIP/2.0 400 Bad Request\r\n\r\n", socket)
            return

        call_id = parsed_message.headers.get("Call-ID")
        if not call_id:
            self.logger.error("No Call-ID in message")
            self._send_response(addr, "SIP/2.0 400 Bad Request\r\n\r\n", socket)
            return

        match parsed_message.request_line.method:
            case "INVITE":
                self.logger.info("INVITE")
                self._handle_invite(parsed_message, call_id, addr, socket)

            case "ACK":
                self.logger.info("ACK")
                self._handle_ack(parsed_message, call_id, addr)

            case "BYE":
                self.logger.info("BYE")
                self._handle_bye(parsed_message, call_id, addr, socket)

            case "CANCEL":
                self.logger.info("CANCEL")
                self._handle_cancel(parsed_message, call_id, addr, socket)

            case _:
                self.logger.warning(
                    f"Unhandled method: {parsed_message.request_line.method}"
                )

                response = self._build_response(parsed_message, "501 Not Implemented")
                self._send_response(addr, response, socket)

    def ws_message_handler(self, ws_command: WebSocketCommand) -> None:
        self.logger.info(f"Processing message from WS: {ws_command.type}")
        self.logger.debug(ws_command.content)

        match ws_command.type:
            case CommandType.CALL:
                self.logger.info("[WS] incoming CAll")
                phone_number = str(ws_command.content)
                self._handle_call(phone_number=phone_number)

            case CommandType.RTP:
                self.logger.info("[WS] incoming RTP")

            case CommandType.BYE:
                self.logger.info("[WS] incoming BYE")

            case _:
                self.logger.error(f"Invalid command: {ws_command.type}")

    def _handle_invite(
        self,
        msg: SIPMessage,
        call_id: str,
        addr: tuple[str, int],
        socket: socket.socket,
    ) -> None:
        """
        Handle SIP INVITE: Create RTP session and send 200 OK.

        Flow:
        1. Check if call already exists (re-INVITE?)
        2. Parse SDP from body
        3. Create RTPSession
        4. Generate SDP answer
        5. Send 200 OK with SDP
        """
        self.logger.info(f"> INVITE from {addr} (call_id={call_id})")

        if call_id in self.sessions:
            self.logger.warning(f"Call {call_id} already exists (re-INVITE?)")

            response = self._build_response(msg, "488 Not Acceptable Here")
            self._send_response(addr, response, socket)
            return

        if not msg.body:
            self.logger.error("INVITE has no SDP body")
            response = self._build_response(msg, "400 Bad Request")
            self._send_response(addr, response, socket)
            return

        try:
            sdp_offer = msg.body
            self.logger.debug(sdp_offer)

            session = SIPRTPSession(local_ip=self.local_ip)

            if isinstance(sdp_offer, str):
                raise ValueError(f"{type(sdp_offer)=} prefer SDPMessage")

            sdp_answer = session.handle_invite(sdp_offer)

            self.sessions[call_id] = session

            self.logger.info(f"> RTP session created for call {call_id}")
            self.logger.info(
                f"   Local RTP ports: send={session.local_send_port}, recv={session.local_recv_port}"
            )

            response = self._build_ok_response(msg, sdp_answer)
            self._send_response(addr, response, socket)

            self.logger.info(f"> Sent 200 OK to {addr}")

        except ValueError as e:
            self.logger.exception(f"Invalid SDP in INVITE: {e}")
            self.logger.error(msg.body)
            response = self._build_response(msg, "488 Not Acceptable Here")
            self._send_response(addr, response, socket)

        except Exception as e:
            self.logger.exception(f"Failed to handle INVITE: {e}")
            response = self._build_response(msg, "500 Server Internal Error")
            self._send_response(addr, response, socket)

    def _handle_ack(
        self,
        msg: SIPMessage,
        call_id: str,
        addr: tuple[str, int],
    ) -> None:
        """
        Handle SIP ACK: Start sending audio.

        ACK is the final handshake after 200 OK.
        Once we receive ACK, the call is fully established.
        """
        self.logger.info(f"> ACK from {addr} (call_id={call_id})")

        session = self.sessions.get(call_id)
        if not session:
            self.logger.error(f"ACK for unknown call {call_id}")
            return

        try:
            audio_path = "./output/transcode/greeting.wav"
            wav_path = Path(audio_path)
            if wav_path.exists():
                self.logger.info(f"Playing audio file: {audio_path}")
                session.start_audio(mode="wav", wav_path=wav_path)

            else:
                ...
            self.logger.info(f"> Started sending audio for call {call_id}")

        except Exception as e:
            self.logger.exception(f"Failed to start audio: {e}")

    def _handle_bye(
        self,
        msg: SIPMessage,
        call_id: str,
        addr: tuple[str, int],
        socket: socket.socket,
    ) -> None:
        """
        Handle SIP BYE: End call and save recording.

        BYE terminates the call. We must:
        1. Stop RTP
        2. Save received audio
        3. Send 200 OK
        4. Clean up session
        """
        self.logger.info(f"> BYE from {addr} (call_id={call_id})")

        session = self.sessions.get(call_id)
        if not session:
            self.logger.warning(f"BYE for unknown call {call_id}")

            response = self._build_response(msg, "200 OK")
            self._send_response(addr, response, socket)
            return

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{call_id[:8]}.wav"
            output_path = Path("./recording") / filename

            session.stop_and_save(output_path)

            self.logger.info(f"> Saved recording to {output_path}")

            del self.sessions[call_id]

            response = self._build_response(msg, "200 OK")
            self._send_response(addr, response, socket)

            self.logger.info(f"> Call {call_id} terminated")

        except Exception as e:
            self.logger.exception(f"Failed to handle BYE: {e}")
            response = self._build_response(msg, "500 Server Internal Error")
            self._send_response(addr, response, socket)

    def _handle_cancel(
        self,
        msg: SIPMessage,
        call_id: str,
        addr: tuple[str, int],
        socket: socket.socket,
    ) -> None:
        """
        Handle SIP CANCEL: Abort ringing call.

        CANCEL is used to abort a call before it's answered.
        For simplicity, we treat it like BYE.
        """
        self.logger.info(f"> CANCEL from {addr} (call_id={call_id})")

        session = self.sessions.get(call_id)
        if session:
            session.stop_and_save()
            del self.sessions[call_id]

        response = self._build_response(msg, "200 OK")
        self._send_response(addr, response, socket)

    def _build_response(self, request: SIPMessage, status: str) -> str:
        """
        Build a simple SIP response.

        Args:
            request: Original request message
            status: Status line (e.g., "200 OK", "404 Not Found")

        Returns:
            Complete SIP response as string
        """
        lines = [
            f"SIP/2.0 {status}",
            f"Via: {request.headers.get('Via')}",
            f"From: {request.headers.get('From')}",
            f"To: {request.headers.get('To')}",
            f"Call-ID: {request.headers.get('Call-ID')}",
            f"CSeq: {request.headers.get('CSeq')}",
            "Content-Length: 0",
            "",
            "",
        ]
        return "\r\n".join(lines)

    def _build_ok_response(self, request: SIPMessage, sdp_answer: SDPMessage) -> str:
        """
        Build 200 OK response with SDP body.

        Args:
            request: Original INVITE request
            sdp_answer: SDP answer from RTPSession

        Returns:
            Complete SIP response with SDP
        """

        sdp_body = self._serialize_sdp(sdp_answer)
        self.logger.debug(f"[SDP ANSWER]\n{sdp_body}")

        lines = [
            "SIP/2.0 200 OK",
            f"Via: {request.headers.get('Via')}",
            f"From: {request.headers.get('From')}",
            f"To: {request.headers.get('To')}",
            f"Call-ID: {request.headers.get('Call-ID')}",
            f"CSeq: {request.headers.get('CSeq')}",
            f"Contact: <sip:{self.local_ip}:{self.recv_port}>",
            "Content-Type: application/sdp",
            f"Content-Length: {len(sdp_body)}",
            "",
            sdp_body,
        ]
        return "\r\n".join(lines)

    def _serialize_sdp(self, sdp: SDPMessage) -> str:
        """
        Convert SDPMessage to SDP string format.

        Args:
            sdp: Pydantic SDPMessage

        Returns:
            SDP as string (RFC 4566 format)
        """
        lines = []

        lines.append(f"v={sdp.version}")
        lines.append(f"o={sdp.origin}")
        lines.append(f"s={sdp.session_name}")

        if sdp.connection_info:
            lines.append(f"c={sdp.connection_info}")

        for td in sdp.time_descriptions:
            lines.append(f"t={td.active_times}")

        if sdp.media_descriptions:
            for md in sdp.media_descriptions:
                lines.append(f"m={md.media}")

                if md.attributes:
                    for attr in md.attributes:
                        lines.append(f"a={attr}")
        lines.append("a=sendrecv")

        return "\r\n".join(lines) + "\r\n"

    def _send_response(
        self, addr: tuple[str, int], response: str, socket: socket.socket
    ) -> None:
        """
        Send SIP response to remote.

        Args:
            addr: Remote address (ip, port)
            response: Complete SIP response string
            socket: target socket

        NOTE: This assumes you have a UDP socket.
        Replace with your actual transport layer.
        """
        self.logger.debug(f"Sending response to {addr}:\n{response}")
        socket.sendto(response.encode("utf-8"), addr)

    def _handle_call(self, phone_number: str) -> str | None:
        """
        Initiate outbound call to SIP server.

        Args:
            phone_number: Target phone number to dial

        Returns:
            call_id if INVITE sent successfully, None on failure
        """
        import uuid

        call_id = str(uuid.uuid4())
        branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
        tag = uuid.uuid4().hex[:8]

        session = SIPRTPSession(local_ip=self.local_ip)
        local_rtp_port = session.local_recv_port

        if local_rtp_port is None:
            raise Exception(f"SIPRTPSession {local_rtp_port=}")
        sdp_body = self._build_sdp_offer(local_rtp_port)

        target_uri = f"sip:{phone_number}@{self.host}"
        invite = "\r\n".join(
            [
                f"INVITE {target_uri} SIP/2.0",
                f"Via: SIP/2.0/UDP {self.local_ip}:{self.recv_port};branch={branch}",
                f"From: <sip:relay@{self.local_ip}>;tag={tag}",
                f"To: <{target_uri}>",
                f"Call-ID: {call_id}",
                "CSeq: 1 INVITE",
                f"Contact: <sip:relay@{self.local_ip}:{self.recv_port}>",
                "Content-Type: application/sdp",
                "Max-Forwards: 70",
                f"Content-Length: {len(sdp_body)}",
                "",
                sdp_body,
            ]
        )

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(invite.encode("utf-8"), (self.host, self.transf_port))
            sock.close()

            self.sessions[call_id] = session
            self.logger.info(f"INVITE sent to {phone_number} (call_id={call_id})")

            return call_id

        except Exception as e:
            self.logger.exception(f"Failed to send INVITE: {e}")
            return None

    def _handle_rtp(self, rtp: bytes | str | None = None) -> None: ...

    def _build_sdp_offer(self, rtp_port: int) -> str:
        """Build minimal SDP offer for outbound call."""
        import time

        session_id = int(time.time())
        lines = [
            "v=0",
            f"o=relay {session_id} {session_id} IN IP4 {self.local_ip}",
            "s=Call",
            f"c=IN IP4 {self.local_ip}",
            "t=0 0",
            f"m=audio {rtp_port} RTP/AVP 0 8 101",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:8 PCMA/8000",
            "a=rtpmap:101 telephone-event/8000",
            "a=fmtp:101 0-16",
            "a=sendrecv",
        ]
        return "\r\n".join(lines) + "\r\n"


if __name__ == "__main__":
    server = RelayServer()
    server_process = server.start()

    print(server_process)
    while True:
        try:
            pass
        except KeyboardInterrupt:
            server.stop(server_process)
