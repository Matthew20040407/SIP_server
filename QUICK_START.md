# Quick Start Guide - Gradio Web UI

## Launch the Web UI

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run the web UI
python gradio_ui.py

# 3. Open browser to:
# http://192.168.1.101:7860
```

## Main Features at a Glance

### 🎮 Control Tab

#### Start/Stop the call center

- Enter WebSocket URL
- Click "Start Call Center"
- Monitor status

### 💬 Chat Tab (NEW!)

#### Text chat with AI assistant

1. Type your message
2. Press Enter or click "Send"
3. Get instant text response
4. Continue conversation
5. Clear chat to start over

**Perfect for:**

- Quick questions
- Fast text interactions
- Testing AI responses
- No audio needed
- Works on any device

### 🎤 Audio Chat Tab

#### Talk to AI without phone calls

1. Click microphone or upload audio
2. Record your message
3. Click "Send Audio"
4. Get AI response as text + audio
5. Play back the response

**Perfect for:**

- Testing AI responses
- Demos without SIP infrastructure
- Quick conversations with AI
- Multilingual testing

### 📊 Dashboard Tab

#### Real-time monitoring

- System statistics (auto-refresh every 3s)
- Active calls list
- Packet counts
- Error tracking

### 💬 Transcripts Tab

#### View conversation history

- Recent transcripts from calls
- Web UI audio chat transcripts
- Language detection
- Timestamps

### 📞 Call History Tab

#### Browse completed calls

- Call duration
- Packet statistics
- Conversation exchanges

### ⚙️ Configuration Tab

#### View system settings

- WebSocket configuration
- SIP settings
- Output directories

## Typical Workflow

### For Quick Text Chat (Fastest)

```text
1. Start Call Center (Control tab)
2. Go to Chat tab
3. Type and send messages
4. Get instant AI responses
5. Continue conversation
```

### For Testing AI with Audio (No Phone)

```text
1. Start Call Center (Control tab)
2. Go to Audio Chat tab
3. Record/upload audio
4. Send and receive response
5. Repeat as needed
```

### For Monitoring Phone Calls

```text
1. Start Call Center (Control tab)
2. Phone calls come in automatically
3. Monitor in Dashboard tab
4. View transcripts in Transcripts tab
5. Check history in Call History tab
```

## Browser Support

| Browser | Recording    | Upload | Recommended |
| ------- | ------------ | ------ | ----------- |
| Chrome  | ✅ Excellent | ✅ Yes | ⭐ Best     |
| Firefox | ✅ Good      | ✅ Yes | ⭐ Good     |
| Edge    | ✅ Good      | ✅ Yes | ⭐ Good     |
| Safari  | ⚠️ Limited   | ✅ Yes | Use upload  |

## Requirements

- Call center must be **started** to use Audio Chat
- Microphone permission required for recording
- Port 7860 must be available
- STT/TTS/LLM models must be configured

## Keyboard Shortcuts

- **Ctrl+R**: Refresh page
- **Tab**: Navigate between fields
- **Enter**: Submit in text fields
- **Space**: Start/stop recording (when focused)

## Common Issues

### "Call center is not running"

→ Go to Control tab and click "Start Call Center"

### Can't record audio

→ Check browser microphone permissions
→ Try uploading a file instead

### Slow response

→ First request loads models (10-15s)
→ Subsequent requests faster (2-5s)

### No audio playback

→ Check browser audio settings
→ Verify speakers/headphones connected
→ Try downloading the audio file

## Tips

✅ **Start the call center first** before using any features
✅ **Grant microphone permission** when prompted
✅ **Speak clearly** for best transcription
✅ **Keep recordings short** (under 30 seconds)
✅ **Check logs** if something doesn't work
✅ **Refresh the page** if UI becomes unresponsive

## File Locations

- **Logs**: `gradio_ui.log`
- **Audio Responses**: `./output/response/web_ui_*.wav`
- **Configuration**: `config.py`, `.env`

## Next Steps

📖 Read [GRADIO_UI_README.md](GRADIO_UI_README.md) for detailed documentation
📖 Read [AUDIO_CHAT_GUIDE.md](AUDIO_CHAT_GUIDE.md) for audio chat details
📖 Check logs for troubleshooting

## Support

Found an issue? Check the logs:

```bash
tail -f gradio_ui.log
```

Need help? Review the documentation or check the code comments.
