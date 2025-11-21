# Code by DHT@Matthew

import logging
import multiprocessing
import socket
import sys
import time
from pathlib import Path

from helper.parser.sip_parsers import SipMessageParser
from helper.sip_session import SIPRTPSession
from model.sip_message import SDPMessage, SIPMessage


class SIPServer:
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

        # logger
        self.logger = logging.getLogger("SIPServer")
        logging.basicConfig(
            level=logging.INFO,
            # format="[%(levelname)s] - %(asctime)s - %(message)s - %(pathname)s:%(lineno)d",
            format="[%(levelname)s] - %(asctime)s - %(message)s - %(threadName)s",
            filemode="w+",
            filename="sip_server.log",
            datefmt="%y-%m-%d %H:%M:%S",
        )
        console_handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(console_handler)
        # message parser
        self.sip_message_parser = SipMessageParser()

        # shared boolean flag
        self.is_running = multiprocessing.Value("b", False)
        self.listening_incoming_call = multiprocessing.Value("b", False)

        # RTP
        self.sessions: dict[str, SIPRTPSession] = {}

    def setup_sip_listener(self) -> socket.socket:
        """Create and bind the UDP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.recv_port))
        self.logger.info(f"Listening for SIP messages on {self.host}:{self.recv_port}")
        return sock

    def sip_listener_loop(self, host: str, port: int) -> None:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(levelname)s] %(asctime)s - %(processName)s:%(threadName)s - %(message)s",
            filemode="a+",
            filename="sip_server_child.log",
        )
        logger = logging.getLogger("SIPListener")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        logger.info(f"Listening for SIP messages on {host}:{port}")
        sock.bind((host, port))

        while True:
            try:
                data, addr = sock.recvfrom(4096)
                msg = data.decode(errors="ignore")
                logger.info(f"Received: {len(msg)}byte data from {addr}")
                self.message_handler(msg, addr, sock)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")

        sock.close()

    def start(self) -> multiprocessing.Process:
        """Spawn the listener in a new process."""
        listener_proc = multiprocessing.Process(
            target=self.sip_listener_loop, args=(self.host, self.recv_port)
        )
        # kills automatically when parent exits
        listener_proc.daemon = True
        self.logger.info("Starting")
        listener_proc.start()

        self.logger.info(f"SIP listener started on PID {listener_proc.pid}")
        return listener_proc

    def stop(self, proc: multiprocessing.Process) -> None:
        """Terminate the listener process."""
        proc.terminate()
        proc.join()
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

        # Extract Call-ID (unique identifier for this call)
        call_id = parsed_message.headers.get("Call-ID")
        if not call_id:
            self.logger.error("No Call-ID in message")
            self._send_response(addr, "SIP/2.0 400 Bad Request\r\n\r\n", socket)
            return

        # Route by method
        match parsed_message.request_line.method:
            case "INVITE":
                self._handle_invite(parsed_message, call_id, addr, socket)
                self.logger.info("INVITE")

            case "ACK":
                self._handle_ack(parsed_message, call_id, addr)
                self.logger.info("ACK")

            case "BYE":
                self._handle_bye(parsed_message, call_id, addr, socket)
                self.logger.info("ACK")

            case "CANCEL":
                self._handle_cancel(parsed_message, call_id, addr, socket)
                self.logger.info("CANCEL")

            case "RTP":
                self.logger.info("RTP")

            case _:
                self.logger.warning(
                    f"Unhandled method: {parsed_message.request_line.method}"
                )
                # Send 501 Not Implemented
                response = self._build_response(parsed_message, "501 Not Implemented")
                self._send_response(addr, response, socket)

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

        # Check if session already exists
        if call_id in self.sessions:
            self.logger.warning(f"Call {call_id} already exists (re-INVITE?)")
            # For simplicity, reject re-INVITE
            response = self._build_response(msg, "488 Not Acceptable Here")
            self._send_response(addr, response, socket)
            return

        # Extract SDP from body
        if not msg.body:
            self.logger.error("INVITE has no SDP body")
            response = self._build_response(msg, "400 Bad Request")
            self._send_response(addr, response, socket)
            return

        try:
            # Parse SDP (assumes msg.body is already SDPMessage or dict)

            sdp_offer = msg.body
            self.logger.debug(sdp_offer)
            # Create RTP session
            session = SIPRTPSession(local_ip=self.local_ip)

            # Handle INVITE, get SDP answer
            sdp_answer = session.handle_invite(sdp_offer)  # type: ignore[reportArgumentType]

            # Store session
            self.sessions[call_id] = session

            self.logger.info(f"> RTP session created for call {call_id}")
            self.logger.info(
                f"   Local RTP ports: send={session.local_send_port}, recv={session.local_recv_port}"
            )

            # Build 200 OK response
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

        # Check if session exists
        session = self.sessions.get(call_id)
        if not session:
            self.logger.error(f"ACK for unknown call {call_id}")
            return

        try:
            # Start sending audio
            audio_path = "./output/transcode/greeting.wav"
            wav_path = Path(audio_path)
            if wav_path.exists():
                self.logger.info(f"Playing audio file: {audio_path}")
                session.start_audio(mode="wav", wav_path=wav_path)
                # session.start_audio(mode="dummy")
            else:
                # session.start_audio(mode="dummy")
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

        # Check if session exists
        session = self.sessions.get(call_id)
        if not session:
            self.logger.warning(f"BYE for unknown call {call_id}")
            # Still send 200 OK (idempotent)
            response = self._build_response(msg, "200 OK")
            self._send_response(addr, response, socket)
            return

        try:
            # Generate filename from call_id
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{call_id[:8]}.wav"
            output_path = Path("./recoding") / filename

            # Stop RTP and save
            session.stop_and_save(output_path)

            self.logger.info(f"> Saved recording to {output_path}")

            # Remove session
            del self.sessions[call_id]

            # Send 200 OK
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
            session.stop_and_save()  # Don't save (no audio yet)
            del self.sessions[call_id]

        # Send 200 OK
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
        # Serialize SDP to string
        sdp_body = self._serialize_sdp(sdp_answer)
        self.logger.info(f"[SDP ANSWER]\n{sdp_body}")

        lines = [
            "SIP/2.0 200 OK",
            f"Via: {request.headers.get('Via')}",
            f"From: {request.headers.get('From')}",
            f"To: {request.headers.get('To')}",  # Should add ;tag=xxx
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

        # Session-level fields
        lines.append(f"v={sdp.version}")
        lines.append(f"o={sdp.origin}")
        lines.append(f"s={sdp.session_name}")

        if sdp.connection_info:
            lines.append(f"c={sdp.connection_info}")

        # Time descriptions
        for td in sdp.time_descriptions:
            lines.append(f"t={td.active_times}")

        # Media descriptions
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
        self.logger.debug(f"Sending response to {addr}:\n{response}")  # Debug
        socket.sendto(response.encode("utf-8"), addr)


if __name__ == "__main__":
    server = SIPServer()
    server_process = server.start()

    print(server_process)
    while True:
        try:
            pass
        except KeyboardInterrupt:
            server.stop(server_process)
