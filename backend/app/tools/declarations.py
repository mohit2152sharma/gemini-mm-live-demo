"""
Tool function declarations for Gemini Live API integration.

This module contains the function declarations that define the interface
for travel booking tools. These declarations are used by the Gemini Live API
to understand what functions are available and how to call them.
"""

from google.genai import types


# Helper builders to keep schema and declaration definitions DRY
def _schema_string(description: str | None = None, enum: list[str] | None = None, default: str | None = None) -> types.Schema:
    kwargs: dict = {"type": types.Type.STRING}
    if description is not None:
        kwargs["description"] = description
    if enum is not None:
        kwargs["enum"] = enum
    if default is not None:
        kwargs["default"] = default
    return types.Schema(**kwargs)


def _schema_object(properties: dict | None = None, required: list[str] | None = None, description: str | None = None) -> types.Schema:
    kwargs: dict = {"type": types.Type.OBJECT, "properties": properties or {}}
    if required is not None:
        kwargs["required"] = required
    if description is not None:
        kwargs["description"] = description
    return types.Schema(**kwargs)


def _schema_array(items: types.Schema, description: str | None = None) -> types.Schema:
    kwargs: dict = {"type": types.Type.ARRAY, "items": items}
    if description is not None:
        kwargs["description"] = description
    return types.Schema(**kwargs)


def _declare(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=_schema_object(properties=properties or {}, required=required or []),
    )


# Function Declarations

take_a_nap_declaration = _declare(
    name="take_a_nap",
    description="A dummy function that takes a nap for 30 seconds and then wakes up with a friendly message. Use this to test long-running function calls and non-blocking execution.",
)

NameCorrectionAgent_declaration = _declare(
    name="NameCorrectionAgent",
    description="This **NameCorrectionAgent** will take care of name corrections  as well as name change also for given bookingID/PNR. This agent handles various types of name corrections including spelling corrections, name swaps, gender corrections, maiden name changes, and title removals.",
    properties={
        "correction_type": _schema_string(
            description="Type of name correction required.",
            enum=[
                "NAME_CORRECTION",
                "NAME_SWAP",
                "GENDER_SWAP",
                "MAIDEN_NAME_CHANGE",
                "REMOVE_TITLE",
            ],
        ),
        "fn": _schema_string(description="First Name of the passenger."),
        "ln": _schema_string(description="Last Name of the passenger."),
    },
    required=["correction_type", "fn", "ln"],
)

SpecialClaimAgent_declaration = _declare(
    name="SpecialClaimAgent",
    description="This **SpecialClaimAgent** handles special claim requests for flight bookings. This agent helps users file claims for various flight-related issues and disruptions.",
    properties={
        "claim_type": _schema_string(
            description="Type of special claim being filed by the user",
            enum=[
                "FLIGHT_NOT_OPERATIONAL",
                "MEDICAL_EMERGENCY",
                "TICKET_CANCELLED_WITH_AIRLINE",
            ],
        )
    },
    required=["claim_type"],
)

Enquiry_Tool_declaration = _declare(
    name="Enquiry_Tool",
    description="Helps user to get related documents for user query. Only help to retrieve relevant documentation for a enquiry or support.",
)

Eticket_Sender_Agent_declaration = _declare(
    name="Eticket_Sender_Agent",
    description="Sends the e-ticket for the given PNR or Booking ID via supported communication channels whatsapp and email.",
    properties={
        "booking_id_or_pnr": _schema_string(
            description="The booking ID or PNR of the user itinerary."
        )
    },
    required=["booking_id_or_pnr"],
)

ObservabilityAgent_declaration = _declare(
    name="ObservabilityAgent",
    description="This tool tracks or fetches the refund status for a given Booking ID based on a specific user operation.",
    properties={
        "operation_type": _schema_string(
            description="Type of operation_type being filed by the user",
            enum=["CANCELLATION", "DATE_CHANGE"],
        )
    },
    required=["operation_type"],
)

DateChangeAgent_declaration = _declare(
    name="DateChangeAgent",
    description="Quotes penalties or executes date change for an existing itinerary.",
    properties={
        "action": _schema_string(
            description="Choose QUOTE to fetch penalty/fare difference information, CONFIRM to execute the date change.",
            enum=["QUOTE", "CONFIRM"],
        ),
        "sector_info": _schema_array(
            items=_schema_object(
                properties={
                    "origin": _schema_string(
                        description="Airport Code of the origin city (e.g., DEL)."
                    ),
                    "destination": _schema_string(
                        description="Airport Code of the destination city (e.g., BOM)."
                    ),
                    "newDate": _schema_string(
                        description="New date for the journey in YYYY-MM-DD format (e.g., 2024-01-15)."
                    ),
                },
                required=["origin", "destination", "newDate"],
            ),
            description="List of sectors/journeys to change with their new dates.",
        ),
    },
    required=["action", "sector_info"],
)

Connect_To_Human_Tool_declaration = _declare(
    name="Connect_To_Human_Tool",
    description="Helps user to connect with human agent.",
    properties={
        "reason_of_invoke": _schema_string(
            description="Was the user frustrated or you are not able to help.",
            enum=["FRUSTRATED", "UNABLE_TO_HELP"],
        ),
        "frustration_score": _schema_string(
            description="How frustrated is the user in the conversation on a scale of 1 to 10."
        ),
    },
    required=["reason_of_invoke"],
)

Booking_Cancellation_Agent_declaration = _declare(
    name="Booking_Cancellation_Agent",
    description="Quotes penalties or executes cancellations for an existing itinerary. REQUIRES a valid booking ID/PNR to proceed.",
    properties={
        "booking_id_or_pnr": _schema_string(
            description="The booking ID or PNR of the itinerary to cancel. This is MANDATORY."
        ),
        "action": _schema_string(
            description="Choose QUOTE to fetch refund/penalty information, CONFIRM to execute the cancellation.",
            enum=["QUOTE", "CONFIRM"],
            default="QUOTE",
        ),
        "cancel_scope": _schema_string(
            description="Defaults to NOT_MENTIONED. Type of cancellation - FULL or PARTIAL. Don't ask this information upfront. ONLY fill when user mentions about it.",
            enum=["NOT_MENTIONED", "FULL", "PARTIAL"],
            default="NOT_MENTIONED",
        ),
        "otp": _schema_string(
            description="OTP (One Time Password) for confirmation use case. And it's length is **4 digit**. NOT A MANDATORY FIELD.",
            default="",
        ),
        "partial_info": _schema_array(
            description="Required **only** when cancel_scope = PARTIAL. Provide a list of journeys and passengers to cancel.",
            items=_schema_object(
                properties={
                    "journey": _schema_object(
                        properties={
                            "from_city": _schema_string(
                                description="Airport Code of the origin city (e.g., DEL)."
                            ),
                            "to_city": _schema_string(
                                description="Airport Code of the destination city (e.g., BOM)."
                            ),
                        }
                    ),
                    "pax_to_cancel": _schema_array(
                        description="List of passengers to cancel for the specified journey.",
                        items=_schema_object(
                            properties={
                                "fn": _schema_string(description="First Name of the passenger."),
                                "ln": _schema_string(description="Last Name of the passenger."),
                            }
                        ),
                    ),
                }
            ),
        ),
    },
    required=["booking_id_or_pnr", "action"],
)

Flight_Booking_Details_Agent_declaration = _declare(
    name="Flight_Booking_Details_Agent",
    description="Retrieves the full itinerary record for a given PNR / Booking ID—passengers, flight segments, departure & arrival times, airlines, fare classes, and ancillary add-ons.",
    properties={
        "booking_id_or_pnr": _schema_string(
            description="The booking ID or PNR of the user itinerary."
        )
    },
    required=["booking_id_or_pnr"],
)

Webcheckin_And_Boarding_Pass_Agent_declaration = _declare(
    name="Webcheckin_And_Boarding_Pass_Agent",
    description="This **Webcheckin_And_Boarding_Pass_Agent** agents will take care of web checkin and boarding pass for given bookingID/PNR. If user is already checked-in this agent will send boarding pass given PNR / Booking ID  via supported communication channels such as WhatsApp, email, or SMS. REQUIRES a valid booking ID/PNR to proceed.",
    properties={
        "booking_id_or_pnr": _schema_string(
            description="The booking ID or PNR of the itinerary for web check-in. This is MANDATORY."
        ),
        "journeys": _schema_array(
            description="List of journeys for which user wants to do web check-in. Each journey can have different passengers.",
            items=_schema_object(
                properties={
                    "origin": _schema_string(
                        description="Airport Code of the origin city (e.g., DEL)."
                    ),
                    "destination": _schema_string(
                        description="Airport Code of the destination city (e.g., BOM)."
                    ),
                    "isAllPax": _schema_string(
                        description="Set to true if user wants web check-in for all passengers on this journey, false if for specific passengers only.",
                        default="true",
                    ),
                    "pax_info": _schema_array(
                        description="Required **only** when isAllPax = false. Provide list of specific passengers for web check-in on this journey.",
                        items=_schema_object(
                            properties={
                                "fn": _schema_string(description="First Name of the passenger."),
                                "ln": _schema_string(description="Last Name of the passenger."),
                            },
                            required=["fn", "ln"],
                        ),
                    ),
                },
                required=["origin", "destination", "isAllPax"],
            ),
        ),
    },
    required=["booking_id_or_pnr", "journeys"],
)