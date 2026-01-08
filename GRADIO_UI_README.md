# Gradio Web UI for SIP Call Center

A web-based control panel for monitoring and managing the AI-powered SIP call center system.

## Features

### 1. Control Panel

- Start/Stop the call center from the web interface
- Configure WebSocket URL dynamically
- Real-time status updates

### 2. Chat (NEW!)

- **Text-based Conversation**: Chat with the AI assistant using text messages
- **Real-time Responses**: Get instant AI responses to your messages
- **Chat History**: See the full conversation in a chat bubble interface
- **Message Persistence**: Chat history is saved to transcript storage
- **Easy to Use**: Simple text input with Enter to send
- **Clear Function**: Clear chat history with one click

### 3. Dashboard

- **System Statistics**: View total calls, active calls, packets processed, and error counts
- **Active Calls**: Monitor currently active calls with duration, packet counts, and transcript counts
- Auto-refreshes every 3 seconds

### 4. Audio Chat

- **Interactive Audio Interface**: Record or upload audio directly in your browser
- **Real-time AI Conversation**: Talk to the AI assistant without making a phone call
- **Voice Response**: Receive AI responses as audio that you can play back
- **Transcript Display**: See both your input and AI response in text format
- **Multi-language Support**: Automatic language detection and response
- **Send to Active Calls**: Inject audio into active phone calls (advanced feature)

### 5. Transcripts

- View recent conversation transcripts between users and the AI assistant
- See user input, AI responses, and language detection
- Adjustable display limit (5-50 transcripts)
- Timestamps and call ID tracking
- Includes web UI audio chat and text chat transcripts

### 6. Call History

- Browse completed calls
- View call duration, start time, packet counts, and conversation exchanges
- Adjustable history limit (5-50 calls)

### 7. Configuration Viewer

- Display current system configuration
- View WebSocket, SIP, and call center settings
- Check output directories and log files

## Installation

Gradio is already installed in your virtual environment. If you need to install it separately:

```bash
pip install gradio
```

## Usage

### Starting the Web UI

1. Activate your virtual environment:

```bash
source .venv/bin/activate
```

2. Run the Gradio UI:

```bash
python gradio_ui.py
```

3. Open your browser and navigate to:

```url
http://localhost:7860
```

### Using the Interface

1. **Start Call Center**:

   - Go to the "Control" tab
   - Verify the WebSocket URL (default: ws://192.168.1.101:8080)
   - Click "Start Call Center"
   - The system will connect to the WebSocket and begin processing calls

2. **Use Text Chat** (NEW!):
   - Go to the "Chat" tab
   - Type your message in the text box
   - Press Enter or click "Send" to submit
   - The AI will respond instantly with text
   - Your conversation appears in chat bubbles (you on the right, AI on the left)
   - Click "Clear Chat" to start a new conversation

   **Text Chat Features**:
   - Fast, instant text responses
   - No audio processing needed
   - Perfect for quick questions
   - Chat history visible in transcript history
   - Easy to copy/paste messages
   - Works on any device with a browser

3. **Use Audio Chat**:

   - Go to the "Audio Chat" tab
   - Click the microphone icon to record audio, or upload an audio file
   - Click "Send Audio" to process your audio
   - The AI will transcribe your audio, generate a response, and provide both text and audio output
   - Play back the AI's audio response directly in the browser
   - Your conversation will appear in the transcript display

   **Audio Chat Features**:

   - Supports multiple languages (automatic detection)
   - Records directly in the browser (no phone call needed)
   - Accepts uploaded audio files (WAV, MP3, etc.)
   - Provides both text and audio responses
   - Saves conversations to the transcript history

   **Advanced: Send Audio to Active Call**:

   - Scroll down in the "Audio Chat" tab
   - Enter a Call ID from an active phone call
   - Record or upload audio
   - Click "Send to Call" to inject audio into the active call

4. **Monitor Calls**:

   - Switch to the "Dashboard" tab to see real-time statistics
   - View active calls with their details
   - Statistics auto-refresh every 3 seconds

5. **View Transcripts**:

   - Go to the "Transcripts" tab
   - Adjust the slider to show more or fewer transcripts
   - Click "Refresh Transcripts" to update manually
   - Includes phone calls, text chat, and audio chat transcripts

6. **Check History**:

   - Navigate to "Call History" tab
   - Review completed calls with their statistics
   - Adjust the limit slider as needed

7. **Stop Call Center**:
   - Return to the "Control" tab
   - Click "Stop Call Center"

## Architecture

The Gradio UI runs the call center in a background thread, allowing you to:

- Start and stop call processing without restarting the application
- Monitor multiple calls simultaneously
- View real-time statistics and transcripts

### Key Components

- **CallCenterState**: Global state management for calls, transcripts, and statistics
- **RTPSession**: Manages RTP packet buffering for each call
- **WebSocket Thread**: Processes messages in the background
- **Auto-refresh**: Dashboard updates automatically every 3 seconds

## Configuration

The UI uses the same configuration as the main call center application from `config.py`:

- **WS_URL**: WebSocket connection URL
- **CALL_CENTER_BUFFER_SIZE**: Number of packets to buffer before processing
- **OUTPUT_DIR**: Directory for storing audio files
- **LOG_LEVEL**: Logging verbosity

## Logging

Logs are written to:

- **gradio_ui.log**: UI-specific logs
- **Console**: Real-time log output in the terminal

## Network Access

By default, the UI is accessible on all network interfaces:

- **Local**: <http://localhost:7860>
- **Network**: <http://{your-ip}:7860>

To restrict access to localhost only, modify the `demo.launch()` call in `gradio_ui.py`:

```python
demo.launch(
    server_name="127.0.0.1",  # localhost only
    server_port=7860,
    share=False
)
```

## Differences from Original call_center.py

1. **Background Processing**: Runs in a thread, allowing UI interaction
2. **State Management**: Tracks calls, transcripts, and statistics globally
3. **Start/Stop Control**: Can start and stop processing without restarting
4. **Real-time Monitoring**: Live updates of call status and transcripts
5. **Web Interface**: Accessible from any browser

## Troubleshooting

### UI won't start

- Ensure Gradio is installed: `pip install gradio`
- Check if port 7860 is available
- Review logs in `gradio_ui.log`

### Can't connect to WebSocket

- Verify the WebSocket URL is correct
- Ensure the SIP server is running
- Check network connectivity

### No transcripts appearing

- Confirm calls are being received
- Check if STT/TTS models are loaded
- Review error counts in the Dashboard

### Statistics not updating

- Verify auto-refresh is enabled (default: every 3 seconds)
- Click manual refresh buttons if needed
- Check browser console for errors

### Audio Chat not working

- Make sure the call center is started (click "Start Call Center" first)
- Check browser permissions for microphone access
- Verify STT/TTS models are loaded (check logs)
- Ensure audio format is supported (WAV, MP3, etc.)
- Check the console output for detailed error messages

### Audio recording fails

- Grant microphone permission in your browser
- Try uploading a pre-recorded audio file instead
- Check if your browser supports the MediaRecorder API (Chrome, Firefox, Edge recommended)
- Verify audio input device is properly connected

### AI response is slow

- First request may be slow due to model loading (STT/TTS/LLM)
- Subsequent requests should be faster
- Check system resources (CPU/RAM/GPU)
- Review logs for processing time details

### Text chat not working

- Ensure call center is started (click "Start Call Center" first)
- Check if LLM model is loaded properly
- Review error messages in the chat interface
- Check logs for detailed error information

### Chat messages not appearing

- Verify the message was sent (press Enter or click Send)
- Check browser console for JavaScript errors
- Try refreshing the page
- Clear chat and try again

## Future Enhancements

Potential improvements:

- Export call transcripts to CSV/JSON
- Audio playback for recorded calls
- Real-time audio streaming
- Call analytics and metrics visualization
- Multi-language support in the UI
- User authentication
- Configurable system settings from the UI
