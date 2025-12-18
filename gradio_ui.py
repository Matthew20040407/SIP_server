import logging
import os
import sys
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import gradio as gr
from websockets.sync.client import connect

from config import Config
from helper.custom_sts_handler import LLM, Speech2Text, Text2Speech
from helper.PROMPT import SYSTEM_PROMPT
from helper.wav_handler import WavHandler
from helper.ws_command import WSCommandHelper
from model.rtp import PayloadType
from model.ws_command import CommandType

# Initialize handlers
ws_cmd = WSCommandHelper()
wav_handler = WavHandler()
logger = logging.getLogger()

# LLM and STT/TTS initialized")
stt = Speech2Text()
tts = Text2Speech()
llm_handler = LLM(SYSTEM_PROMPT)


# Global state for UI
class CallCenterState:
    def __init__(self):
        self.active_calls = {}
        self.call_history = deque(maxlen=100)
        self.transcripts = deque(maxlen=50)
        self.is_running = False
        self.ws_thread: threading.Thread | None = None
        self.stats = {
            "total_calls": 0,
            "active_calls": 0,
            "packets_processed": 0,
            "errors": 0,
        }


state = CallCenterState()


@dataclass
class RTPPacket:
    payload_type: PayloadType
    data: bytes

    @classmethod
    def from_hex(cls, payload_type: int, hex_string: str) -> "RTPPacket":
        return cls(
            payload_type=PayloadType(payload_type), data=bytes.fromhex(hex_string)
        )


class RTPSession:
    def __init__(self):
        self.call_id: str = ""
        self.codec: PayloadType = PayloadType.PCMA
        self.buffer: list[RTPPacket] = []
        self.start_time: datetime = datetime.now()

    def add_packet(self, packet: RTPPacket) -> bool:
        self.buffer.append(packet)
        return len(self.buffer) >= Config.CALL_CENTER_BUFFER_SIZE

    def flush(self) -> list[bytes]:
        data = [p.data for p in self.buffer]
        self.buffer.clear()
        return data


def process_websocket_messages(ws_url: str):
    """Background thread to process WebSocket messages"""
    session = RTPSession()

    packet_count = 0

    try:
        with connect(ws_url) as websocket:
            logger.info(f"WebSocket connected to {ws_url}")
            state.is_running = True

            for message in websocket:
                if not state.is_running:
                    logger.info("Stopping WebSocket processing")
                    break

                try:
                    cmd = ws_cmd.parser(str(message))
                except Exception as e:
                    logger.warning(f"Invalid message format: {e}")
                    state.stats["errors"] += 1
                    continue

                if not isinstance(cmd.content, str):
                    continue

                if cmd.type == CommandType.CALL_ANS:
                    session.buffer.clear()
                    session.call_id = cmd.content
                    session.start_time = datetime.now()

                    state.active_calls[session.call_id] = {
                        "start_time": session.start_time,
                        "packets": 0,
                        "transcripts": [],
                    }
                    state.stats["total_calls"] += 1
                    state.stats["active_calls"] += 1

                    logger.info(f"Call started: {session.call_id}")
                    continue

                if cmd.type == CommandType.BYE:
                    if session.call_id in state.active_calls:
                        call_data = state.active_calls[session.call_id]
                        duration = (
                            datetime.now() - call_data["start_time"]
                        ).total_seconds()

                        state.call_history.append(
                            {
                                "call_id": session.call_id,
                                "start_time": call_data["start_time"],
                                "duration": duration,
                                "packets": call_data["packets"],
                                "transcripts": call_data["transcripts"],
                            }
                        )

                        del state.active_calls[session.call_id]
                        state.stats["active_calls"] -= 1

                    logger.info(f"Call ended: {session.call_id}")
                    continue

                if cmd.type != CommandType.RTP:
                    continue

                try:
                    payload_type, rtp_hex = cmd.content.split("##")
                    packet = RTPPacket.from_hex(int(payload_type), rtp_hex)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Malformed RTP packet: {e}")
                    state.stats["errors"] += 1
                    continue

                session.codec = packet.payload_type

                if session.add_packet(packet):
                    packet_count += Config.CALL_CENTER_BUFFER_SIZE
                    state.stats["packets_processed"] += Config.CALL_CENTER_BUFFER_SIZE

                    if session.call_id in state.active_calls:
                        state.active_calls[session.call_id]["packets"] += (
                            Config.CALL_CENTER_BUFFER_SIZE
                        )

                    logger.info(f"Processed {packet_count} packets")

                    wav_path = None
                    response_audio_path = Path(f"./output/response/{uuid4()}.wav")
                    try:
                        wav_path = wav_handler.hex2wav(session.flush(), session.codec)
                        logger.info(f"WAV file converted at {wav_path}")

                        audio_transcribe, language = stt.transcribe(wav_path)
                        llm_response = llm_handler.generate_response(
                            audio_transcribe, language
                        )

                        # Store transcript
                        transcript_entry = {
                            "call_id": session.call_id,
                            "timestamp": datetime.now(),
                            "user": audio_transcribe,
                            "assistant": llm_response,
                            "language": language,
                        }
                        state.transcripts.append(transcript_entry)

                        if session.call_id in state.active_calls:
                            state.active_calls[session.call_id]["transcripts"].append(
                                transcript_entry
                            )

                        logger.info(f"User: {audio_transcribe}")
                        logger.info(f"LLM Response: {llm_response}")

                        tts.generate(llm_response, response_audio_path, language)
                        wav_data = wav_handler.wav2base64(response_audio_path)

                        websocket.send(
                            str(
                                ws_cmd.builder(
                                    CommandType.RTP, f"{session.call_id}##{wav_data}"
                                )
                            )
                        )
                        logger.info("Audio sent")
                    except Exception as e:
                        logger.error(f"Processing failed: {e}")
                        state.stats["errors"] += 1
                        session.buffer.clear()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        state.is_running = False
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        state.is_running = False
        state.stats["errors"] += 1


def start_call_center(ws_url: str):
    """Start the call center processing"""
    if state.is_running:
        return "Call center is already running!"

    if not ws_url:
        ws_url = os.getenv("WS_URL", "ws://192.168.1.101:8080")

    state.ws_thread = threading.Thread(
        target=process_websocket_messages, args=(ws_url,), daemon=True
    )
    state.ws_thread.start()
    return f"Call center started. Connected to {ws_url}"


def stop_call_center():
    """Stop the call center processing"""
    if not state.is_running:
        return "Call center is not running!"

    state.is_running = False
    if state.ws_thread:
        state.ws_thread.join(timeout=5)
    return "Call center stopped"


def get_stats():
    """Get current statistics"""
    return {
        "Total Calls": state.stats["total_calls"],
        "Active Calls": state.stats["active_calls"],
        "Packets Processed": state.stats["packets_processed"],
        "Errors": state.stats["errors"],
        "Status": "Running" if state.is_running else "Stopped",
    }


def get_active_calls():
    """Get list of active calls"""
    if not state.active_calls:
        return "No active calls"

    output = []
    for call_id, data in state.active_calls.items():
        duration = (datetime.now() - data["start_time"]).total_seconds()
        output.append(
            f"Call ID: {call_id}\n"
            f"  Duration: {duration:.1f}s\n"
            f"  Packets: {data['packets']}\n"
            f"  Transcripts: {len(data['transcripts'])}\n"
        )
    return "\n".join(output)


def get_recent_transcripts(limit: int = 10):
    """Get recent transcripts"""
    if not state.transcripts:
        return "No transcripts yet"

    output = []
    for t in list(state.transcripts)[-limit:]:
        output.append(
            f"[{t['timestamp'].strftime('%H:%M:%S')}] Call: {t['call_id'][:8]}... ({t['language']})\n"
            f"  User: {t['user']}\n"
            f"  AI: {t['assistant']}\n"
        )
    return "\n".join(output)


def get_call_history(limit: int = 10):
    """Get call history"""
    if not state.call_history:
        return "No call history yet"

    output = []
    for call in list(state.call_history)[-limit:]:
        output.append(
            f"Call ID: {call['call_id']}\n"
            f"  Start: {call['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  Duration: {call['duration']:.1f}s\n"
            f"  Packets: {call['packets']}\n"
            f"  Exchanges: {len(call['transcripts'])}\n"
        )
    return "\n".join(output)


def process_audio_input(audio_file):
    """Process audio input from user and get AI response"""
    if audio_file is None:
        return None, "Please record or upload an audio file", ""

    if not state.is_running:
        return None, "Error: Call center is not running. Please start it first.", ""

    try:
        # Convert audio file path to Path object
        audio_path = Path(audio_file)

        # Transcribe the audio
        logger.info(f"Processing audio file: {audio_path}")
        audio_transcribe, language = stt.transcribe(audio_path)

        if not audio_transcribe:
            return None, "Could not transcribe audio. Please try again.", ""

        logger.info(f"Transcribed ({language}): {audio_transcribe}")

        # Get LLM response
        llm_response = llm_handler.generate_response(audio_transcribe, language)
        logger.info(f"LLM Response: {llm_response}")

        # Generate audio response
        response_audio_path = Path(f"./output/response/web_ui_{uuid4()}.wav")
        tts.generate(llm_response, response_audio_path, language)

        # Store in transcripts for display
        transcript_entry = {
            "call_id": "web-ui",
            "timestamp": datetime.now(),
            "user": audio_transcribe,
            "assistant": llm_response,
            "language": language,
        }
        state.transcripts.append(transcript_entry)

        # Format transcript display
        transcript_text = (
            f"[{transcript_entry['timestamp'].strftime('%H:%M:%S')}] Web UI ({language})\n"
            f"You: {audio_transcribe}\n"
            f"AI: {llm_response}"
        )

        return str(response_audio_path), transcript_text, llm_response

    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        return None, f"Error: {str(e)}", ""


def send_audio_to_call(audio_file, call_id: str):
    """Send audio directly to an active call"""
    if audio_file is None:
        return "Please provide an audio file"

    if not call_id:
        return "Please enter a Call ID"

    if not state.is_running:
        return "Error: Call center is not running"

    if call_id not in state.active_calls:
        return f"Error: Call ID {call_id} not found in active calls"

    try:
        # Convert audio to base64 and send via WebSocket
        audio_path = Path(audio_file)
        wav_data = wav_handler.wav2base64(audio_path)
        logger.info(f"{wav_data[:30]=}")
        return f"Feature requires WebSocket connection integration. Audio prepared for call {call_id}"

    except Exception as e:
        logger.error(f"Error sending audio to call: {e}")
        return f"Error: {str(e)}"


def create_ui():
    """Create the Gradio UI"""
    with gr.Blocks(
        title="SIP Call Center Control Panel",
        theme=gr.themes.Soft(),  # pyright: ignore[reportPrivateImportUsage]
    ) as demo:
        gr.Markdown("# SIP Call Center Control Panel")
        gr.Markdown("Monitor and manage your AI-powered call center system")

        with gr.Tab("Control"):
            with gr.Row():
                ws_url_input = gr.Textbox(
                    label="WebSocket URL",
                    value=os.getenv("WS_URL", "ws://192.168.1.101:8080"),
                    placeholder="ws://host:port",
                )

            with gr.Row():
                start_btn = gr.Button("Start Call Center", variant="primary")
                stop_btn = gr.Button("Stop Call Center", variant="stop")

            status_output = gr.Textbox(label="Status", interactive=False)

            start_btn.click(
                fn=start_call_center, inputs=[ws_url_input], outputs=[status_output]
            )
            stop_btn.click(fn=stop_call_center, outputs=[status_output])

        with gr.Tab("Dashboard"):
            gr.Markdown("## System Statistics")
            stats_display = gr.JSON(label="Statistics")
            refresh_stats_btn = gr.Button("Refresh Stats")
            refresh_stats_btn.click(fn=get_stats, outputs=[stats_display])

            gr.Markdown("## Active Calls")
            active_calls_display = gr.Textbox(
                label="Active Calls", lines=10, interactive=False
            )
            refresh_calls_btn = gr.Button("Refresh Active Calls")
            refresh_calls_btn.click(fn=get_active_calls, outputs=[active_calls_display])

        with gr.Tab("Audio Chat"):
            gr.Markdown("## Talk to the AI Assistant")
            gr.Markdown(
                "Record or upload audio to interact with the AI assistant directly through the web interface."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(
                        sources=["microphone", "upload"],
                        type="filepath",
                        label="Record or Upload Audio",
                    )
                    process_audio_btn = gr.Button(
                        "Send Audio", variant="primary", size="lg"
                    )

                with gr.Column(scale=1):
                    audio_output = gr.Audio(
                        label="AI Response Audio", type="filepath", interactive=False
                    )

            with gr.Row():
                conversation_display = gr.Textbox(
                    label="Conversation",
                    lines=8,
                    interactive=False,
                    placeholder="Your conversation will appear here...",
                )

            with gr.Row():
                ai_response_text = gr.Textbox(
                    label="AI Response Text",
                    lines=4,
                    interactive=False,
                    placeholder="AI response will appear here...",
                )

            process_audio_btn.click(
                fn=process_audio_input,
                inputs=[audio_input],
                outputs=[audio_output, conversation_display, ai_response_text],
            )

            gr.Markdown("---")
            gr.Markdown("### Send Audio to Active Call")
            gr.Markdown(
                "Send pre-recorded audio directly to an active call (requires call to be in progress)."
            )

            with gr.Row():
                call_id_input = gr.Textbox(
                    label="Call ID", placeholder="Enter the Call ID from active calls"
                )
                audio_to_call = gr.Audio(
                    sources=["microphone", "upload"],
                    type="filepath",
                    label="Audio to Send",
                )

            send_to_call_btn = gr.Button("Send to Call")
            send_result = gr.Textbox(label="Result", interactive=False)

            send_to_call_btn.click(
                fn=send_audio_to_call,
                inputs=[audio_to_call, call_id_input],
                outputs=[send_result],
            )

        with gr.Tab("Transcripts"):
            gr.Markdown("## Recent Conversation Transcripts")
            transcript_limit = gr.Slider(
                minimum=5,
                maximum=50,
                value=10,
                step=5,
                label="Number of recent transcripts to show",
            )
            transcripts_display = gr.Textbox(
                label="Transcripts", lines=20, interactive=False
            )
            refresh_transcripts_btn = gr.Button("Refresh Transcripts")
            refresh_transcripts_btn.click(
                fn=get_recent_transcripts,
                inputs=[transcript_limit],
                outputs=[transcripts_display],
            )

        with gr.Tab("Call History"):
            gr.Markdown("## Call History")
            history_limit = gr.Slider(
                minimum=5,
                maximum=50,
                value=10,
                step=5,
                label="Number of recent calls to show",
            )
            history_display = gr.Textbox(
                label="Call History", lines=15, interactive=False
            )
            refresh_history_btn = gr.Button("Refresh History")
            refresh_history_btn.click(
                fn=get_call_history, inputs=[history_limit], outputs=[history_display]
            )

        with gr.Tab("Configuration"):
            gr.Markdown("## Current Configuration")
        # Auto-refresh for dashboard (every 3 seconds) using gr.Timer
        timer = gr.Timer(value=3, active=True)
        timer.tick(fn=get_stats, outputs=[stats_display])
        timer.tick(fn=get_active_calls, outputs=[active_calls_display])

    return demo


def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="[%(levelname)s] - %(asctime)s - %(message)s - %(pathname)s:%(lineno)d",
        datefmt="%y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("gradio_ui.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Create output directories
    Config.validate()

    # Create and launch UI
    demo = create_ui()
    demo.launch(
        server_name="192.168.1.101", server_port=7860, share=False, show_error=True
    )


if __name__ == "__main__":
    main()
