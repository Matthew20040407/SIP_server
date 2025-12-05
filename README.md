# SIP Relay Server v2

A Python-based SIP relay server with OpenAI integration for intelligent voice interactions. Supports SIP signaling, RTP media handling, WebSocket-driven real-time control, and AI-powered audio transcription and response generation. Designed for environments requiring call routing, audio streaming, SIP integration, and AI-assisted call center functionality.

## Features

- **SIP Signaling Support**
  INVITE, ACK, BYE, CANCEL
- **RTP Media Streaming**
  Real-time audio using G.711 (PCMA/PCMU)
- **WebSocket Integration**
  Bi-directional control and audio transmission
- **WAV Audio Playback**
  Automatic audio playback on call establishment
- **Call Recording**
  Saves inbound audio streams to WAV files
- **Dual Operation Modes**

  - Incoming call handling (server mode)
  - Outgoing call initiation (client mode)

- **Dynamic RTP Port Allocation**
- **Multi-Session Management**
- **OpenAI Integration**
  - Speech-to-Text (Whisper API)
  - Text-to-Speech (TTS API)
  - LLM-powered responses (GPT-4o-mini)
- **Call Center Mode**
  - Real-time audio buffering and processing
  - AI-powered conversation handling
- **Environment-based Configuration**
  - Centralized config management
  - .env file support

| Command     | Format                             |
| ----------- | ---------------------------------- |
| CALL        | CALL:{PHONE_NUMBER}                |
| RTP         | RTP:{PCM Byte String}              |
| RTP         | RTP:{CALL_ID}##{BASE64 AUDIO}      |
| CALL_ANS    | CALL_ANS:{CALL_ID}                 |
| CALL_IGNORE | CALL_IGNORE:{CALL_ID}              |
| HANGUP      | HANGUP:{CALL_ID}                   |
| BYE         | BYE:{CALL_ID}                      |
| RING_ANS    | RING_ANS:{PHONE_NUMBER}            |
| RING_IGNORE | RING_IGNORE:{CALL_ID}              |
| CALL_FAILED | CALL_FAILED:{STATUS_CODE} {REASON} |

---

## Architecture Overview

### Core Components

- **RelayServer** (`receive_server.py`)
  Handles SIP signaling and orchestrates all subsystems.
- **RTPHandler** (`helper/rtp_handler.py`)
  Manages RTP packet sending and receiving.
- **SIPRTPSession** (`helper/sip_session.py`)
  Maintains session state and resources.
- **SIPMessageParser** (`helper/sip_parsers.py`)
  Parses and validates SIP messages.
- **WebSocket Helper** (`helper/ws_helper.py`)
  Handles WebSocket communication.
- **LLMHandler** (`call_center.py`)
  Integrates OpenAI services for speech-to-text, text-to-speech, and LLM responses.
- **Config** (`config.py`)
  Centralized configuration management with environment variable support.

### Project Structure

```text
SIP_server_v2/
  main.py               # Main entry point
  receive_server.py     # SIP relay server
  call_center.py        # AI call center implementation
  reply_handler.py      # OpenAI integration (STT, TTS, LLM)
  config.py             # Configuration management
  helper/
    rtp_handler.py      # RTP packet handling
    sip_session.py      # Session management
    sip_parsers.py      # SIP message parsing
    ws_helper.py        # WebSocket communication
    ws_command.py       # WebSocket command helpers
    wav_handler.py      # WAV file operations
  model/
    sip_message.py      # SIP message models
    rtp.py              # RTP packet models
    ws_command.py       # WebSocket command models
    call_status.py      # Call status enums
  recording/            # Call recordings
  output/
    convented/          # Converted audio files
    response/           # AI response audio
    transcode/          # Transcoded audio (greeting.wav)
```

---

## Requirements

- **Python 3.12+**
- **OpenAI API Key** (required for AI features)
- Dependencies:

  - `openai >= 2.8.1`
  - `pydantic >= 2.12.4`
  - `pydub >= 0.25.1`
  - `python-dotenv >= 1.2.1`
  - `websockets >= 15.0.1`
  - `realtimestt >= 0.3.104`

### Installation

```bash
git clone <repository-url>
cd SIP_server_v2
uv sync
```

Create a `.env` file:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# SIP Configuration (optional, defaults shown)
SIP_LOCAL_IP=192.168.1.101
SIP_LOCAL_PORT=5062
SIP_TRANSFER_PORT=5060
SIP_SERVER_IP=192.168.1.170

# WebSocket Configuration (optional)
WS_HOST=192.168.1.101
WS_PORT=8080

# RTP Configuration (optional)
RTP_PORT_START=31000
RTP_PORT_END=31010

# Logging (optional)
LOG_LEVEL=INFO

# Call Center (optional)
CALL_CENTER_BUFFER_SIZE=120
```

---

## Configuration

The server uses a centralized `Config` class that loads settings from environment variables (`.env` file). All configuration is managed through the `config.py` module.

### Configuration Options

See the `.env` file created during installation for all available options. The configuration is validated on startup to ensure required values (like `OPENAI_API_KEY`) are present.

---

## Usage

### Running the SIP Server

Using the main entry point (recommended):

```bash
python main.py
```

This starts both the SIP server and WebSocket server with proper configuration validation.

### Running the Call Center (AI Mode)

To run the AI-powered call center that processes audio with OpenAI:

```bash
python call_center.py
```

This mode:
- Connects to the WebSocket server
- Buffers incoming RTP audio packets
- Transcribes audio using Whisper
- Generates responses using GPT-4o-mini
- Converts responses to speech using TTS
- Sends audio back through the call

---

## WebSocket Interface

### Commands (client → server)

#### Initiate Outgoing Call

```WsCommand
CALL:{phone_number>
```

Example:

```WsCommand
CALL:0912341234
```

#### Send RTP Audio

```WsCommand
RTP:{call_id>##<base64_audio>
```

#### Terminate Call

```WsCommand
BYE
```

---

### Events (server → client)

- `RING_ANS:{phone_number>##<call_id>`
- `CALL_ANS:{call_id>`
- `CALL_IGNORE:{call_id>`
- `CALL_FAILED:{status> <reason>`
- `BYE:{call_id>`
- `RTP:{hex_audio_data>`

---

## Call Flow

### Incoming Call

1. Receive INVITE
2. Parse SDP offer
3. Allocate RTP ports
4. Reply with 200 OK + SDP
5. Receive ACK
6. Start RTP
7. Play greeting audio
8. Record inbound audio
9. Handle BYE
10. Finalize recording

### Outgoing Call

1. Receive WebSocket CALL command
2. Allocate RTP ports
3. Send INVITE
4. Handle 180 Ringing
5. Receive 200 OK
6. Send ACK
7. Stream audio
8. Handle BYE

---

## Audio Handling

### Supported Codecs

- **PCMA (G.711 A-law)** – Payload 8
- **PCMU (G.711 μ-law)** – Payload 0

### Audio

- 8000 Hz sample rate
- Mono
- 16-bit PCM
- 160 samples per 20 ms frame

### Audio Playback

Place WAV files in:

```bash
./output/transcode/greeting.wav
```

---

## RTP Configuration

- Default port range: **31000–31010**
- Ports allocated in **pairs**
- 4-port spacing between each session
- Automatic cleanup on session termination

### Packet Properties

- UDP transport
- G.711 payload
- 160-byte payload per packet
- Automatic sequence number rollover

---

## OpenAI Integration

The system integrates with OpenAI's APIs for AI-powered voice interactions:

### Components

- **OpenAiSTT** (`reply_handler.py`)
  - Uses Whisper-1 model for speech-to-text
  - Supports multiple languages (default: Chinese)
  - Transcribes audio files to text

- **OpenAiTTS** (`reply_handler.py`)
  - Uses GPT-4o-mini-TTS for text-to-speech
  - Multiple voice options (default: alloy)
  - Adjustable speed (0.25-4.0x)

- **OpenAiLLM** (`reply_handler.py`)
  - Uses GPT-4o-mini for text generation
  - Customizable system prompts
  - Generates conversational responses

### Usage Example

```python
from reply_handler import OpenAiSTT, OpenAiTTS, OpenAiLLM
from pathlib import Path

# Initialize
api_key = "your-api-key"
stt = OpenAiSTT(api_key)
tts = OpenAiTTS(api_key)
llm = OpenAiLLM(api_key, model="gpt-4o-mini")

# Process audio
text = stt.transcribe(Path("input.wav"))
response = llm.chat(text)
tts.speak(response, output=Path("output.wav"))
```

---

## Logging

- **File**: `sip_server.log`
- **Console**: stdout
- **Format**: `[LEVEL] - TIMESTAMP - MESSAGE - FILE:LINE`

### Levels

- INFO
- DEBUG
- WARNING
- ERROR

---

## Development Notes

- Full type hint coverage
- Pydantic for all data structures
- Match/case routing
- Structured logging practices

### Testing

```bash
python receive_server.py
```

---

## Troubleshooting

### Port in Use

```python
socket.error: [Errno 98] Address already in use
```

Change port or free the process.

### Missing Audio

- Check UDP firewall rules
- Verify `greeting.wav` exists
- Confirm RTP ports allocated correctly

### SIP Not Received

- Verify IP and port config
- Check NAT/firewall
- Review SIP logs

### Immediate Call Failure

- Confirm SIP server IP/port
- Codec compatibility
- Look at SIP response codes

### OpenAI API Issues

**Missing API Key:**
```
ValueError: OPENAI_API_KEY is required
```
- Ensure `.env` file exists with valid `OPENAI_API_KEY`
- Check that the API key is active in your OpenAI account

**Authentication Error:**
- Verify API key is correct and not expired
- Check OpenAI account has available credits

**Audio Processing Issues:**
- Ensure audio files are in WAV format for transcription
- Check that `CALL_CENTER_BUFFER_SIZE` is appropriate for your use case
- Verify network connectivity to OpenAI APIs

---

## Author

Code by DHT@Matthew

---
