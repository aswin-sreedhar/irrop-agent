# Shared state definition
# Defines the state schema that flows through the LangGraph workflow

from typing import TypedDict, Optional


class IRROPState(TypedDict):
    """
    Shared state for the SSBRES reaccommodation notification workflow.

    This state object flows through each node in the LangGraph agent,
    processing SSBRES messages to analyze passenger reaccommodations,
    generate personalized notifications, and dispatch them through
    appropriate channels (SMS or Email).
    """

    # Input - raw SSBRES message
    raw_message: dict  # Full incoming SSBRES JSON payload
    pnr: str  # Booking reference

    # Parsed message components
    passengers: list[dict]  # Passenger details from message
    original_itinerary: list[dict]  # Original flight segments
    new_itinerary: list[dict]  # New/rerouted flight segments
    disruption: dict  # Disruption type, reason, affected segments

    # Impact analysis - per passenger
    passenger_analysis: dict  # Keyed by passenger_id, contains reaccommodation details

    # Message generation and validation
    generated_messages: dict  # Keyed by passenger_id, raw generated message
    validated_messages: dict  # Keyed by passenger_id, validated message

    # Channel-specific formatted notifications
    sms_notifications: list[dict]  # SMS notifications ready to send
    email_notifications: list[dict]  # Email notifications ready to send

    # Dispatch tracking
    dispatch_log: list[dict]  # Record of every notification sent
    failed_notifications: list[dict]  # Notifications that failed pre-dispatch check

    # Validation and verification
    validation_warnings: list[str]  # Non-fatal warnings from verify_impact
    needs_review: list[str]  # Passenger IDs whose messages need human review

    # Error handling
    error: Optional[str]  # Any error encountered during processing
