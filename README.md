# SIP Relay Server v2

A Python-based SIP relay server supporting SIP signaling, RTP media handling, and WebSocket-driven real-time control. Designed for environments requiring call routing, audio streaming, and SIP integration with external systems.

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

### Project Structure

```text
SIP_server_v2/
  receive_server.py
  main.py
  helper/
    rtp_handler.py
    sip_session.py
    sip_parsers.py
    ws_helper.py
    ws_command.py
    wav_handler.py
  model/
    sip_message.py
    rtp.py
    ws_command.py
    call_status.py
  recording/
  output/
    transcode/
      greeting.wav
```

---

## Requirements

- **Python 3.12+**
- Dependencies:

  - `pydantic >= 2.12.4`
  - `pydub >= 0.25.1`
  - `websockets >= 15.0.1`

### Installation

```bash
git clone <repository-url>
cd SIP_server_v2
uv sync
```

---

## Configuration

You can configure the server by passing settings to `RelayServer`:

```python
server = RelayServer(
    host="192.168.1.101",
    recv_port=5062,
    transf_port=5060,
    local_ip="192.168.1.101",
    sip_server_ip="192.168.1.170"
)
```

### Environment Variables (recommended)

```bash
export SIP_LOCAL_IP="192.168.1.101"
export SIP_LOCAL_PORT="5062"
export SIP_SERVER_IP="192.168.1.170"
export SIP_SERVER_PORT="5060"
```

---

## Usage

### Running the Server

```python
from receive_server import RelayServer

server = RelayServer()
server_process = server.start()

try:
    while True:
        pass
except KeyboardInterrupt:
    server.stop(server_process)
```

Or run directly:

```bash
python receive_server.py
```

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

---

## Author

Code by DHT@Matthew

---
