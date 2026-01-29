# SIP Relay Server v2

A Python-based SIP relay server with advanced AI integration for intelligent voice interactions. Supports SIP signaling, RTP media handling, WebSocket-driven real-time control, and AI-powered audio transcription and response generation. Designed for call routing, audio streaming, SIP integration, and AI-assisted call center functionality.

## Features

### SIP & Telephony

- **SIP Signaling** - INVITE, ACK, BYE, CANCEL message handling
- **RTP Media Streaming** - Real-time audio using G.711 (PCMA/PCMU)
- **Dynamic RTP Port Allocation** - Automatic port management with pair allocation
- **Multi-Session Management** - Handle multiple concurrent calls
- **Call Recording** - Automatic timestamped WAV recordings of inbound audio
- **Dual Operation Modes** - Incoming call handling (server) and outgoing call initiation (client)

### AI & Speech Processing

- **Speech-to-Text** - Faster-Whisper for local transcription (multi-language)
- **Text-to-Speech** - Piper TTS with multi-language voice models
- **LLM Integration** - Three backend options:
  - API Backend (remote HTTP LLM server)
  - Local Backend (Qwen3 model on GPU)
  - OpenAI Backend (GPT-4o-mini)
- **Voice Activity Detection (VAD)** - Silero VAD for speech boundary detection
- **Language Detection** - Automatic language identification (langid)

### Integration & Control

- **WebSocket Interface** - Bi-directional control and audio transmission
- **Real-time Audio Streaming** - Base64-encoded audio over WebSocket
- **Environment-based Configuration** - Centralized config with .env support

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                         SIP Server v2                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌─────────────────┐                   │
│  │  SIP Clients │◄───────►│  RelayServer    │                   │
│  │  (VoIP)      │  UDP    │  (SIP Signaling)│                   │
│  └──────────────┘         └────────┬────────┘                   │
│                                    │                            │
│                           ┌────────▼────────┐                   │
│                           │  SIPRTPSession  │                   │
│                           │  Management     │                   │
│                           └────────┬────────┘                   │
│                                    │                            │
│         ┌──────────────────────────┼──────────────────────┐     │
│         │                          │                      │     │
│  ┌──────▼──────┐  ┌────────────────▼───────┐  ┌───────────▼─┐   │
│  │ RTPHandler  │  │    VADHandler          │  │ SIPParsers  │   │
│  │ (Audio I/O) │  │ (Voice Activity Detect)│  │ (SIP/SDP)   │   │
│  └──────┬──────┘  └────────────────────────┘  └─────────────┘   │
│         │                                                       │
│  ┌──────▼──────────────────────────────────┐                    │
│  │     WebSocket Server                    │                    │
│  │     (Real-time control & audio feed)    │                    │
│  └──────┬──────────────────────────────────┘                    │
│         │                                                       │
│  ┌──────▼──────────────────────────────────┐                    │
│  │     Call Center (AI Mode)               │                    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐    │                    │
│  │  │   STT   │ │   LLM   │ │   TTS   │    │                    │
│  │  │(Whisper)│ │(Backend)│ │ (Piper) │    │                    │
│  │  └─────────┘ └─────────┘ └─────────┘    │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component            | File                    | Description                                            |
| -------------------- | ----------------------- | ------------------------------------------------------ |
| **RelayServer**      | `receive_server.py`     | Main SIP message handler and session orchestrator      |
| **SIPRTPSession**    | `helper/sip_session.py` | RTP session lifecycle, port allocation, audio handling |
| **RTPHandler**       | `helper/rtp_handler.py` | Bidirectional RTP packet transmission and reception    |
| **VADHandler**       | `helper/rtp_handler.py` | Silero-based voice activity detection                  |
| **SIPMessageParser** | `helper/sip_parsers.py` | SIP/SDP message parsing and validation                 |
| **WebSocketServer**  | `helper/ws_helper.py`   | WebSocket communication for real-time control          |
| **CallCenter**       | `call_center.py`        | AI pipeline: STT → LLM → TTS                           |
| **LLM Backends**     | `helper/llm_backends/`  | Pluggable LLM backends (API, Local, OpenAI)            |
| **Config**           | `config.py`             | Centralized configuration management                   |

### Project Structure

```text
SIP_server_v2/
├── main.py                    # Main entry point
├── receive_server.py          # SIP relay server
├── call_center.py             # AI call center implementation
├── config.py                  # Configuration management
│
├── helper/
│   ├── rtp_handler.py         # RTP packet handling + VAD
│   ├── sip_session.py         # Session management
│   ├── sip_parsers.py         # SIP message parsing
│   ├── ws_helper.py           # WebSocket server
│   ├── ws_command.py          # WebSocket command helpers
│   ├── wav_handler.py         # WAV file operations
│   ├── custom_sts_handler.py  # Faster-Whisper STT + Piper TTS
│   ├── openai_sts_handler.py  # OpenAI STT/TTS (legacy)
│   ├── PROMPT.py              # System prompt for AI
│   └── llm_backends/
│       ├── llm_backend.py     # Abstract base class
│       ├── api.py             # Remote API backend
│       ├── local.py           # Local Qwen3 backend
│       ├── openai.py          # OpenAI API backend
│       └── models.py          # Type definitions
│
├── model/
│   ├── sip_message.py         # SIP/SDP message models
│   ├── rtp.py                 # RTP packet models
│   ├── ws_command.py          # WebSocket command models
│   └── call_status.py         # Call state enums
│
├── voices/                    # Piper TTS voice models
│   ├── en/                    # English voices
│   ├── zh/                    # Chinese voices
│   └── .../                   # Other languages
│
├── output/
│   ├── transcode/             # Greeting audio (greeting.wav)
│   ├── converted/             # Converted audio files
│   └── response/              # AI response audio
│
└── recording/                 # Call recordings
```

---

## Requirements

### System Requirements

- **Python 3.12+**
- **CUDA 12.x** (for GPU acceleration of ML models)
- **FFmpeg** (for audio conversion)
- Sufficient disk space for voice models (~500MB+)

### Dependencies

Core dependencies (managed via `pyproject.toml`):

```text
accelerate>=1.12.0          # GPU acceleration
bitsandbytes>=0.48.2        # Quantization
faster-whisper>=1.2.1       # Speech-to-text
huggingface-hub>=0.36.0     # Model downloading
jieba>=0.42.1               # Chinese tokenization
langid>=1.1.6               # Language detection
openai>=2.8.1               # OpenAI API client
piper-tts>=1.3.0            # Text-to-speech
pydantic>=2.12.4            # Data validation
pydub>=0.25.1               # Audio processing
python-dotenv>=1.2.1        # .env support
silero-vad>=6.2.0           # Voice activity detection
transformers>=4.51.3        # HuggingFace models
websockets>=15.0.1          # WebSocket protocol
```

---

## Installation

### Option 1: Docker (Recommended)

```bash
git clone <repository-url>
cd SIP_server_v2

# Copy and configure environment
cp .env.docker.example .env
# Edit .env with your settings (SIP_LOCAL_IP, OPENAI_API_KEY, etc.)

# Build and start services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Docker Requirements:**
- Docker Engine 20.10+
- Docker Compose v2.0+
- Approximately 2GB disk space for images
- Host network mode (for SIP/RTP compatibility)

**Volume Mounts:**
- `./voices/` - TTS voice models (~500MB)
- `./output/` - Audio output files
- `./recording/` - Call recordings
- `./output/transcode/greeting.wav` - Greeting audio

### Option 2: Local Installation

```bash
git clone <repository-url>
cd SIP_server_v2

# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here

# SIP Configuration
SIP_LOCAL_IP=192.168.1.101        # Your server's IP address
SIP_LOCAL_PORT=5062               # SIP listening port
SIP_TRANSFER_PORT=5060            # SIP transfer/relay port
SIP_SERVER_IP=192.168.1.170       # Remote SIP server IP

# WebSocket Configuration
WS_HOST=192.168.1.101
WS_PORT=8080
WS_URL=ws://192.168.1.101:8080

# RTP Configuration
RTP_PORT_START=31000              # Start of RTP port range
RTP_PORT_END=31010                # End of RTP port range

# Logging
LOG_LEVEL=INFO
SIP_LOG_FILE=sip_server.log
CALL_CENTER_LOG_FILE=call_center.log

# File Management
RECORDING_DIR=./recording
OUTPUT_DIR=./output
MAX_RECORDING_AGE_DAYS=7

# Performance Tuning
CALL_CENTER_BUFFER_SIZE=120       # Audio packets per utterance
WS_SEND_QUEUE_MAX=1000
WS_RECV_QUEUE_MAX=1000
RTP_SEND_QUEUE_MAX=500
RTP_RECV_QUEUE_MAX=500
```

---

## Usage

### Running the SIP Server

Start the main server (SIP + WebSocket):

```bash
uv run receive_server.py
```

This initializes:

- SIP listener on `SIP_LOCAL_IP:SIP_LOCAL_PORT`
- WebSocket server on `WS_HOST:WS_PORT`
- Configuration validation
- Logging setup

### Running the Call Center (AI Mode)

In a separate terminal, start the AI call processing:

```bash
uv run call_center.py
```

The call center:

1. Connects to the WebSocket server
2. Receives RTP audio packets
3. Buffers audio with VAD-based speech detection
4. Transcribes speech using Faster-Whisper
5. Generates responses using the configured LLM backend
6. Converts responses to speech using Piper TTS
7. Sends audio back through the call

---

## Call Flows

### Incoming Call

```text
SIP Client                    Server
    │                           │
    │──── INVITE + SDP ────────►│
    │                           │ Parse SDP, allocate RTP ports
    │◄─── 200 OK + SDP ─────────│
    │                           │
    │──── ACK ─────────────────►│
    │                           │ Start RTP, play greeting.wav
    │◄═══ RTP Audio ═══════════►│ Bidirectional audio
    │                           │ Record inbound audio
    │──── BYE ─────────────────►│
    │                           │ Save recording, cleanup
    │◄─── 200 OK ───────────────│
    │                           │
```

### Outgoing Call (via WebSocket)

```text
WebSocket Client              Server                    SIP Endpoint
       │                        │                           │
       │── CALL:{phone} ───────►│                           │
       │                        │──── INVITE + SDP ────────►│
       │                        │◄─── 180 Ringing ──────────│
       │◄─ RING_ANS:{phone} ────│                           │
       │                        │◄─── 200 OK + SDP ─────────│
       │◄─ CALL_ANS:{call_id} ──│                           │
       │                        │──── ACK ─────────────────►│
       │                        │                           │
       │═══ RTP:{audio} ═══════►│◄═══ RTP Audio ═══════════►│
       │                        │                           │
       │── BYE:{call_id} ──────►│──── BYE ─────────────────►│
       │                        │◄─── 200 OK ───────────────│
```

---

## WebSocket Protocol

### Commands (Client → Server)

| Command         | Format                          | Description            |
| --------------- | ------------------------------- | ---------------------- |
| **CALL**        | `CALL:{phone_number}`           | Initiate outgoing call |
| **RTP**         | `RTP:{call_id}##{base64_audio}` | Send audio data        |
| **BYE**         | `BYE:{call_id}`                 | Terminate call         |
| **CALL_ANS**    | `CALL_ANS:{call_id}`            | Answer incoming call   |
| **CALL_IGNORE** | `CALL_IGNORE:{call_id}`         | Ignore incoming call   |
| **HANGUP**      | `HANGUP:{call_id}`              | Hang up call           |

### Events (Server → Client)

| Event           | Format                          | Description                |
| --------------- | ------------------------------- | -------------------------- |
| **RING_ANS**    | `RING_ANS:{phone}##{call_id}`   | Incoming call notification |
| **CALL_ANS**    | `CALL_ANS:{call_id}`            | Call answered              |
| **CALL_IGNORE** | `CALL_IGNORE:{call_id}`         | Call ignored               |
| **CALL_FAILED** | `CALL_FAILED:{status} {reason}` | Call failed                |
| **BYE**         | `BYE:{call_id}`                 | Call terminated            |
| **RTP**         | `RTP:{call_id}##{base64_audio}` | Incoming audio data        |

---

## Audio Specifications

### Codec Support

| Codec    | Payload Type | Description |
| -------- | ------------ | ----------- |
| **PCMU** | 0            | G.711 μ-law |
| **PCMA** | 8            | G.711 A-law |

### Audio Format

- **Sample Rate**: 8000 Hz
- **Channels**: Mono
- **Sample Width**: 16-bit PCM
- **Frame Duration**: 20ms
- **Samples per Frame**: 160
- **Bytes per RTP Packet**: 160 bytes (encoded)

### Audio Files

Place greeting audio in:

```text
./output/transcode/greeting.wav
```

This audio plays automatically when answering incoming calls.

---

## LLM Backends

The system supports three LLM backends for AI response generation:

### API Backend

Connects to a remote LLM server via HTTP POST.

```python
from helper.llm_backends.api import APIBackend

backend = APIBackend(
    base_url="http://localhost:8000",
    api_key="your-api-key"  # optional
)
```

### Local Backend

Runs Qwen3-1.7B model locally on GPU.

```python
from helper.llm_backends.local import LocalBackend

backend = LocalBackend()
# Automatically loads model on first use
```

### OpenAI Backend

Uses OpenAI's GPT-4o-mini API.

```python
from helper.llm_backends.openai import OpenAIBackend

backend = OpenAIBackend(
    api_key="your-openai-api-key",
    model="gpt-4o-mini"
)
```

---

## Voice Activity Detection (VAD)

The system uses Silero VAD for detecting speech boundaries:

- **Purpose**: Determine when a speaker starts/stops talking
- **Threshold**: Configurable sensitivity (default: 0.5)
- **Frame Size**: 512 samples at 16kHz
- **Integration**: Built into RTPHandler for real-time processing

VAD enables:

- Efficient audio buffering (only process complete utterances)
- Natural conversation flow (wait for speaker to finish)
- Reduced processing overhead (skip silence)

---

## RTP Configuration

### Port Allocation

- **Default Range**: 31000-31010
- **Allocation**: Ports allocated in pairs (RTP + RTCP)
- **Spacing**: 4-port spacing between sessions
- **Cleanup**: Automatic release on session termination

### Packet Properties

| Property     | Value                   |
| ------------ | ----------------------- |
| Transport    | UDP                     |
| Payload      | G.711 (PCMA/PCMU)       |
| Payload Size | 160 bytes               |
| Sequence     | 16-bit with wraparound  |
| Timestamp    | 32-bit, +160 per packet |

---

## Logging

### Log Files

- **SIP Server**: `sip_server.log`
- **Call Center**: `call_center.log`

### Log Format

```text
[LEVEL] - TIMESTAMP - MESSAGE - FILE:LINE
```

### Log Levels

- `DEBUG` - Detailed debugging information
- `INFO` - General operational messages
- `WARNING` - Warning conditions
- `ERROR` - Error conditions

Configure via `LOG_LEVEL` environment variable.

---

## Network Ports

| Service      | Default Port | Protocol | Direction     |
| ------------ | ------------ | -------- | ------------- |
| SIP Receive  | 5062         | UDP      | Inbound       |
| SIP Transfer | 5060         | UDP      | Bidirectional |
| WebSocket    | 8080         | TCP      | Bidirectional |
| RTP Audio    | 31000-31010  | UDP      | Bidirectional |

---

## Troubleshooting

### Port Already in Use

```text
socket.error: [Errno 98] Address already in use
```

**Solution**: Change port in `.env` or kill the process using the port:

```bash
lsof -i :5062
kill <PID>
```

### No Audio / One-Way Audio

- Check UDP firewall rules for RTP ports
- Verify `greeting.wav` exists in `output/transcode/`
- Confirm RTP ports are correctly allocated (check logs)
- Ensure NAT traversal is configured if behind NAT

### SIP Messages Not Received

- Verify `SIP_LOCAL_IP` matches your network interface
- Check firewall allows UDP on SIP port
- Review SIP server routing rules
- Enable DEBUG logging for detailed traces

### Call Fails Immediately

- Confirm `SIP_SERVER_IP` is correct
- Check codec compatibility (PCMA/PCMU)
- Review SIP response codes in logs
- Verify SIP credentials if required

### OpenAI API Issues

**Missing API Key:**

```text
ValueError: OPENAI_API_KEY is required
```

Ensure `.env` contains valid `OPENAI_API_KEY`.

**Rate Limiting:**

- Check OpenAI account quota
- Implement retry logic or reduce request frequency

### VAD Not Detecting Speech

- Check microphone/audio input quality
- Adjust VAD sensitivity threshold
- Verify audio is 16kHz sample rate for VAD
- Review VAD logs for detection events

### AI Responses Slow

- Consider using Local backend for lower latency
- Check network connectivity to API endpoints
- Monitor GPU utilization for local models
- Reduce `CALL_CENTER_BUFFER_SIZE` for faster processing

### Call Recording Issues

- Verify `RECORDING_DIR` exists and is writable
- Check disk space availability
- Ensure proper cleanup of old recordings

---

## Development

### Code Style

- Full type hint coverage
- Pydantic models for data validation
- Match/case for message routing
- Structured logging throughout

### Adding a New LLM Backend

1. Create a new file in `helper/llm_backends/`
2. Inherit from `LLMBackend` base class
3. Implement the `generate()` method
4. Register in call_center.py

```python
from helper.llm_backends.llm_backend import LLMBackend

class MyBackend(LLMBackend):
    def generate(self, messages: list) -> str:
        # Your implementation
        pass
```

---

## API Reference

### SIPRTPSession

```python
session = SIPRTPSession(
    call_id="unique-call-id",
    remote_ip="192.168.1.100",
    remote_port=5060
)

# Start audio
session.start_rtp()

# Play audio file
session.play_audio(Path("greeting.wav"))

# Stop and cleanup
session.stop()
```

### RTPHandler

```python
handler = RTPHandler(
    local_port=31000,
    remote_ip="192.168.1.100",
    remote_port=31002
)

# Send audio
handler.send_audio(audio_bytes)

# Receive with callback
handler.set_receive_callback(on_audio_received)
handler.start_receiving()
```

### WebSocket Commands

```python
from helper.ws_command import WSCommandHelper

# Parse incoming command
cmd_type, payload = WSCommandHelper.parse("CALL:1234567890")

# Build outgoing command
message = WSCommandHelper.build("RING_ANS", "1234567890##call-123")
```

---

## Docker Deployment

### Quick Start

```bash
# 1. Configure environment
cp .env.docker.example .env
vim .env  # Set SIP_LOCAL_IP, OPENAI_API_KEY, etc.

# 2. Ensure greeting audio exists
mkdir -p output/transcode
# Copy your greeting.wav to output/transcode/

# 3. Build and run (using build script)
./scripts/docker-build.sh up

# Or manually:
docker compose up -d --build

# 4. Check status
./scripts/docker-build.sh status
```

### Build Script

A convenience script is provided at `scripts/docker-build.sh`:

```bash
./scripts/docker-build.sh [COMMAND] [OPTIONS]

Commands:
    build       Build Docker images
    up          Build and start services
    down        Stop and remove containers
    restart     Restart services
    logs        View service logs (supports -f for follow)
    status      Show container status and resource usage
    clean       Remove images and volumes
    shell       Open shell in container
    help        Show help message

Options:
    --no-cache  Build without cache
    --gpu       Enable GPU support
    -t, --tag   Image tag (default: latest)

Examples:
    ./scripts/docker-build.sh build --no-cache
    ./scripts/docker-build.sh up --gpu
    ./scripts/docker-build.sh logs -f
    ./scripts/docker-build.sh shell sip-server
```

### Architecture

The Docker deployment consists of two services:

| Service | Container | Description |
|---------|-----------|-------------|
| `sip-server` | sip-server | SIP signaling, RTP handling, WebSocket server |
| `call-center` | call-center | AI pipeline (STT → LLM → TTS) |

Both containers use `network_mode: host` for proper SIP/RTP NAT traversal.

### GPU Support

To enable NVIDIA GPU acceleration for ML models (Whisper, local LLM):

```yaml
# Uncomment in docker-compose.yml under call-center service:
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

Requirements:
- NVIDIA Docker runtime (`nvidia-container-toolkit`)
- CUDA 12.x compatible GPU

### Common Commands

```bash
# Build images
docker compose build

# Start in foreground
docker compose up

# Start in background
docker compose up -d

# View logs
docker compose logs -f sip-server
docker compose logs -f call-center

# Restart services
docker compose restart

# Stop and remove containers
docker compose down

# Stop and remove with volumes
docker compose down -v

# Rebuild and restart
docker compose up -d --build
```

### Troubleshooting Docker

**Port conflicts:**
```bash
# Check if ports are in use
ss -tulpn | grep -E '5060|5062|8080|31000'
```

**Container won't start:**
```bash
# Check logs
docker compose logs sip-server
docker compose logs call-center
```

**No audio / SIP issues:**
- Ensure `SIP_LOCAL_IP` is set to your host's actual IP (not `0.0.0.0` or `127.0.0.1`)
- Verify firewall allows UDP on SIP and RTP ports
- Check that `network_mode: host` is set in docker-compose.yml

**Model download issues:**
- First startup may take time to download Whisper models
- Check `huggingface-cache` volume for cached models

---

## Author

Code by DHT@Matthew

Version: 0.2.0
