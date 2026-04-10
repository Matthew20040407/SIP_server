# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python-based SIP relay server with AI integration for intelligent voice interactions. Two cooperating processes handle SIP signaling/RTP media (`receive_server.py`) and the AI pipeline (`call_center.py`).

## Commands

### Setup

```bash
cp .env.docker.example .env  # then configure SIP_LOCAL_IP, OPENAI_API_KEY, etc.
uv sync --frozen              # install dependencies
```

### Running

```bash
./run.sh                      # starts both processes in background (local)
uv run receive_server.py      # SIP server only
uv run call_center.py         # AI pipeline only

# Docker
./scripts/docker-build.sh build [--gpu]
./scripts/docker-build.sh up [--gpu]
./scripts/docker-build.sh logs
./scripts/docker-build.sh down
```

### Testing

```bash
uv run test.py    # minimal STT/TTS smoke test via custom_sts_handler
```

### Linting

Ruff is configured in `.trunk/configs/ruff.toml` with import sorting (`extend-select = ["I"]`).

## Architecture

### Two-Process Design

**`receive_server.py` — SIP Relay + WebSocket Server**

- `RelayServer` listens on `SIP_LOCAL_IP:SIP_LOCAL_PORT` (UDP, default 5062)
- Routes INVITE → allocates RTP ports, builds SDP answer → 200 OK
- On ACK → starts RTP session and plays `greeting.wav`
- On BYE → saves recording, cleans up session
- Runs a WebSocket server (default port 8080) as the control channel to `call_center.py`
- Session state lives in a `call_id → SIPRTPSession` dict

**`call_center.py` — AI Pipeline**

- Connects to `receive_server`'s WebSocket as a client
- Receives raw RTP audio hex packets, buffers them with VAD (webrtcvad)
- When speech ends: hex → WAV → STT (Faster-Whisper) → LLM → TTS (Qwen3-TTS) → base64
- Sends synthesized audio back over WebSocket as an RTP command
- Maintains per-call conversation history (capped at 10 turns)
- Exposes a FastAPI chat-monitor UI on port 8088

### WebSocket Command Protocol (`model/ws_command.py`)

`CommandType` values: `CALL`, `RTP`, `BYE`, `CALL_ANS`, `RING_ANS`  
Audio is transmitted as base64-encoded bytes inside `WebSocketCommand` messages.

### Helper Modules (`helper/`)

| File                    | Key Classes                              | Purpose                                                                    |
| ----------------------- | ---------------------------------------- | -------------------------------------------------------------------------- |
| `sip_session.py`        | `SIPRTPSession`                          | RTP port allocation (4-port spacing), SDP generation, call recording       |
| `rtp_handler.py`        | `RTPSender`, `RTPReceiver`, `VADHandler` | G.711 audio I/O, 20ms packets @ 8 kHz, Silero VAD state machine            |
| `sip_parsers.py`        | `SipMessageParser`                       | SIP/SDP parsing → Pydantic models                                          |
| `ws_helper.py`          | `WebsocketServer`                        | Async WebSocket with send/recv queues                                      |
| `custom_sts_handler.py` | `Speech2Text`, `Text2Speech`             | Faster-Whisper + Qwen3-TTS wrappers                                        |
| `llm_backends/`         | `LLMBackend` + subclasses                | Pluggable LLM: `api.py` (remote HTTP), `local.py` (Qwen3 GPU), `openai.py` |
| `PROMPT.py`             | —                                        | System prompt for the AI assistant (Chinese, 极度简洁 style)               |

### Configuration (`config.py`)

Pydantic `BaseSettings` with env-var mapping. Key settings groups: `SIPConfig`, `WebSocketConfig`, `RTPConfig`, `LoggingConfig`, `FileConfig`, `OpenaiConfig`, `LLMServerConfig`, `CacheServerConfig`.

### Audio Specs

- Codec: PCMU (G.711 μ-law, PT=0) or PCMA (A-law, PT=8)
- 8000 Hz mono, 16-bit PCM, 20ms frames (160 samples/160 bytes per RTP packet)
- RTP ports: 31000–31010 (default), allocated in 4-port groups

### Ports

| Service           | Port        | Protocol |
| ----------------- | ----------- | -------- |
| SIP listen        | 5062        | UDP      |
| SIP relay         | 5060        | UDP      |
| WebSocket control | 8080        | TCP      |
| RTP audio         | 31000–31010 | UDP      |
| Chat monitor UI   | 8088        | TCP      |

### Deployment Notes

- Docker uses `network_mode: host` — required for SIP/RTP NAT traversal
- NVIDIA GPU (CUDA 12.6.3) is used for Whisper and Qwen3-TTS inference
- Voices directory (`./voices/`) and `greeting.wav` must exist before starting
- Logs: `sip_server.log` (receive_server) and `call_center.log` (AI pipeline)
