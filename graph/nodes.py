# Individual agent nodes
# Contains discrete workflow steps: parse SSBRES message, analyze reaccommodations, generate notifications

import os
import re
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from graph.state import IRROPState

# Load environment variables
load_dotenv()

# Initialize Claude API
llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.7
)


def validate_input(state: IRROPState) -> dict:
    """
    Node 0: Validate raw SSBRES message structure and data integrity.

    Verifies all required fields exist, data formats are correct, and
    referenced entities (passengers, segments) are consistent.
    """
    raw_message = state["raw_message"]
    errors = []

    # Check required top-level fields
    required_fields = ["message_id", "pnr", "passengers", "original_itinerary", "disruption", "new_itinerary"]
    for field in required_fields:
        if field not in raw_message:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"error": f"Input validation failed: {', '.join(errors)}"}

    # Validate passengers list
    passengers = raw_message.get("passengers", [])
    if not passengers or len(passengers) == 0:
        errors.append("passengers list is empty")

    passenger_ids = set()
    for idx, passenger in enumerate(passengers):
        if "passenger_id" not in passenger:
            errors.append(f"Passenger at index {idx} missing passenger_id")
        else:
            passenger_ids.add(passenger["passenger_id"])

        # Check required passenger fields
        for field in ["first_name", "last_name", "email", "phone", "notification_preference"]:
            if field not in passenger:
                errors.append(f"Passenger {passenger.get('passenger_id', idx)} missing {field}")

    # Validate original_itinerary
    original_itinerary = raw_message.get("original_itinerary", [])
    if not original_itinerary:
        errors.append("original_itinerary is empty")

    for idx, segment in enumerate(original_itinerary):
        segment_required = ["segment_id", "flight_number", "origin", "destination", "departure_date", "departure_time", "cabin", "passengers"]
        for field in segment_required:
            if field not in segment:
                errors.append(f"Original segment {idx} missing {field}")

        # Validate date format (YYYY-MM-DD)
        if "departure_date" in segment:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", segment["departure_date"]):
                errors.append(f"Original segment {idx} has invalid departure_date format (expected YYYY-MM-DD)")

        # Validate time format (HH:MM)
        if "departure_time" in segment:
            if not re.match(r"^\d{2}:\d{2}$", segment["departure_time"]):
                errors.append(f"Original segment {idx} has invalid departure_time format (expected HH:MM)")

        # Verify passenger_ids in segment exist in passengers list
        if "passengers" in segment:
            for pid in segment["passengers"]:
                if pid not in passenger_ids:
                    errors.append(f"Original segment {idx} references unknown passenger_id: {pid}")

    # Validate new_itinerary
    new_itinerary = raw_message.get("new_itinerary", [])

    for idx, segment in enumerate(new_itinerary):
        segment_required = ["segment_id", "flight_number", "origin", "destination", "departure_date", "departure_time", "cabin", "passengers"]
        for field in segment_required:
            if field not in segment:
                errors.append(f"New segment {idx} missing {field}")

        # Validate date format
        if "departure_date" in segment:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", segment["departure_date"]):
                errors.append(f"New segment {idx} has invalid departure_date format")

        # Validate time format
        if "departure_time" in segment:
            if not re.match(r"^\d{2}:\d{2}$", segment["departure_time"]):
                errors.append(f"New segment {idx} has invalid departure_time format")

        # Verify passenger_ids
        if "passengers" in segment:
            for pid in segment["passengers"]:
                if pid not in passenger_ids:
                    errors.append(f"New segment {idx} references unknown passenger_id: {pid}")

    # Validate disruption
    disruption = raw_message.get("disruption", {})
    if "type" not in disruption:
        errors.append("disruption missing 'type' field")
    elif disruption["type"] not in ["CANCELLATION", "DELAY", "DIVERSION", "GATE_CHANGE"]:
        errors.append(f"disruption.type '{disruption['type']}' is not a valid type (expected CANCELLATION, DELAY, DIVERSION, or GATE_CHANGE)")

    if errors:
        return {"error": f"Input validation failed: {'; '.join(errors)}"}

    return {"error": None}


def identify_event(state: IRROPState) -> dict:
    """
    Node 1: Parse SSBRES message and extract key components.

    Extracts PNR, passengers, itineraries, and disruption information
    from the raw SSBRES JSON payload.
    """
    raw_message = state["raw_message"]

    try:
        pnr = raw_message.get("pnr")
        passengers = raw_message.get("passengers", [])
        original_itinerary = raw_message.get("original_itinerary", [])
        new_itinerary = raw_message.get("new_itinerary", [])
        disruption = raw_message.get("disruption", {})

        return {
            "pnr": pnr,
            "passengers": passengers,
            "original_itinerary": original_itinerary,
            "new_itinerary": new_itinerary,
            "disruption": disruption,
            "error": None
        }
    except Exception as e:
        return {"error": f"Failed to parse SSBRES message: {str(e)}"}


def assess_impact(state: IRROPState) -> dict:
    """
    Node 2: Analyze reaccommodation impact for each passenger.

    Compares original vs new itinerary for each passenger to determine:
    - Cabin changes (DOWNGRADE/UPGRADE/SAME)
    - Routing changes (different flight path)
    - Date changes (travel date shifted)
    - Reaccommodation status (REROUTED/DATE_CHANGE/etc.)
    """
    passengers = state["passengers"]
    original_itinerary = state["original_itinerary"]
    new_itinerary = state["new_itinerary"]

    passenger_analysis = {}

    for passenger in passengers:
        passenger_id = passenger["passenger_id"]

        # Find segments this passenger was on
        original_segments = [seg for seg in original_itinerary if passenger_id in seg.get("passengers", [])]
        new_segments = [seg for seg in new_itinerary if passenger_id in seg.get("passengers", [])]

        # Analyze cabin change
        cabin_change = "NONE"
        if original_segments and new_segments:
            orig_cabin = original_segments[0].get("cabin")
            new_cabin = new_segments[0].get("cabin")

            if orig_cabin != new_cabin:
                cabin_map = {"Business": 2, "Economy": 1}
                if cabin_map.get(new_cabin, 0) < cabin_map.get(orig_cabin, 0):
                    cabin_change = "DOWNGRADE"
                elif cabin_map.get(new_cabin, 0) > cabin_map.get(orig_cabin, 0):
                    cabin_change = "UPGRADE"
            else:
                cabin_change = "SAME"

        # Analyze routing change
        routing_change = False
        if original_segments and new_segments:
            orig_route = "→".join([seg["origin"] for seg in original_segments] + [original_segments[-1]["destination"]])
            new_route = "→".join([seg["origin"] for seg in new_segments] + [new_segments[-1]["destination"]])
            routing_change = (orig_route != new_route) or (len(original_segments) != len(new_segments))

        # Analyze date change
        date_change = False
        if original_segments and new_segments:
            orig_date = original_segments[0].get("departure_date")
            new_date = new_segments[0].get("departure_date")
            date_change = orig_date != new_date

        # Determine reaccommodation status
        if not new_segments:
            reaccommodation_status = "UNACCOMMODATED"
        elif cabin_change == "DOWNGRADE":
            reaccommodation_status = "DOWNGRADE"
        elif cabin_change == "UPGRADE":
            reaccommodation_status = "UPGRADE"
        elif date_change:
            reaccommodation_status = "DATE_CHANGE"
        elif routing_change:
            reaccommodation_status = "REROUTED"
        else:
            reaccommodation_status = "SAME"

        passenger_analysis[passenger_id] = {
            "reaccommodation_status": reaccommodation_status,
            "cabin_change": cabin_change,
            "routing_change": routing_change,
            "date_change": date_change,
            "original_segments": original_segments,
            "new_segments": new_segments
        }

    return {"passenger_analysis": passenger_analysis}


def verify_impact(state: IRROPState) -> dict:
    """
    Node 2.5: Verify passenger impact analysis for completeness and correctness.

    Cross-checks that all passengers are analyzed, cabin hierarchy is correct,
    and routing logic is sound. Logs warnings but doesn't halt workflow.
    """
    passengers = state["passengers"]
    passenger_analysis = state["passenger_analysis"]
    original_itinerary = state["original_itinerary"]
    new_itinerary = state["new_itinerary"]
    warnings = []

    # Cabin hierarchy (higher number = higher class)
    cabin_hierarchy = {"FIRST": 4, "BUSINESS": 3, "PREMIUM_ECONOMY": 2, "ECONOMY": 1}

    # Check every passenger has analysis
    passenger_ids = [p["passenger_id"] for p in passengers]
    for passenger_id in passenger_ids:
        if passenger_id not in passenger_analysis:
            warnings.append(f"Passenger {passenger_id} missing from passenger_analysis")

    # Verify each analysis entry
    for passenger_id, analysis in passenger_analysis.items():
        # Verify passenger exists
        if passenger_id not in passenger_ids:
            warnings.append(f"Unknown passenger {passenger_id} in passenger_analysis")
            continue

        cabin_change = analysis.get("cabin_change", "NONE")
        reaccommodation_status = analysis.get("reaccommodation_status", "UNKNOWN")
        original_segs = analysis.get("original_segments", [])
        new_segs = analysis.get("new_segments", [])

        # Verify DOWNGRADE cabin hierarchy
        if cabin_change == "DOWNGRADE":
            if original_segs and new_segs:
                orig_cabin = original_segs[0].get("cabin", "").upper()
                new_cabin = new_segs[0].get("cabin", "").upper()
                orig_level = cabin_hierarchy.get(orig_cabin, 0)
                new_level = cabin_hierarchy.get(new_cabin, 0)
                if new_level >= orig_level:
                    warnings.append(f"Passenger {passenger_id}: cabin_change=DOWNGRADE but {new_cabin} is not lower than {orig_cabin}")

        # Verify UPGRADE cabin hierarchy
        if cabin_change == "UPGRADE":
            if original_segs and new_segs:
                orig_cabin = original_segs[0].get("cabin", "").upper()
                new_cabin = new_segs[0].get("cabin", "").upper()
                orig_level = cabin_hierarchy.get(orig_cabin, 0)
                new_level = cabin_hierarchy.get(new_cabin, 0)
                if new_level <= orig_level:
                    warnings.append(f"Passenger {passenger_id}: cabin_change=UPGRADE but {new_cabin} is not higher than {orig_cabin}")

        # Verify UNACCOMMODATED truly has no new segments
        if reaccommodation_status == "UNACCOMMODATED":
            if new_segs:
                warnings.append(f"Passenger {passenger_id}: status=UNACCOMMODATED but has {len(new_segs)} new segments")

        # Verify REROUTED reaches same final destination
        if reaccommodation_status == "REROUTED" and original_segs and new_segs:
            orig_dest = original_segs[-1].get("destination")
            new_dest = new_segs[-1].get("destination")
            if orig_dest != new_dest:
                warnings.append(f"Passenger {passenger_id}: REROUTED but final destination changed from {orig_dest} to {new_dest}")

    return {"validation_warnings": warnings}


def generate_messages(state: IRROPState) -> dict:
    """
    Node 3: Generate personalized notification messages using Claude API.

    For each passenger, generates a message tailored to their specific
    reaccommodation situation (downgrades, rerouting, date changes, etc.)
    """
    passengers = state["passengers"]
    passenger_analysis = state["passenger_analysis"]
    disruption = state["disruption"]

    generated_messages = {}

    for passenger in passengers:
        passenger_id = passenger["passenger_id"]
        analysis = passenger_analysis.get(passenger_id, {})

        # Build context for Claude
        original_segs = analysis.get("original_segments", [])
        new_segs = analysis.get("new_segments", [])
        status = analysis.get("reaccommodation_status", "UNKNOWN")
        cabin_change = analysis.get("cabin_change", "NONE")
        routing_change = analysis.get("routing_change", False)
        date_change = analysis.get("date_change", False)

        # Format original itinerary
        orig_itin_str = " → ".join([f"{s['flight_number']} ({s['origin']}-{s['destination']}, {s['departure_date']} {s['departure_time']}, {s['cabin']})" for s in original_segs])

        # Format new itinerary
        new_itin_str = " → ".join([f"{s['flight_number']} ({s['origin']}-{s['destination']}, {s['departure_date']} {s['departure_time']}, {s['cabin']})" for s in new_segs]) if new_segs else "Not yet reaccommodated"

        # Build notification preference context
        notif_pref = passenger.get("notification_preference", "EMAIL")
        format_instruction = "Maximum 2 sentences, under 160 characters" if notif_pref == "SMS" else "Short paragraph, professional and detailed tone"

        # Build prompt
        prompt = f"""Generate a clear, empathetic passenger notification message for an airline reaccommodation:

Passenger: {passenger['first_name']} {passenger['last_name']} (ID: {passenger_id})
Notification Preference: {notif_pref}

Disruption:
- Type: {disruption.get('type')}
- Reason: {disruption.get('reason')}

Original Itinerary:
{orig_itin_str}

New Itinerary:
{new_itin_str}

Reaccommodation Status: {status}
Cabin Change: {cabin_change}
Routing Changed: {routing_change}
Date Changed: {date_change}

Requirements:
- Be empathetic and apologetic
- Clearly state what happened and the new arrangements
- Include all flight numbers, times, and cabin classes
- For {notif_pref}: {format_instruction}
{"- IMPORTANT: Mention they may be eligible for compensation due to cabin downgrade" if cabin_change == "DOWNGRADE" else ""}
{"- IMPORTANT: Highlight the travel date has changed prominently" if date_change else ""}
{"- IMPORTANT: Mention complimentary cabin upgrade" if cabin_change == "UPGRADE" else ""}
{"- IMPORTANT: Ask them to contact Air India immediately for rebooking" if status == "UNACCOMMODATED" else ""}

Generate only the message text, no additional commentary."""

        try:
            response = llm.invoke(prompt)
            message = response.content.strip()

            # Self-consistency check: extract key facts from generated message
            fact_check_prompt = f"""Extract the following key facts from this passenger notification message:

Message: "{message}"

Extract and list:
1. All flight numbers mentioned (e.g., AI-661, AI-662)
2. All dates mentioned (in YYYY-MM-DD format if possible)
3. Cabin class(es) mentioned (e.g., Business, Economy)

Respond in this exact format:
Flight numbers: [list them comma-separated]
Dates: [list them comma-separated]
Cabin classes: [list them comma-separated]"""

            try:
                fact_response = llm.invoke(fact_check_prompt)
                extracted_facts = fact_response.content.strip()

                # Check if new flight numbers are mentioned
                expected_flights = [seg["flight_number"] for seg in new_segs]
                facts_valid = True

                for expected_flight in expected_flights:
                    if expected_flight not in extracted_facts:
                        facts_valid = False
                        break

                # If facts don't match, regenerate with explicit correction
                if not facts_valid and expected_flights:
                    correction_prompt = f"""The previous message was missing key flight numbers. Generate a corrected version:

Original message: "{message}"

REQUIRED flight numbers to mention: {', '.join(expected_flights)}
REQUIRED cabin class: {', '.join(cabin_classes) if cabin_classes else 'N/A'}

Generate a corrected message that includes ALL flight numbers and correct cabin information."""

                    correction_response = llm.invoke(correction_prompt)
                    corrected_message = correction_response.content.strip()

                    # Try fact check once more
                    final_check_response = llm.invoke(fact_check_prompt.replace(message, corrected_message))
                    final_facts = final_check_response.content.strip()

                    # If still wrong, flag for review
                    still_wrong = False
                    for expected_flight in expected_flights:
                        if expected_flight not in final_facts:
                            still_wrong = True
                            break

                    if still_wrong:
                        generated_messages[passenger_id] = corrected_message
                        state.get("needs_review", []).append(passenger_id)
                    else:
                        generated_messages[passenger_id] = corrected_message
                else:
                    generated_messages[passenger_id] = message

            except Exception as fact_check_error:
                # If fact checking fails, just use original message
                generated_messages[passenger_id] = message

        except Exception as e:
            generated_messages[passenger_id] = f"Error generating message: {str(e)}"

    return {"generated_messages": generated_messages, "needs_review": state.get("needs_review", [])}


def validate_messages(state: IRROPState) -> dict:
    """
    Node 4: Validate generated messages for accuracy and completeness.

    Uses Claude API to validate each message contains correct flight numbers,
    dates, cabin classes, and appropriate tone for the situation.
    """
    generated_messages = state["generated_messages"]
    passenger_analysis = state["passenger_analysis"]
    passengers = state["passengers"]

    validated_messages = {}

    for passenger in passengers:
        passenger_id = passenger["passenger_id"]
        message = generated_messages.get(passenger_id, "")
        analysis = passenger_analysis.get(passenger_id, {})

        new_segs = analysis.get("new_segments", [])
        cabin_change = analysis.get("cabin_change", "NONE")
        date_change = analysis.get("date_change", False)

        # Build validation criteria
        flight_numbers = [seg["flight_number"] for seg in new_segs]
        cabin_classes = list(set([seg["cabin"] for seg in new_segs]))

        validation_prompt = f"""Validate the following passenger notification message:

Message: "{message}"

Expected to contain:
- Flight numbers: {', '.join(flight_numbers) if flight_numbers else 'N/A'}
- Cabin class(es): {', '.join(cabin_classes) if cabin_classes else 'N/A'}
- Cabin change status: {cabin_change}
- Date change mentioned: {date_change}

Check if the message:
1. Contains all correct flight numbers
2. Mentions correct cabin class(es)
3. Is empathetic and includes an apology
4. Provides accurate dates and times
5. {"Mentions compensation eligibility for cabin downgrade" if cabin_change == "DOWNGRADE" else "Is clear and concise"}
6. Appropriate tone for the situation

Respond with only "VALID" if all criteria are met, or "INVALID: [reason]" if not."""

        try:
            response = llm.invoke(validation_prompt)
            validation_result = response.content.strip()

            if validation_result.startswith("VALID"):
                validated_messages[passenger_id] = message
            else:
                # Attempt to regenerate once
                regenerate_prompt = f"""The following message was invalid: "{message}"
Reason: {validation_result}

Generate a better version that includes:
- All flight numbers: {', '.join(flight_numbers) if flight_numbers else 'N/A'}
- Correct cabin class: {', '.join(cabin_classes) if cabin_classes else 'N/A'}
- Empathetic apology
- Accurate information
{"- Compensation eligibility notice" if cabin_change == "DOWNGRADE" else ""}
{"- Prominent date change warning" if date_change else ""}

Generate only the improved message text."""

                regenerate_response = llm.invoke(regenerate_prompt)
                validated_messages[passenger_id] = regenerate_response.content.strip()
        except Exception as e:
            # If validation fails, accept the original message
            validated_messages[passenger_id] = message

    return {"validated_messages": validated_messages}


def format_sms(state: IRROPState) -> dict:
    """
    Node 5: Format SMS notifications for passengers who prefer SMS.

    Formats messages to be under 160 characters with PNR prefix,
    ready for SMS dispatch.
    """
    validated_messages = state["validated_messages"]
    passengers = state["passengers"]
    pnr = state["pnr"]

    sms_notifications = []

    for passenger in passengers:
        if passenger.get("notification_preference") == "SMS":
            passenger_id = passenger["passenger_id"]
            message = validated_messages.get(passenger_id, "")

            # Format with PNR prefix
            formatted_message = f"{pnr}: {message}"

            # Truncate if too long (SMS limit 160 chars)
            if len(formatted_message) > 160:
                formatted_message = formatted_message[:157] + "..."

            sms_notifications.append({
                "passenger_id": passenger_id,
                "phone": passenger["phone"],
                "message": formatted_message
            })

    return {"sms_notifications": sms_notifications}


def format_email(state: IRROPState) -> dict:
    """
    Node 6: Format email notifications for passengers who prefer email.

    Formats messages with appropriate subject lines based on the specific
    reaccommodation scenario (cabin downgrade, rerouting, date change, etc.)
    """
    validated_messages = state["validated_messages"]
    passengers = state["passengers"]
    passenger_analysis = state["passenger_analysis"]
    pnr = state["pnr"]
    disruption = state["disruption"]

    email_notifications = []

    for passenger in passengers:
        if passenger.get("notification_preference") == "EMAIL":
            passenger_id = passenger["passenger_id"]
            message = validated_messages.get(passenger_id, "")
            analysis = passenger_analysis.get(passenger_id, {})

            # Determine subject line based on reaccommodation status
            status = analysis.get("reaccommodation_status", "UNKNOWN")
            cabin_change = analysis.get("cabin_change", "NONE")

            if cabin_change == "DOWNGRADE":
                subject = f"Important: Cabin Downgrade Notice - PNR {pnr}"
            elif cabin_change == "UPGRADE":
                subject = f"Complimentary Cabin Upgrade - PNR {pnr}"
            elif status == "DATE_CHANGE":
                subject = f"URGENT: Travel Date Change - PNR {pnr}"
            elif status == "REROUTED":
                subject = f"Flight Rerouting Update - PNR {pnr}"
            elif status == "UNACCOMMODATED":
                subject = f"ACTION REQUIRED: Rebooking Assistance - PNR {pnr}"
            else:
                subject = f"Flight Update - PNR {pnr} - {disruption.get('type', 'DISRUPTION')}"

            # Format email body
            body = f"""Dear {passenger['first_name']} {passenger['last_name']},

{message}

We sincerely apologize for any inconvenience this may cause. If you have any questions or need assistance, please contact our customer service team at 1800-180-1407 or visit our website.

Booking Reference: {pnr}
Passenger ID: {passenger_id}

Best regards,
Air India Customer Service Team"""

            email_notifications.append({
                "passenger_id": passenger_id,
                "email": passenger["email"],
                "subject": subject,
                "body": body
            })

    return {"email_notifications": email_notifications}


def pre_dispatch_check(state: IRROPState) -> dict:
    """
    Node 7: Pre-dispatch verification to ensure notification quality.

    Verifies every passenger has exactly one notification, all required
    fields are present, and formatting constraints are met. Removes
    invalid notifications and logs them as failed.
    """
    passengers = state["passengers"]
    sms_notifications = state.get("sms_notifications", [])
    email_notifications = state.get("email_notifications", [])
    failed_notifications = []

    # Track which passengers have been notified
    notified_passengers = set()
    verified_sms = []
    verified_email = []

    # Verify SMS notifications
    for sms in sms_notifications:
        passenger_id = sms.get("passenger_id")
        phone = sms.get("phone")
        message = sms.get("message", "")

        # Check for required fields
        if not passenger_id:
            failed_notifications.append({
                "notification": sms,
                "reason": "Missing passenger_id"
            })
            continue

        if not phone:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": sms,
                "reason": "Missing phone number"
            })
            continue

        # Check SMS length (160 chars)
        if len(message) > 160:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": sms,
                "reason": f"SMS message exceeds 160 chars (actual: {len(message)})"
            })
            continue

        # Check for duplicate
        if passenger_id in notified_passengers:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": sms,
                "reason": "Duplicate notification (passenger already notified)"
            })
            continue

        notified_passengers.add(passenger_id)
        verified_sms.append(sms)

    # Verify email notifications
    for email in email_notifications:
        passenger_id = email.get("passenger_id")
        email_addr = email.get("email")
        subject = email.get("subject", "")
        body = email.get("body", "")

        # Check for required fields
        if not passenger_id:
            failed_notifications.append({
                "notification": email,
                "reason": "Missing passenger_id"
            })
            continue

        if not email_addr:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": email,
                "reason": "Missing email address"
            })
            continue

        if not subject:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": email,
                "reason": "Missing email subject"
            })
            continue

        if not body:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": email,
                "reason": "Missing email body"
            })
            continue

        # Check for duplicate
        if passenger_id in notified_passengers:
            failed_notifications.append({
                "passenger_id": passenger_id,
                "notification": email,
                "reason": "Duplicate notification (passenger already notified)"
            })
            continue

        notified_passengers.add(passenger_id)
        verified_email.append(email)

    # Check if any passenger is missing a notification
    all_passenger_ids = {p["passenger_id"] for p in passengers}
    missing_passengers = all_passenger_ids - notified_passengers

    for missing_pid in missing_passengers:
        failed_notifications.append({
            "passenger_id": missing_pid,
            "notification": None,
            "reason": "No notification generated for this passenger"
        })

    return {
        "sms_notifications": verified_sms,
        "email_notifications": verified_email,
        "failed_notifications": failed_notifications
    }
