"""
Tool function implementations for travel booking operations.

This module contains the actual implementation of the travel booking tools.
Each function corresponds to a declared tool in declarations.py and provides
the business logic for handling various travel-related operations.
"""

import json
from datetime import datetime, timezone
import logging
import asyncio
from app.data.travel_mock_data import get_booking_details, send_eticket, validate_booking_exists

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _log_tool_event(event_type: str, tool_name: str, parameters: dict, response: dict | None = None):
    """Create and print a structured log entry for tool events."""
    log_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "log_type": "TOOL_EVENT",
        "event_subtype": event_type,
        "tool_function_name": tool_name,
        "parameters_sent": parameters,
    }
    if response is not None:
        log_payload["response_received"] = response
    print(json.dumps(log_payload))


def _build_system_message(text: str) -> dict:
    return {
        "role": "user",
        "parts": [{"text": f"[SYSTEM]: {text}"}],
    }


async def _execute_background_tool(
    queue,
    tool_name: str,
    params_sent: dict,
    build_response,
    message_template: str,
    template_kwargs: dict | None = None,
    sleep_seconds: int = 20,
):
    """Run a background tool with consistent logging and system messaging."""
    await asyncio.sleep(sleep_seconds)
    _log_tool_event("BACKGROUND_TASK_START", tool_name, params_sent)
    response = build_response()
    response_json = json.dumps(response)
    text = message_template.format(response_json=response_json, **(template_kwargs or {}))
    system_message = _build_system_message(text)
    await queue.put(system_message)
    _log_tool_event("BACKGROUND_TASK_END", tool_name, params_sent, response)


# --- Asynchronous Task Implementations ---

async def _name_correction_later(queue, correction_type: str, fn: str, ln: str):
    tool_name = "NameCorrectionAgent"
    params_sent = {"correction_type": correction_type, "fn": fn, "ln": ln}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": f"Name correction of type {correction_type} for {fn} {ln} has been processed.",
        },
        message_template="The name correction for {fn} {ln} is complete. Details: {response_json}. Please inform the user.",
        template_kwargs={"fn": fn, "ln": ln},
    )

async def _special_claim_later(queue, claim_type: str):
    tool_name = "SpecialClaimAgent"
    params_sent = {"claim_type": claim_type}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": f"Special claim of type {claim_type} has been filed.",
        },
        message_template="The special claim of type {claim_type} has been filed. Details: {response_json}. Please inform the user.",
        template_kwargs={"claim_type": claim_type},
    )

async def _enquiry_tool_later(queue):
    tool_name = "Enquiry_Tool"
    params_sent = {}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": "This is a mock response to your enquiry.",
        },
        message_template="The enquiry has been resolved. Details: {response_json}. Please inform the user.",
    )

async def _eticket_sender_later(queue, booking_id_or_pnr: str):
    tool_name = "Eticket_Sender_Agent"
    params_sent = {"booking_id_or_pnr": booking_id_or_pnr}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: send_eticket(booking_id_or_pnr),
        message_template="The e-ticket for booking {booking_id_or_pnr} has been sent. Details: {response_json}. Please inform the user.",
        template_kwargs={"booking_id_or_pnr": booking_id_or_pnr},
    )

async def _observability_agent_later(queue, operation_type: str):
    tool_name = "ObservabilityAgent"
    params_sent = {"operation_type": operation_type}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": f"Refund status for {operation_type} is being tracked.",
        },
        message_template="The refund status for {operation_type} is now available. Details: {response_json}. Please inform the user.",
        template_kwargs={"operation_type": operation_type},
    )

async def _date_change_agent_later(queue, action: str, sector_info: list):
    tool_name = "DateChangeAgent"
    params_sent = {"action": action, "sector_info": sector_info}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": f"Date change action '{action}' has been processed for the provided sectors.",
        },
        message_template="The date change action '{action}' has been processed. Details: {response_json}. Please inform the user.",
        template_kwargs={"action": action},
    )

async def _connect_to_human_tool_later(queue, reason_of_invoke: str, frustration_score: str = None):
    tool_name = "Connect_To_Human_Tool"
    params_sent = {
        "reason_of_invoke": reason_of_invoke,
        "frustration_score": frustration_score,
    }
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": "Connecting you to a human agent...",
        },
        message_template="The connection to a human agent has been initiated. Details: {response_json}. Please inform the user.",
    )

async def _booking_cancellation_agent_later(queue, booking_id_or_pnr: str, action: str, cancel_scope: str, otp: str, partial_info: list):
    tool_name = "Booking_Cancellation_Agent"
    params_sent = {
        "booking_id_or_pnr": booking_id_or_pnr,
        "action": action,
        "cancel_scope": cancel_scope,
        "otp": otp,
        "partial_info": partial_info,
    }
    def build_response():
        validation = validate_booking_exists(booking_id_or_pnr)
        if not validation["is_valid"]:
            return {"status": validation["status"], "message": validation["message"]}
        booking = validation["booking"]
        if action == "QUOTE":
            return {
                "status": "SUCCESS",
                "message": f"Cancellation quote for booking {booking_id_or_pnr}: Refund amount ₹{booking['total_cost'] * 0.8:.0f}, Penalty ₹{booking['total_cost'] * 0.2:.0f}",
                "refund_amount": booking['total_cost'] * 0.8,
                "penalty": booking['total_cost'] * 0.2,
                "currency": booking['currency'],
            }
        return {
            "status": "SUCCESS",
            "message": f"Booking {booking_id_or_pnr} has been successfully cancelled. Refund will be processed in 5-7 business days.",
            "booking_cancelled": True,
        }
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=build_response,
        message_template="The booking cancellation action '{action}' has been processed. Details: {response_json}. Please inform the user.",
        template_kwargs={"action": action},
    )

async def _webcheckin_and_boarding_pass_agent_later(queue, booking_id_or_pnr: str, journeys: list):
    tool_name = "Webcheckin_And_Boarding_Pass_Agent"
    params_sent = {"booking_id_or_pnr": booking_id_or_pnr, "journeys": journeys}
    def build_response():
        validation = validate_booking_exists(booking_id_or_pnr)
        if not validation["is_valid"]:
            return {"status": validation["status"], "message": validation["message"]}
        booking = validation["booking"]
        if booking["type"] != "flight":
            return {
                "status": "INVALID_BOOKING_TYPE",
                "message": f"Web check-in is only available for flight bookings. Booking {booking_id_or_pnr} is a {booking['type']} booking.",
            }
        return {
            "status": "SUCCESS",
            "message": f"Web check-in completed for booking {booking_id_or_pnr}. Boarding passes have been sent to your registered email and mobile number.",
            "booking_type": booking["type"],
            "journeys_processed": len(journeys),
        }
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=build_response,
        message_template="The web check-in and boarding pass request has been processed. Details: {response_json}. Please inform the user.",
    )

async def _take_a_nap_later(queue):
    tool_name = "take_a_nap"
    params_sent = {}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: {
            "status": "SUCCESS",
            "message": "I have slept really good, thanks for waking me up! 😴💤",
            "sleep_duration": "30 seconds",
            "wake_up_time": datetime.now(timezone.utc).isoformat(),
        },
        message_template="The nap is over. Details: {response_json}. Please inform the user.",
        sleep_seconds=30,
    )

async def _fetch_and_send_details_later(queue, booking_id_or_pnr: str):
    """Simulates a long-running task to fetch booking details and sends them back to the session."""
    tool_name = "Flight_Booking_Details_Agent"
    params_sent = {"booking_id_or_pnr": booking_id_or_pnr}
    await _execute_background_tool(
        queue,
        tool_name,
        params_sent,
        build_response=lambda: get_booking_details(booking_id_or_pnr),
        message_template="The booking details for {booking_id_or_pnr} are now available. Here they are: {response_json}. Please present this to the user.",
        template_kwargs={"booking_id_or_pnr": booking_id_or_pnr},
    )


# --- Tool Function Implementations (Synchronous Wrappers) ---

def _pending(message: str) -> dict:
    return {"status": "PENDING", "message": message}


def _start_background(task_coro, pending_message: str) -> dict:
    asyncio.create_task(task_coro)
    return _pending(pending_message)


def NameCorrectionAgent(session, queue, correction_type: str, fn: str, ln: str) -> dict:
    return _start_background(
        _name_correction_later(queue, correction_type, fn, ln),
        "Processing name correction...",
    )

def SpecialClaimAgent(session, queue, claim_type: str) -> dict:
    return _start_background(
        _special_claim_later(queue, claim_type),
        "Filing special claim...",
    )

def Enquiry_Tool(session, queue) -> dict:
    return _start_background(
        _enquiry_tool_later(queue),
        "Looking up information for your enquiry...",
    )

def Eticket_Sender_Agent(session, queue, booking_id_or_pnr: str) -> dict:
    return _start_background(
        _eticket_sender_later(queue, booking_id_or_pnr),
        f"Sending e-ticket for booking {booking_id_or_pnr}...",
    )

def ObservabilityAgent(session, queue, operation_type: str) -> dict:
    return _start_background(
        _observability_agent_later(queue, operation_type),
        f"Tracking refund status for {operation_type}...",
    )

def DateChangeAgent(session, queue, action: str, sector_info: list) -> dict:
    return _start_background(
        _date_change_agent_later(queue, action, sector_info),
        f"Processing date change action '{action}'...",
    )

def Connect_To_Human_Tool(session, queue, reason_of_invoke: str, frustration_score: str = None) -> dict:
    return _start_background(
        _connect_to_human_tool_later(queue, reason_of_invoke, frustration_score),
        "Connecting you to a human agent...",
    )

def Booking_Cancellation_Agent(session, queue, booking_id_or_pnr: str, action: str, cancel_scope: str = "NOT_MENTIONED", otp: str = "", partial_info: list = None) -> dict:
    return _start_background(
        _booking_cancellation_agent_later(queue, booking_id_or_pnr, action, cancel_scope, otp, partial_info),
        f"Processing cancellation action '{action}' for booking {booking_id_or_pnr}...",
    )

def Flight_Booking_Details_Agent(session, queue, booking_id_or_pnr: str) -> dict:
    """
    Starts a background task to fetch booking details and immediately returns a pending message.
    """
    tool_name = "Flight_Booking_Details_Agent"
    params_sent = {"booking_id_or_pnr": booking_id_or_pnr}
    _log_tool_event("INVOCATION_START", tool_name, params_sent)

    # Start the background task and return a pending response
    asyncio.create_task(_fetch_and_send_details_later(queue, booking_id_or_pnr))
    response = _pending(
        f"I'm fetching the details for booking {booking_id_or_pnr}. It might take a moment. You can continue our conversation in the meantime."
    )
    _log_tool_event("INVOCATION_PENDING", tool_name, params_sent, response)
    return response

def Webcheckin_And_Boarding_Pass_Agent(session, queue, booking_id_or_pnr: str, journeys: list) -> dict:
    return _start_background(
        _webcheckin_and_boarding_pass_agent_later(queue, booking_id_or_pnr, journeys),
        f"Processing web check-in for booking {booking_id_or_pnr}...",
    )

def take_a_nap(session, queue) -> dict:
    return _start_background(
        _take_a_nap_later(queue),
        "I'm going to take a short nap... I'll be back in 30 seconds.",
    )