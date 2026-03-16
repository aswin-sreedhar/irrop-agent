# IRROP Agent — Airline Reaccommodation Notification System

An AI-powered notification system that processes airline SSBRES (Special Service Request) reaccommodation messages and automatically generates personalized passenger notifications. Built using LangGraph multi-agent architecture and Claude Sonnet 4.5, the system validates SSBRES payloads, analyzes passenger-specific impacts (cabin downgrades/upgrades, rerouting, date changes), generates empathetic context-aware messages, and dispatches notifications through appropriate channels (SMS/Email) based on passenger preferences.

## Architecture

The system uses a LangGraph state machine with **8 sequential nodes** that process SSBRES reaccommodation events:

```
┌─────────────────┐
│  API Request    │
│ (PNR or Raw Msg)│
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                      LangGraph Workflow                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  0. validate_input                                               │
│     • Verify SSBRES message structure and required fields       │
│     • Validate date/time formats                                │
│     • Check disruption type is valid                            │
│     • Cross-check passenger_ids referenced in segments          │
│     • Return errors if validation fails                         │
│                                                                  │
│  1. identify_event                                               │
│     • Parse SSBRES JSON payload                                 │
│     • Extract PNR, passengers, itineraries, disruption info     │
│     • Populate state with parsed data                           │
│                                                                  │
│  2. assess_impact                                                │
│     • Compare original vs new itinerary per passenger           │
│     • Detect cabin changes (DOWNGRADE/UPGRADE/SAME)             │
│     • Detect routing changes (different flight path)            │
│     • Detect date changes (travel date shifted)                 │
│     • Classify reaccommodation status                           │
│                                                                  │
│  2.5 verify_impact                                               │
│     • Verify all passengers have analysis                       │
│     • Validate cabin hierarchy logic                            │
│     • Check UNACCOMMODATED passengers have no new segments      │
│     • Check REROUTED passengers reach same final destination    │
│     • Log warnings but continue workflow (graceful)             │
│                                                                  │
│  3. generate_messages                                            │
│     • Call Claude API for each passenger                        │
│     • Generate context-aware messages:                          │
│       - Downgrades → mention compensation eligibility           │
│       - Upgrades → highlight complimentary nature               │
│       - Date changes → prominently warn about new date          │
│       - Unaccommodated → ask to contact airline                 │
│     • Run self-consistency fact-checking on generated messages  │
│     • Regenerate if flight numbers/details are wrong            │
│     • Flag messages needing human review                        │
│                                                                  │
│  4. validate_messages                                            │
│     • Call Claude API to validate each message                  │
│     • Check for correct flight numbers, dates, cabin classes    │
│     • Verify empathetic tone and apology present                │
│     • Regenerate invalid messages once                          │
│                                                                  │
│  5. Conditional Routing                                          │
│     ├─> format_sms (if SMS passengers exist)                    │
│     │   • Add PNR prefix                                        │
│     │   • Truncate to 160 chars                                 │
│     │                                                            │
│     └─> format_email (if EMAIL passengers exist)                │
│         • Generate scenario-specific subject lines              │
│         • Add greeting, sign-off, contact details               │
│                                                                  │
│  6. pre_dispatch_check                                           │
│     • Verify every passenger has exactly one notification       │
│     • Check SMS messages ≤ 160 chars                            │
│     • Check email has subject and body                          │
│     • Check all required fields populated                       │
│     • Remove invalid notifications (log as failed)              │
│                                                                  │
│  7. dispatch                                                     │
│     • Print notifications to console (simulated sending)        │
│     • Log all dispatches with timestamps                        │
│     • Return dispatch log                                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│  API Response    │
│  (Summary + Log  │
│   + Warnings)    │
└──────────────────┘
```

## SSBRES Payload Structure

The system processes SSBRES-style JSON payloads with the following structure:

```json
{
  "message_id": "SSBRES_2026031601_STU901",
  "pnr": "STU901",
  "booking_reference": "STU901",
  "disruption": {
    "type": "CANCELLATION",
    "reason": "AIRCRAFT_TECHNICAL_ISSUE",
    "affected_segments": ["AI-661"]
  },
  "passengers": [
    {
      "passenger_id": "PAX001",
      "first_name": "Arjun",
      "last_name": "Nair",
      "email": "arjun.nair@email.com",
      "phone": "+919876543216",
      "notification_preference": "SMS"
    },
    {
      "passenger_id": "PAX002",
      "first_name": "Meera",
      "last_name": "Nair",
      "email": "meera.nair@email.com",
      "phone": "+919876543217",
      "notification_preference": "EMAIL"
    }
  ],
  "original_itinerary": [
    {
      "segment_id": "SEG001",
      "flight_number": "AI-661",
      "origin": "COK",
      "destination": "DEL",
      "departure_date": "2026-03-16",
      "departure_time": "14:30",
      "arrival_date": "2026-03-16",
      "arrival_time": "17:45",
      "cabin": "Business",
      "passengers": ["PAX001", "PAX002"]
    }
  ],
  "new_itinerary": [
    {
      "segment_id": "SEG002",
      "flight_number": "AI-662",
      "origin": "COK",
      "destination": "BOM",
      "departure_date": "2026-03-16",
      "departure_time": "16:15",
      "arrival_date": "2026-03-16",
      "arrival_time": "18:30",
      "cabin": "Economy",
      "passengers": ["PAX001"]
    },
    {
      "segment_id": "SEG003",
      "flight_number": "AI-864",
      "origin": "BOM",
      "destination": "DEL",
      "departure_date": "2026-03-16",
      "departure_time": "20:00",
      "arrival_date": "2026-03-16",
      "arrival_time": "22:15",
      "cabin": "Economy",
      "passengers": ["PAX001"]
    },
    {
      "segment_id": "SEG004",
      "flight_number": "AI-661",
      "origin": "COK",
      "destination": "DEL",
      "departure_date": "2026-03-17",
      "departure_time": "14:30",
      "arrival_date": "2026-03-17",
      "arrival_time": "17:45",
      "cabin": "Business",
      "passengers": ["PAX002"]
    }
  ]
}
```

## Inference Rules

The agent applies **3 core inference rules** to analyze reaccommodation impact per passenger:

### 1. Cabin Change Detection
Compares cabin class between original and new itinerary using hierarchy:
```
FIRST (4) > BUSINESS (3) > PREMIUM_ECONOMY (2) > ECONOMY (1)
```
- **DOWNGRADE**: New cabin level < Original cabin level → Triggers compensation mention
- **UPGRADE**: New cabin level > Original cabin level → Highlights complimentary upgrade
- **SAME**: No cabin change

### 2. Routing Change Detection
Compares flight paths between original and new itinerary:
```
Original: COK → DEL (direct)
New: COK → BOM → DEL (via BOM)
```
- **REROUTED**: Different origin→destination path OR different number of segments
- **Verifies**: Final destination must still match original destination

### 3. Date Change Detection
Compares departure dates:
```
Original: 2026-03-16
New: 2026-03-17
```
- **DATE_CHANGE**: Departure date differs → Prominently warns passenger about new date
- Used to prioritize email subject lines (e.g., "URGENT: Travel Date Change")

## Tech Stack

- **Framework**: FastAPI
- **AI Orchestration**: LangGraph (state machine with 8 nodes)
- **LLM**: Anthropic Claude Sonnet 4.5 (claude-sonnet-4-20250514) via langchain-anthropic
- **Database**: SQLAlchemy with in-memory SQLite (PNR records with JSON payloads)
- **Validation**: Comprehensive input validation, impact verification, pre-dispatch checks
- **Environment**: Python 3.13+, python-dotenv
- **Server**: Uvicorn

## How to Run Locally

### 1. Clone the repository
```bash
git clone <repository-url>
cd irrop-agent
```

### 2. Set up environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 3. Install dependencies
```bash
pip install fastapi uvicorn langgraph langchain-anthropic python-dotenv sqlalchemy
```

### 4. Configure API key
Create a `.env` file in the project root:
```bash
ANTHROPIC_API_KEY=your_api_key_here
```

### 5. Start the server
```bash
uvicorn main:app --reload
```

The server will start at `http://127.0.0.1:8000`

### 6. Make your first API call
```bash
curl -X POST http://127.0.0.1:8000/trigger-ssbres \
  -H "Content-Type: application/json" \
  -d '{"pnr": "STU901"}'
```

## Example API Request & Response

**Request:**
```bash
POST /trigger-ssbres
Content-Type: application/json

{
  "pnr": "STU901"
}
```

**Response:**
```json
{
  "pnr": "STU901",
  "message_id": "SSBRES_2026031601_STU901",
  "disruption_type": "CANCELLATION",
  "passengers_notified": 2,
  "sms_count": 1,
  "email_count": 1,
  "reaccommodation_summary": {
    "PAX001": {
      "status": "DOWNGRADE",
      "cabin_change": "DOWNGRADE",
      "date_change": false,
      "routing_change": true
    },
    "PAX002": {
      "status": "DATE_CHANGE",
      "cabin_change": "SAME",
      "date_change": true,
      "routing_change": false
    }
  },
  "dispatch_log": [
    {
      "passenger_id": "PAX001",
      "channel": "SMS",
      "status": "SENT",
      "timestamp": "2026-03-16T09:57:16.869750"
    },
    {
      "passenger_id": "PAX002",
      "channel": "EMAIL",
      "status": "SENT",
      "timestamp": "2026-03-16T09:57:16.869760"
    }
  ],
  "validation_warnings": [],
  "needs_review": [],
  "failed_notifications": []
}
```

**Console Output (Sample SMS):**
```
[SMS] To: +919876543216 (Passenger: PAX001)
Message: STU901: Dear Arjun, we sincerely apologize for the significant inconvenience - your flight AI-661 COK-DEL has been cancelled due to technical issues. We have...
Timestamp: 2026-03-16T09:57:16.869750
```

**Console Output (Sample Email):**
```
[EMAIL] To: meera.nair@email.com (Passenger: PAX002)
Subject: URGENT: Travel Date Change - PNR STU901

Body:
Dear Meera Nair,

We sincerely apologize for the inconvenience, but we must inform you that your
flight AI-661 from Cochin (COK) to Delhi (DEL) originally scheduled for
March 16, 2026 at 2:30 PM has been cancelled due to an unexpected aircraft
technical issue. **Your travel date has changed to March 17, 2026.**

We have automatically rebooked you on the same flight AI-661 departing
March 17, 2026 at 2:30 PM in Business Class, maintaining your original cabin
preference and routing. We understand how disruptive schedule changes can be
to your travel plans, and we deeply regret any inconvenience this may cause...

Best regards,
Air India Customer Service Team
Timestamp: 2026-03-16T09:57:16.869760
```

## API Endpoints

- `POST /trigger-ssbres` - Process SSBRES message (accepts `pnr` or `raw_message`)
- `GET /pnr/{pnr}` - Retrieve full SSBRES payload for a specific PNR
- `GET /pnrs` - List all seeded PNRs in the database
- `GET /health` - Health check

## Validation & Quality Assurance

The system implements multi-layered validation:

1. **Input Validation**: Verifies SSBRES message structure, date/time formats, disruption types
2. **Impact Verification**: Cross-checks passenger analysis for completeness and cabin hierarchy logic
3. **Self-Consistency Checking**: Extracts facts from generated messages and validates against source data
4. **Message Validation**: Claude validates message accuracy and regenerates if needed
5. **Pre-Dispatch Checks**: Verifies notification completeness, formatting constraints, uniqueness

## Note

This is an **open-source, sanitized version** of a production notification system built for a **major Indian airline carrier**. The production implementation:

- Ingests SSBRES messages in **EDIFACT format** via **IBM MQ**
- Integrates with real **SMS gateways** (Twilio, Gupshup) and **email providers** (SendGrid)
- Includes comprehensive **logging, monitoring, and alerting** (Datadog, PagerDuty)
- Implements **regulatory compliance** features (GDPR, data retention policies)
- Handles **thousands of notifications per day** during disruption events

This demonstration version uses:
- **JSON** instead of EDIFACT
- **In-memory SQLite** instead of production databases
- **Console output** instead of real SMS/email dispatch
- **Mock data** for testing purposes
