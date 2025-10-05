import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from app.tools import AllTools


# A helper function to print results nicely
def print_result(tool_name, result):
    print(f"--- Testing {tool_name} ---")
    # A simple check for a success-like message
    if result.get("status", "").upper() == "SUCCESS":
        print("✅ SUCCESS")
    elif result.get("status", "").upper() == "PENDING":
        print("⏳ PENDING (background task started)")
    else:
        # Fallback for tools that might not have a status, or have a different one
        print(f"🔵 STATUS: {result.get('status', 'N/A')}")

    print(json.dumps(result, indent=2))
    print("-" * (len(tool_name) + 12))
    print()


async def main():
    """Runs test calls for all available tool functions."""
    print("🚀 Starting Tool Call Verification Script 🚀\n")

    # Create mock session and queue
    mock_session = MagicMock()
    mock_queue = AsyncMock()

    # Create a mapping of tool names to their implementations
    tool_map = {
        tool.name: tool.implementation(mock_session, mock_queue)
        for tool in AllTools.get_all()
    }

    # 1. Test Flight_Booking_Details_Agent
    flight_details_func = tool_map["Flight_Booking_Details_Agent"]
    booking_details = flight_details_func(booking_id_or_pnr="BK001")
    print_result("Flight_Booking_Details_Agent", booking_details)

    # 2. Test Booking_Cancellation_Agent
    cancel_func = tool_map["Booking_Cancellation_Agent"]
    cancel_quote = cancel_func(booking_id_or_pnr="BK001", action="QUOTE")
    print_result("Booking_Cancellation_Agent (QUOTE)", cancel_quote)

    # 3. Test Eticket_Sender_Agent
    eticket_func = tool_map["Eticket_Sender_Agent"]
    eticket = eticket_func(booking_id_or_pnr="BK002")
    print_result("Eticket_Sender_Agent", eticket)

    # 4. Test Webcheckin_And_Boarding_Pass_Agent
    webcheckin_func = tool_map["Webcheckin_And_Boarding_Pass_Agent"]
    webcheckin = webcheckin_func(
        booking_id_or_pnr="BK001",
        journeys=[{"origin": "BOM", "destination": "DXB", "isAllPax": "true"}],
    )
    print_result("Webcheckin_And_Boarding_Pass_Agent", webcheckin)

    # 5. Test NameCorrectionAgent
    name_correction_func = tool_map["NameCorrectionAgent"]
    name_correction = name_correction_func(
        correction_type="NAME_CORRECTION", fn="Shubham", ln="Kumar"
    )
    print_result("NameCorrectionAgent", name_correction)

    # 6. Test DateChangeAgent
    date_change_func = tool_map["DateChangeAgent"]
    date_change = date_change_func(
        action="QUOTE",
        sector_info=[{"origin": "BOM", "destination": "DXB", "newDate": "2025-08-20"}],
    )
    print_result("DateChangeAgent", date_change)

    # 7. Test SpecialClaimAgent
    special_claim_func = tool_map["SpecialClaimAgent"]
    special_claim = special_claim_func(claim_type="MEDICAL_EMERGENCY")
    print_result("SpecialClaimAgent", special_claim)

    # 8. Test ObservabilityAgent
    observability_func = tool_map["ObservabilityAgent"]
    observability = observability_func(operation_type="CANCELLATION")
    print_result("ObservabilityAgent", observability)

    # 9. Test Enquiry_Tool
    enquiry_func = tool_map["Enquiry_Tool"]
    enquiry = enquiry_func()
    print_result("Enquiry_Tool", enquiry)

    # 10. Test Connect_To_Human_Tool
    human_connect_func = tool_map["Connect_To_Human_Tool"]
    human_connect = human_connect_func(
        reason_of_invoke="FRUSTRATED", frustration_score="8"
    )
    print_result("Connect_To_Human_Tool", human_connect)

    # 11. Test take_a_nap
    take_nap_func = tool_map["take_a_nap"]
    take_nap = take_nap_func()
    print_result("take_a_nap", take_nap)

    print("\n🏁 Tool Call Verification Script Finished 🏁")
    print(
        "\nNote: All tools return PENDING status immediately and execute in the background."
    )
    print(
        "In production, results are sent back via the queue after processing completes."
    )


if __name__ == "__main__":
    asyncio.run(main())
