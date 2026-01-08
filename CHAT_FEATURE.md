# Text Chat Feature

## Overview

The new **Chat** tab provides a text-based interface to interact with the AI assistant in real-time. This is the fastest and easiest way to test and interact with your AI system.

## Key Features

### 💬 Chat Interface

- Clean, modern chat bubble design
- User messages on the right (blue)
- AI responses on the left (gray)
- Scrollable conversation history
- Real-time message display

### ⚡ Fast & Easy

- Type and press Enter to send
- Instant AI responses (no audio processing)
- No microphone needed
- Works on all devices and browsers
- Perfect for quick questions

### 💾 Persistent

- Chat history saved during session
- Messages stored in transcript history
- Can clear chat to start fresh
- Integrated with system transcripts

## How to Use

### Basic Usage

1. **Start the Call Center**

   - Go to Control tab
   - Click "Start Call Center"

2. **Open Chat Tab**

   - Click on the "Chat" tab

3. **Send a Message**

   - Type your message in the text box
   - Press Enter or click "Send"

4. **Get Response**

   - AI responds immediately
   - Message appears in chat bubbles

5. **Continue Conversation**

   - Keep typing and sending messages
   - Full conversation context maintained

6. **Clear Chat** (Optional)
   - Click "Clear Chat" button
   - Starts a fresh conversation

### Keyboard Shortcuts

- **Enter**: Send message (when in text box)
- **Shift+Enter**: New line in message

## Use Cases

### 1. Quick Testing

Test AI responses without audio processing overhead:

```text
You: What services do you offer?
AI: [Instant response based on system prompt]
```

### 2. Development & Debugging

Rapid iteration during development:

- Test prompt changes quickly
- Verify response logic
- Check language understanding
- Debug conversation flows

### 3. Demonstrations

Show AI capabilities without SIP setup:

- No phone infrastructure needed
- Easy to present to stakeholders
- Clear visual interface
- Fast response times

### 4. Training & Documentation

Document AI behavior:

- Easy to copy conversations
- Screenshot friendly
- Clear message history
- Good for creating examples

### 5. Accessibility

More accessible than audio:

- No microphone required
- Works in quiet environments
- Easy to review responses
- Can use assistive technologies

## Technical Details

### Message Flow

```text
User Input → LLM Processing → AI Response → Display
              ↓
         Transcript Storage
```

### Implementation

- **Function**: `process_text_chat(message, history)`
- **Storage**: Messages stored with call_id "text-chat"
- **Language**: Currently defaults to English
- **Context**: Full conversation history maintained
- **Clear**: `clear_chat()` function resets history

### Data Structure

Each chat message is stored as:

```python
{
    'call_id': 'text-chat',
    'timestamp': datetime.now(),
    'user': message,
    'assistant': response,
    'language': 'en'
}
```

### Performance

- **Response Time**: 0.5-2 seconds (LLM only)
- **No Audio Processing**: Faster than audio chat
- **Context Maintained**: Full conversation in memory
- **Scalable**: Handles long conversations

## Advantages Over Audio Chat

| Feature       | Text Chat         | Audio Chat             |
| ------------- | ----------------- | ---------------------- |
| Speed         | ⚡ Instant        | 🐢 2-10 seconds        |
| Hardware      | ⌨️ Keyboard only  | 🎤 Microphone required |
| Processing    | 📝 Text only      | 🔊 STT + TTS           |
| Environment   | 🤫 Works anywhere | 🔊 Needs quiet space   |
| Copy/Paste    | ✅ Easy           | ❌ Not possible        |
| Accessibility | ✅ Screen readers | ⚠️ Limited             |

## Integration

### With Other Features

#### Transcripts Tab

- Text chat messages appear in transcripts
- Labeled with call_id "text-chat"
- Timestamps for each message
- Language marked as "en"

#### Dashboard

- Does NOT count as a phone call
- Does NOT increment call statistics
- System must be running (started)

#### Audio Chat

- Completely separate from audio chat
- Can use both in same session
- Each maintains own history

## Error Handling

### Common Errors

#### Call center is not running

- Start the call center first
- Goes to Control tab
- Click "Start Call Center"

#### No response

- Check LLM model is loaded
- Review logs for errors
- Verify system has started properly

#### Message not sending

- Ensure text box has content
- Try clicking Send button
- Check browser console for errors

## Best Practices

### For Users

✅ **DO**:

- Start call center before chatting
- Keep messages clear and concise
- Use chat for quick questions
- Clear chat when starting new topic

❌ **DON'T**:

- Send empty messages
- Expect audio responses (text only)
- Assume context from audio chats
- Forget to start call center first

### For Developers

✅ **DO**:

- Use for rapid testing
- Test prompt changes
- Verify LLM responses
- Debug conversation logic

❌ **DON'T**:

- Rely on for audio testing
- Assume multilingual (currently EN only)
- Forget it uses system LLM
- Skip error logging

## Future Enhancements

Potential improvements:

- **Language Detection**: Auto-detect message language
- **Export**: Export conversation to text/JSON
- **Search**: Search within chat history
- **Markdown**: Rich text formatting in responses
- **Code Highlighting**: Syntax highlighting for code
- **Multi-turn**: Better context handling
- **Streaming**: Stream AI responses word-by-word
- **Attachments**: Send images/files
- **Voice Option**: Click-to-voice for accessibility

## Comparison: Chat Types

### Text Chat (This Feature)

- **Input**: Text typed by user
- **Output**: Text from AI
- **Speed**: Fastest (0.5-2s)
- **Best For**: Quick questions, testing, development

#### Audio Chat Input

- **Input**: Voice recorded/uploaded
- **Output**: Text + Audio playback
- **Speed**: Medium (2-10s)
- **Best For**: Voice testing, demos, natural interaction

### Phone Calls (SIP)

- **Input**: Phone line audio
- **Output**: Phone line audio
- **Speed**: Real-time streaming
- **Best For**: Production use, real phone calls

## Troubleshooting

### Chat not responding

1. Check call center is started
2. Look for error messages in chat
3. Review browser console (F12)
4. Check gradio_ui.log file
5. Verify LLM model loaded

### Messages disappear

- Browser refresh clears chat
- Chat history not persistent across restarts
- Use "Clear Chat" intentionally only

### Slow responses

- First message may be slower (model loading)
- Check system resources
- Review LLM configuration
- Check logs for processing time

## Code Example

### Using the Chat Function

```python
def process_text_chat(message: str, history: list):
    """Process text chat message and get AI response"""
    if not message or not message.strip():
        return history, ""

    # Add user message
    history.append((message, None))

    # Get LLM response
    llm_response = llm_handler.generate_response(message, "en")

    # Update with AI response
    history[-1] = (message, llm_response)

    # Store in transcripts
    state.transcripts.append({
        'call_id': 'text-chat',
        'timestamp': datetime.now(),
        'user': message,
        'assistant': llm_response,
        'language': 'en'
    })

    return history, ""
```

## Summary

The Text Chat feature provides the **fastest and easiest** way to interact with your AI assistant:

✅ No audio processing delays
✅ No microphone required
✅ Works on all devices
✅ Perfect for development and testing
✅ Clean, modern chat interface
✅ Integrated with transcripts

Start chatting now by clicking the **Chat** tab!
