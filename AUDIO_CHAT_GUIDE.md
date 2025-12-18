# Audio Chat Feature Guide

## Overview

The Audio Chat feature allows you to interact with the AI assistant directly through the web interface without making a phone call. You can record audio using your microphone or upload audio files, and receive both text and audio responses.

## How It Works

```text
User Audio Input → Speech-to-Text → LLM Processing → Text-to-Speech → Audio Response
                                    ↓
                            Transcript Storage
```

## Step-by-Step Guide

### 1. Start the Call Center

Before using Audio Chat, you must start the call center:

1. Navigate to the **Control** tab
2. Verify the WebSocket URL (or leave default)
3. Click **Start Call Center**
4. Wait for "Call center started" message

### 2. Use Audio Chat

1. Navigate to the **Audio Chat** tab
2. You'll see two options:
   - **Microphone**: Record live audio in your browser
   - **Upload**: Upload a pre-recorded audio file

#### Option A: Record Audio

1. Click the **microphone icon** in the "Record or Upload Audio" section
2. Grant microphone permission when prompted by your browser
3. Click **Start Recording**
4. Speak your message clearly
5. Click **Stop Recording** when done
6. Click **Send Audio** button

#### Option B: Upload Audio

1. Click the **upload icon** in the "Record or Upload Audio" section
2. Select an audio file from your computer (WAV, MP3, OGG, etc.)
3. Click **Send Audio** button

### 3. Receive AI Response

After clicking "Send Audio", the system will:

1. **Transcribe** your audio (visible in "Conversation" box)
2. **Process** with the LLM to generate a response
3. **Synthesize** speech from the AI response
4. **Display** both text and audio response

You'll see:

- **Conversation**: Your transcribed input and the exchange
- **AI Response Text**: The text of what the AI said
- **AI Response Audio**: Audio player to hear the AI's voice

### 4. Continue the Conversation

Simply record or upload another audio message and click "Send Audio" again. Each interaction is saved to the transcript history.

## Advanced: Send Audio to Active Call

This feature allows you to inject pre-recorded audio directly into an active phone call.

### Use Case

- Testing specific audio scenarios
- Sending pre-recorded messages during a call
- Debugging call flows

### How to Use

1. In the **Dashboard** tab, note the **Call ID** of an active call
2. Return to the **Audio Chat** tab
3. Scroll down to "Send Audio to Active Call"
4. Enter the **Call ID**
5. Record or upload audio
6. Click **Send to Call**

**Note**: This feature requires the WebSocket connection to be active and the call to be in progress.

## Supported Audio Formats

### Recording

- Browser-recorded audio is typically in WebM or WAV format
- Automatically handled by Gradio

### Upload

- WAV (recommended)
- MP3
- OGG
- FLAC
- M4A

## Language Support

The system automatically detects the language of your input and responds in the same language. Supported languages depend on your STT/TTS models, but typically include:

- English (en)
- Chinese (zh)
- Spanish (es)
- French (fr)
- And many others

## Tips for Best Results

### Audio Quality

- Speak clearly and at a moderate pace
- Minimize background noise
- Use a good quality microphone
- Keep recordings under 30 seconds for better processing

### Browser Recommendations

- **Chrome**: Best compatibility
- **Firefox**: Good support
- **Edge**: Good support
- **Safari**: Limited MediaRecorder support (use file upload instead)

### Troubleshooting

#### "Please start call center first"

- Go to Control tab and click "Start Call Center"
- Wait for confirmation message

#### "Could not transcribe audio"

- Check audio quality and volume
- Ensure audio contains speech
- Try speaking more clearly
- Check STT model is loaded (see logs)

#### No audio response

- Check browser audio settings
- Verify TTS model is loaded
- Look for errors in the console/logs
- Try refreshing the page

#### Microphone not working

- Check browser permissions (usually in address bar)
- Verify microphone is connected and working
- Try a different browser
- Use file upload as alternative

## Technical Details

### Processing Pipeline

1. **Audio Input**: Captured from browser or uploaded file
2. **File Storage**: Temporarily saved to process
3. **STT**: Speech-to-Text using configured model
4. **LLM**: Language model generates response based on prompt
5. **TTS**: Text-to-Speech creates audio response
6. **Output**: Both text and audio returned to browser
7. **Storage**: Transcript saved with 'web-ui' call ID

### Response Time

- **First Request**: 5-15 seconds (model loading)
- **Subsequent Requests**: 2-5 seconds
- **Depends on**:
  - Audio length
  - System resources
  - Model size
  - Network latency

### Resource Usage

The Audio Chat feature uses the same AI models as phone calls:

- **Speech2Text**: Transcription model
- **LLM**: Language model for responses
- **Text2Speech**: Voice synthesis model

All models remain loaded in memory after first use, making subsequent requests faster.

## Privacy & Data

- Audio files are stored in `./output/response/` directory
- Files are prefixed with `web_ui_` for easy identification
- Transcripts are stored in memory (not persistent across restarts)
- No audio is sent to external services (all processing is local)

## Integration with Call Center

Web UI audio chats are integrated into the system:

- Appear in the **Transcripts** tab with call ID "web-ui"
- Count towards total transcripts
- Do NOT count as phone calls in statistics
- Stored separately from SIP call data

## Example Use Cases

### 1. Testing AI Responses

Record various questions to test how the AI responds without making phone calls.

### 2. Voice Interface

Use as a voice-controlled interface to interact with the AI system.

### 3. Demo & Presentation

Demonstrate AI capabilities to stakeholders without SIP infrastructure.

### 4. Development & Debugging

Test STT/TTS/LLM changes quickly without phone integration.

### 5. Multilingual Testing

Test language detection and multilingual responses easily.

## Comparison: Audio Chat vs Phone Calls

| Feature            | Audio Chat                  | Phone Calls      |
| ------------------ | --------------------------- | ---------------- |
| Requires SIP       | No                          | Yes              |
| Requires WebSocket | Only if call center running | Yes              |
| Real-time          | No (batch processing)       | Yes (streaming)  |
| Audio Input        | Browser/File                | Phone line       |
| Audio Output       | Browser playback            | Phone line       |
| Call ID            | "web-ui"                    | Actual call ID   |
| Statistics         | Transcripts only            | Full call stats  |
| Use Case           | Testing, demo, dev          | Production calls |

## Future Enhancements

Potential improvements for Audio Chat:

- Conversation history per session
- Export audio conversations
- Real-time streaming (vs batch)
- Multiple conversation threads
- Audio effects/filters
- Custom voice selection
- Conversation export/sharing
