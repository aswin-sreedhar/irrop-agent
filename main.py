# FastAPI entry point for the IRROP notification agent
# Handles HTTP endpoints for triggering notifications from SBRRES reaccommodation messages

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from data.mock_db import get_pnr, get_all_pnrs
from graph.agent import irrop_graph
from graph.state import IRROPState

# Initialize FastAPI app
app = FastAPI(
    title="IRROP Agent - SBRRES Processor",
    description="AI-powered reaccommodation notification system for airline SBRRES messages",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request models
class TriggerSBRRESRequest(BaseModel):
    pnr: Optional[str] = None  # Fetch from database
    raw_message: Optional[dict] = None  # Or provide custom payload


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    print("\n" + "="*60)
    print("IRROP Agent - SBRRES Processor running")
    print("="*60 + "\n")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/pnr/{pnr}")
async def get_pnr_details(pnr: str):
    """Get the raw SBRRES message for a given PNR"""
    message = get_pnr(pnr)

    if not message:
        raise HTTPException(status_code=404, detail=f"PNR {pnr} not found")

    return message


@app.get("/pnrs")
async def list_all_pnrs():
    """List all seeded PNRs in the database"""
    return {"pnrs": get_all_pnrs()}


@app.post("/trigger-ssbres")
async def trigger_ssbres(request: TriggerSBRRESRequest):
    """
    Trigger SBRRES reaccommodation notification workflow.

    Accepts either a PNR (fetches from database) or a raw SBRRES message,
    runs the LangGraph agent to analyze reaccommodations and dispatch
    personalized notifications to all passengers.
    """
    # Determine message source
    if request.raw_message:
        raw_message = request.raw_message
    elif request.pnr:
        raw_message = get_pnr(request.pnr)
        if not raw_message:
            raise HTTPException(status_code=404, detail=f"PNR {request.pnr} not found")
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'pnr' or 'raw_message'"
        )

    # Initialize state for LangGraph
    initial_state: IRROPState = {
        "raw_message": raw_message,
        "pnr": raw_message.get("pnr", ""),
        "passengers": [],
        "original_itinerary": [],
        "new_itinerary": [],
        "disruption": {},
        "passenger_analysis": {},
        "generated_messages": {},
        "validated_messages": {},
        "sms_notifications": [],
        "email_notifications": [],
        "dispatch_log": [],
        "failed_notifications": [],
        "validation_warnings": [],
        "needs_review": [],
        "error": None
    }

    # Run the LangGraph workflow
    try:
        final_state = irrop_graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow error: {str(e)}")

    # Check for errors in final state
    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])

    # Build summary response
    dispatch_log = final_state.get("dispatch_log", [])
    passenger_analysis = final_state.get("passenger_analysis", {})
    sms_count = sum(1 for log in dispatch_log if log["channel"] == "SMS")
    email_count = sum(1 for log in dispatch_log if log["channel"] == "EMAIL")

    # Summarize reaccommodation statuses
    reaccommodation_summary = {}
    for passenger_id, analysis in passenger_analysis.items():
        status = analysis.get("reaccommodation_status", "UNKNOWN")
        reaccommodation_summary[passenger_id] = {
            "status": status,
            "cabin_change": analysis.get("cabin_change", "NONE"),
            "date_change": analysis.get("date_change", False),
            "routing_change": analysis.get("routing_change", False)
        }

    return {
        "pnr": final_state.get("pnr"),
        "message_id": raw_message.get("message_id"),
        "disruption_type": final_state.get("disruption", {}).get("type"),
        "passengers_notified": len(dispatch_log),
        "sms_count": sms_count,
        "email_count": email_count,
        "reaccommodation_summary": reaccommodation_summary,
        "dispatch_log": dispatch_log,
        "validation_warnings": final_state.get("validation_warnings", []),
        "needs_review": final_state.get("needs_review", []),
        "failed_notifications": final_state.get("failed_notifications", [])
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
