
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.soniox.stt import SonioxSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Simulated database for bookings
bookings_db = []


# Function handlers
async def check_availability(params: FunctionCallParams):
    """Check table availability for given date/time."""
    date = params.arguments.get("date")
    time = params.arguments.get("time")
    guests = params.arguments.get("guests")
    
    logger.info(f"Checking availability for {guests} guests on {date} at {time}")
    
    # Simulate availability check (replace with real database query)
    available = True
    
    result = {
        "available": available,
        "date": date,
        "time": time,
        "guests": guests,
        "message": f"Table for {guests} is available on {date} at {time}" if available else "No tables available"
    }
    
    await params.result_callback(result)


async def create_booking(params: FunctionCallParams):
    """Create a new reservation."""
    name = params.arguments.get("name")
    phone = params.arguments.get("phone")
    date = params.arguments.get("date")
    time = params.arguments.get("time")
    guests = params.arguments.get("guests")
    special_requests = params.arguments.get("special_requests", "None")
    
    # Generate booking ID
    booking_id = f"BOOK{len(bookings_db) + 1:04d}"
    
    # Save to database
    booking = {
        "booking_id": booking_id,
        "name": name,
        "phone": phone,
        "date": date,
        "time": time,
        "guests": guests,
        "special_requests": special_requests,
        "created_at": datetime.now().isoformat()
    }
    bookings_db.append(booking)
    
    logger.info(f"Created booking: {booking}")
    
    result = {
        "booking_id": booking_id,
        "status": "confirmed",
        "message": f"Booking confirmed for {name} on {date} at {time} for {guests} guests. Confirmation number: {booking_id}"
    }
    
    await params.result_callback(result)


async def get_restaurant_info(params: FunctionCallParams):
    """Get restaurant information."""
    info_type = params.arguments.get("info_type", "general")
    
    info = {
        "general": "The Golden Spoon Restaurant is open Tuesday to Sunday, 11 AM to 10 PM. We are closed on Mondays.",
        "hours": "Lunch: 11 AM - 3 PM, Dinner: 5 PM - 10 PM. Closed Mondays.",
        "menu": "We offer Italian and Mediterranean cuisine with vegetarian, vegan, and gluten-free options.",
        "location": "123 Main Street, Downtown. Free parking available.",
        "capacity": "We can accommodate parties up to 12 guests."
    }
    
    result = {
        "info": info.get(info_type, info["general"])
    }
    
    await params.result_callback(result)


async def run_bot(transport: BaseTransport, handle_sigint: bool):
    llm = GoogleLLMService(api_key=os.getenv("GOOGLE_API_KEY"))
    stt = SonioxSTTService(api_key=os.getenv("SONIOX_API_KEY"))

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",  # British Reading Lady
    )

    # Define function schemas
    availability_function = FunctionSchema(
        name="check_availability",
        description="Check if tables are available for a specific date, time, and party size",
        properties={
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format or natural language like 'tomorrow', 'Friday'"
            },
            "time": {
                "type": "string",
                "description": "Time in HH:MM format or natural language like '7 PM', 'evening'"
            },
            "guests": {
                "type": "integer",
                "description": "Number of guests (1-12)"
            }
        },
        required=["date", "time", "guests"]
    )

    booking_function = FunctionSchema(
        name="create_booking",
        description="Create a new table reservation after confirming availability",
        properties={
            "name": {
                "type": "string",
                "description": "Customer's full name"
            },
            "phone": {
                "type": "string",
                "description": "Customer's phone number"
            },
            "date": {
                "type": "string",
                "description": "Reservation date in YYYY-MM-DD format"
            },
            "time": {
                "type": "string",
                "description": "Reservation time in HH:MM format"
            },
            "guests": {
                "type": "integer",
                "description": "Number of guests"
            },
            "special_requests": {
                "type": "string",
                "description": "Any special requests (dietary restrictions, occasion, seating preference)"
            }
        },
        required=["name", "phone", "date", "time", "guests"]
    )

    info_function = FunctionSchema(
        name="get_restaurant_info",
        description="Get information about the restaurant",
        properties={
            "info_type": {
                "type": "string",
                "enum": ["general", "hours", "menu", "location", "capacity"],
                "description": "Type of information requested"
            }
        },
        required=["info_type"]
    )

    # Create tools schema
    tools = ToolsSchema(standard_tools=[
        availability_function,
        booking_function,
        info_function
    ])

    # Register function handlers
    llm.register_function("check_availability", check_availability)
    llm.register_function("create_booking", create_booking)
    llm.register_function("get_restaurant_info", get_restaurant_info)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a friendly restaurant booking assistant for 'The Golden Spoon Restaurant'. "
                "Your job is to help customers make reservations. "
                "Keep responses brief and conversational since they will be spoken aloud. "
                "Avoid special characters or formatting. "
                "\n\n"
                "When taking a booking, collect the following information:\n"
                "1. Customer name\n"
                "2. Phone number\n"
                "3. Number of guests (party size, max 12)\n"
                "4. Preferred date\n"
                "5. Preferred time\n"
                "6. Any special requests (dietary restrictions, occasion, seating preference)\n"
                "\n"
                "Restaurant details:\n"
                "- Open: Tuesday to Sunday, 11 AM to 10 PM\n"
                "- Closed: Mondays\n"
                "- Lunch: 11 AM - 3 PM\n"
                "- Dinner: 5 PM - 10 PM\n"
                "- Maximum party size: 12 guests\n"
                "- We offer vegetarian, vegan, and gluten-free options\n"
                "\n"
                "IMPORTANT: Always check availability BEFORE creating a booking. "
                "After collecting all information, confirm the booking details and provide the confirmation number. "
                "Be polite, helpful, and make the customer feel welcome."
            ),
        },
    ]

    context = LLMContext(messages=messages, tools=tools)
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Restaurant booking assistant ready - waiting for customer")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Call ended")
        logger.info(f"Total bookings created: {len(bookings_db)}")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=handle_sigint)

    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat Cloud."""
    transport_type, call_data = await parse_telephony_websocket(runner_args.websocket)
    logger.info(f"Auto-detected transport: {transport_type}")

    body_data = call_data.get("body", {})
    to_number = body_data.get("to_number")
    from_number = body_data.get("from_number")

    logger.info(f"Call metadata - To: {to_number}, From: {from_number}")

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data["call_id"],
        account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
    )

    transport = FastAPIWebsocketTransport(
        websocket=runner_args.websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=serializer,
        ),
    )

    handle_sigint = runner_args.handle_sigint

    await run_bot(transport, handle_sigint)