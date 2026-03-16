# LangGraph agent definition
# Orchestrates the IRROP notification workflow using LangGraph's state machine

from datetime import datetime
from langgraph.graph import StateGraph, END
from graph.state import IRROPState
from graph.nodes import (
    validate_input,
    identify_event,
    assess_impact,
    verify_impact,
    generate_messages,
    validate_messages,
    format_sms,
    format_email,
    pre_dispatch_check
)


def dispatch(state: IRROPState) -> dict:
    """
    Final node: Dispatch all notifications and log results.

    Simulates sending SMS and email notifications by printing them
    to console, then logs each dispatch with timestamp and status.
    """
    sms_notifications = state.get("sms_notifications", [])
    email_notifications = state.get("email_notifications", [])
    dispatch_log = []

    print("\n" + "="*60)
    print("DISPATCHING NOTIFICATIONS")
    print("="*60)

    # Dispatch SMS notifications
    for sms in sms_notifications:
        timestamp = datetime.now().isoformat()
        print(f"\n[SMS] To: {sms['phone']} (Passenger: {sms['passenger_id']})")
        print(f"Message: {sms['message']}")
        print(f"Timestamp: {timestamp}")

        dispatch_log.append({
            "passenger_id": sms["passenger_id"],
            "channel": "SMS",
            "status": "SENT",
            "timestamp": timestamp
        })

    # Dispatch email notifications
    for email in email_notifications:
        timestamp = datetime.now().isoformat()
        print(f"\n[EMAIL] To: {email['email']} (Passenger: {email['passenger_id']})")
        print(f"Subject: {email['subject']}")
        print(f"Body:\n{email['body']}")
        print(f"Timestamp: {timestamp}")

        dispatch_log.append({
            "passenger_id": email["passenger_id"],
            "channel": "EMAIL",
            "status": "SENT",
            "timestamp": timestamp
        })

    print("\n" + "="*60)
    print(f"TOTAL NOTIFICATIONS SENT: {len(dispatch_log)}")
    print("="*60 + "\n")

    return {"dispatch_log": dispatch_log}


def error_handler(state: IRROPState) -> dict:
    """
    Error handling node: Prints error and returns state as-is.
    """
    error = state.get("error", "Unknown error")
    print("\n" + "="*60)
    print("ERROR OCCURRED")
    print("="*60)
    print(f"Error: {error}")
    print("="*60 + "\n")
    return state


def route_after_validation(state: IRROPState) -> str:
    """
    Conditional routing after message validation.

    Determines which formatting nodes to run based on passenger
    notification preferences.
    """
    # Check if there was an error
    if state.get("error"):
        return "error_handler"

    passengers = state.get("passengers", [])

    has_sms = any(p["notification_preference"] == "SMS" for p in passengers)
    has_email = any(p["notification_preference"] == "EMAIL" for p in passengers)

    if has_sms and has_email:
        return "both"
    elif has_sms:
        return "sms_only"
    elif has_email:
        return "email_only"
    else:
        return "dispatch"


def route_after_sms(state: IRROPState) -> str:
    """
    Conditional routing after SMS formatting.

    If we came from "both" route, go to email formatting.
    If we came from "sms_only" route, go to pre_dispatch_check.
    """
    passengers = state.get("passengers", [])
    has_email = any(p["notification_preference"] == "EMAIL" for p in passengers)

    if has_email:
        return "format_email"
    else:
        return "pre_dispatch_check"


def check_error(state: IRROPState) -> str:
    """
    Check for errors after each major node.
    """
    if state.get("error"):
        return "error_handler"
    return "continue"


# Build the StateGraph
workflow = StateGraph(IRROPState)

# Add all nodes
workflow.add_node("validate_input", validate_input)
workflow.add_node("identify_event", identify_event)
workflow.add_node("assess_impact", assess_impact)
workflow.add_node("verify_impact", verify_impact)
workflow.add_node("generate_messages", generate_messages)
workflow.add_node("validate_messages", validate_messages)
workflow.add_node("format_sms", format_sms)
workflow.add_node("format_email", format_email)
workflow.add_node("pre_dispatch_check", pre_dispatch_check)
workflow.add_node("dispatch", dispatch)
workflow.add_node("error_handler", error_handler)

# Set entry point
workflow.set_entry_point("validate_input")

# Add conditional edge after validate_input (check for errors)
workflow.add_conditional_edges(
    "validate_input",
    check_error,
    {
        "error_handler": "error_handler",
        "continue": "identify_event"
    }
)

# Add edges for main workflow
workflow.add_edge("identify_event", "assess_impact")
workflow.add_edge("assess_impact", "verify_impact")
workflow.add_edge("verify_impact", "generate_messages")
workflow.add_edge("generate_messages", "validate_messages")

# Add conditional routing after validation
workflow.add_conditional_edges(
    "validate_messages",
    route_after_validation,
    {
        "both": "format_sms",
        "sms_only": "format_sms",
        "email_only": "format_email",
        "dispatch": "pre_dispatch_check",
        "error_handler": "error_handler"
    }
)

# Add conditional routing after SMS formatting
workflow.add_conditional_edges(
    "format_sms",
    route_after_sms,
    {
        "format_email": "format_email",
        "pre_dispatch_check": "pre_dispatch_check"
    }
)

# Email formatting always leads to pre_dispatch_check
workflow.add_edge("format_email", "pre_dispatch_check")

# Pre-dispatch check leads to dispatch
workflow.add_edge("pre_dispatch_check", "dispatch")

# Terminal nodes
workflow.add_edge("dispatch", END)
workflow.add_edge("error_handler", END)

# Compile the graph
irrop_graph = workflow.compile()
