
# Restaurant Booking Voice AI Agent

A production-ready voice AI agent built with Pipecat for handling restaurant reservations over phone calls. The agent can check table availability, create bookings, and provide restaurant information through natural conversation.

## Features

- **Intelligent Booking Management**: Collects customer details (name, phone, party size, date, time)
- **Real-time Availability Checking**: Validates table availability before confirming reservations
- **Restaurant Information**: Answers questions about hours, menu, location, and capacity
- **Function Calling**: Uses LLM function calling to interact with booking database
- **Natural Conversations**: Powered by Google Gemini for human-like interactions
- **High-Quality Voice**: Cartesia TTS for natural-sounding speech
- **Accurate Transcription**: Soniox STT for reliable speech recognition

## Architecture

The agent uses a cascaded pipeline approach:

```
Phone Call → Twilio → WebSocket → STT → Context → LLM → TTS → Audio Output
                                           ↓
                                    Function Calls
                                    (Availability, Booking, Info)
```

## Prerequisites

### Required Services

1. **Twilio Account**
   - Account SID and Auth Token
   - Phone number with voice capabilities
   - Enable international calling if needed

2. **AI Service API Keys**
   - Google API key (for Gemini LLM)
   - Soniox API key (for speech-to-text)
   - Cartesia API key (for text-to-speech)

3. **Development Tools**
   - Python 3.10+
   - `uv` package manager
   - ngrok (for local development)

## Installation

1. Clone the repository and navigate to the project directory:


2. Install dependencies using uv:

```bash
uv sync
```

3. Set up environment variables:

```bash
cp env.example .env
```

Edit `.env` with your credentials:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
LOCAL_SERVER_URL=https://your-ngrok-url.ngrok.io

# AI Service Keys
GOOGLE_API_KEY=your_google_api_key
SONIOX_API_KEY=your_soniox_api_key
CARTESIA_API_KEY=your_cartesia_api_key
```

## Local Development

### 1. Start the Server

```bash
uv run server.py
```

The server will start on port 7860.

### 2. Expose with ngrok

In a new terminal:

```bash
ngrok http 7860
```

Copy the ngrok URL (e.g., `https://abc123.ngrok.io`) and update `LOCAL_SERVER_URL` in your `.env` file.

### 3. Make a Test Call

Use curl or Postman to initiate an outbound call:

```bash
curl -X POST https://your-ngrok-url.ngrok.io/dialout \
  -H "Content-Type: application/json" \
  -d '{
    "to_number": "+1234567890",
    "from_number": "+your_twilio_number"
  }'
```

**Important Notes:**
- `from_number` must be a Twilio number you own
- `to_number` must be in E.164 format (+country_code + number)
- Enable international calling in Twilio Console if calling outside US/Canada

## How It Works

### Call Flow

1. **Initiation**: POST request to `/dialout` triggers Twilio API call
2. **TwiML Generation**: Twilio requests TwiML from `/twiml` endpoint
3. **WebSocket Connection**: TwiML instructs Twilio to connect to `/ws` endpoint
4. **Conversation**: Bot waits for user to speak first, then responds naturally
5. **Function Execution**: Bot calls functions to check availability and create bookings

### Available Functions

#### 1. Check Availability
Validates table availability for requested date/time/party size.

```python
check_availability(date, time, guests)
```

#### 2. Create Booking
Creates a new reservation after availability is confirmed.

```python
create_booking(name, phone, date, time, guests, special_requests)
```

#### 3. Get Restaurant Info
Provides information about hours, menu, location, or capacity.

```python
get_restaurant_info(info_type)
```

### Restaurant Configuration

Current settings (modify in `bot.py`):

- **Hours**: Tuesday-Sunday, 11 AM - 10 PM (Closed Mondays)
- **Lunch**: 11 AM - 3 PM
- **Dinner**: 5 PM - 10 PM
- **Max Party Size**: 12 guests
- **Dietary Options**: Vegetarian, vegan, gluten-free

## Customization

### Modify Restaurant Details

Edit the system prompt in `bot.py`:

```python
messages = [
    {
        "role": "system",
        "content": (
            "You are a friendly restaurant booking assistant for 'Your Restaurant Name'. "
            # ... customize instructions ...
        ),
    },
]
```



### Customize Voice

Change the Cartesia voice in `bot.py`:

```python
tts = CartesiaTTSService(
    api_key=os.getenv("CARTESIA_API_KEY"),
    voice_id="your-preferred-voice-id",  # Browse voices at cartesia.ai
)
```



## Troubleshooting

### Call Connects But No Audio
- Check that ngrok URL is correctly set in `.env`
- Verify Twilio credentials are correct
- Ensure all API keys are valid

### Bot Doesn't Respond
- Confirm user speaks first (bot waits for "Hello")
- Check logs for API errors
- Verify LLM and TTS services are working

### International Calls Fail
- Enable geo permissions in Twilio Console
- Check account balance for international calling
- Verify phone number format (E.164)

### Function Calls Not Working
- Check function registration in `bot.py`
- Verify function schemas match LLM expectations
- Review logs for function execution errors

## Project Structure

```
outbound/
├── bot.py              # Main bot logic with functions
├── server.py           # FastAPI server and endpoints
├── server_utils.py     # Twilio integration utilities
├── .env               # Environment variables (create from .env.example)
└── README.md          # This file
```



## Support

For issues or questions:
- Check Pipecat documentation: https://docs.pipecat.ai
- Review Twilio docs: https://www.twilio.com/docs
- Open an issue in the repository

---

Built with [Pipecat](https://pipecat.ai) - The open-source framework for voice AI agents.
