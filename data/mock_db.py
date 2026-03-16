# Mock PNR database for SBRRES message storage
# Stores full SBRRES JSON payloads for reaccommodation scenarios

from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json

Base = declarative_base()


class PNRRecord(Base):
    __tablename__ = "pnr_records"

    pnr = Column(String, primary_key=True)
    message_id = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)  # Full SBRRES JSON message
    created_at = Column(String, nullable=False)


# Create in-memory SQLite database
engine = create_engine("sqlite:///:memory:", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


def seed_database():
    """Seed the database with realistic SBRRES messages"""

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    # Scenario 1: COK→DEL cancelled, rerouted via BOM with cabin downgrade for PAX001, date change for PAX002
    pnr1_payload = {
        "message_id": "SBRRES_2026031601_STU901",
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
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "14:30",
                "arrival_date": now.strftime("%Y-%m-%d"),
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
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "16:15",
                "arrival_date": now.strftime("%Y-%m-%d"),
                "arrival_time": "18:30",
                "cabin": "Economy",
                "passengers": ["PAX001"]
            },
            {
                "segment_id": "SEG003",
                "flight_number": "AI-864",
                "origin": "BOM",
                "destination": "DEL",
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "20:00",
                "arrival_date": now.strftime("%Y-%m-%d"),
                "arrival_time": "22:15",
                "cabin": "Economy",
                "passengers": ["PAX001"]
            },
            {
                "segment_id": "SEG004",
                "flight_number": "AI-661",
                "origin": "COK",
                "destination": "DEL",
                "departure_date": tomorrow.strftime("%Y-%m-%d"),
                "departure_time": "14:30",
                "arrival_date": tomorrow.strftime("%Y-%m-%d"),
                "arrival_time": "17:45",
                "cabin": "Business",
                "passengers": ["PAX002"]
            }
        ]
    }

    # Scenario 2: DEL→BOM delayed 180 minutes, both passengers on same new flight
    pnr2_payload = {
        "message_id": "SBRRES_2026031602_YZA567",
        "pnr": "YZA567",
        "booking_reference": "YZA567",
        "disruption": {
            "type": "DELAY",
            "reason": "CREW_UNAVAILABILITY",
            "affected_segments": ["AI-101"],
            "delay_minutes": 180
        },
        "passengers": [
            {
                "passenger_id": "PAX003",
                "first_name": "Rohan",
                "last_name": "Gupta",
                "email": "rohan.gupta@email.com",
                "phone": "+919876543218",
                "notification_preference": "SMS"
            },
            {
                "passenger_id": "PAX004",
                "first_name": "Priya",
                "last_name": "Gupta",
                "email": "priya.gupta@email.com",
                "phone": "+919876543219",
                "notification_preference": "EMAIL"
            }
        ],
        "original_itinerary": [
            {
                "segment_id": "SEG005",
                "flight_number": "AI-101",
                "origin": "DEL",
                "destination": "BOM",
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "10:00",
                "arrival_date": now.strftime("%Y-%m-%d"),
                "arrival_time": "12:15",
                "cabin": "Economy",
                "passengers": ["PAX003", "PAX004"]
            }
        ],
        "new_itinerary": [
            {
                "segment_id": "SEG006",
                "flight_number": "AI-103",
                "origin": "DEL",
                "destination": "BOM",
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "13:00",
                "arrival_date": now.strftime("%Y-%m-%d"),
                "arrival_time": "15:15",
                "cabin": "Economy",
                "passengers": ["PAX003", "PAX004"]
            }
        ]
    }

    # Scenario 3: BLR→HYD→DEL, first leg diverted to MAA, reaccommodated on direct BLR→DEL with upgrade
    pnr3_payload = {
        "message_id": "SBRRES_2026031603_VWX234",
        "pnr": "VWX234",
        "booking_reference": "VWX234",
        "disruption": {
            "type": "DIVERSION",
            "reason": "WEATHER_AT_DESTINATION",
            "affected_segments": ["AI-522"],
            "diversion_airport": "MAA"
        },
        "passengers": [
            {
                "passenger_id": "PAX005",
                "first_name": "Kavya",
                "last_name": "Desai",
                "email": "kavya.desai@email.com",
                "phone": "+919876543217",
                "notification_preference": "EMAIL"
            }
        ],
        "original_itinerary": [
            {
                "segment_id": "SEG007",
                "flight_number": "AI-522",
                "origin": "BLR",
                "destination": "HYD",
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "08:30",
                "arrival_date": now.strftime("%Y-%m-%d"),
                "arrival_time": "09:45",
                "cabin": "Economy",
                "passengers": ["PAX005"]
            },
            {
                "segment_id": "SEG008",
                "flight_number": "AI-544",
                "origin": "HYD",
                "destination": "DEL",
                "departure_date": now.strftime("%Y-%m-%d"),
                "departure_time": "11:00",
                "arrival_date": now.strftime("%Y-%m-%d"),
                "arrival_time": "13:15",
                "cabin": "Economy",
                "passengers": ["PAX005"]
            }
        ],
        "new_itinerary": [
            {
                "segment_id": "SEG009",
                "flight_number": "AI-504",
                "origin": "BLR",
                "destination": "DEL",
                "departure_date": tomorrow.strftime("%Y-%m-%d"),
                "departure_time": "06:00",
                "arrival_date": tomorrow.strftime("%Y-%m-%d"),
                "arrival_time": "08:45",
                "cabin": "Business",
                "passengers": ["PAX005"]
            }
        ]
    }

    # Store records
    records = [
        PNRRecord(
            pnr="STU901",
            message_id="SBRRES_2026031601_STU901",
            payload=pnr1_payload,
            created_at=now.isoformat()
        ),
        PNRRecord(
            pnr="YZA567",
            message_id="SBRRES_2026031602_YZA567",
            payload=pnr2_payload,
            created_at=now.isoformat()
        ),
        PNRRecord(
            pnr="VWX234",
            message_id="SBRRES_2026031603_VWX234",
            payload=pnr3_payload,
            created_at=now.isoformat()
        )
    ]

    session.add_all(records)
    session.commit()


def get_pnr(pnr: str):
    """Returns the full SBRRES message for a given PNR"""
    record = session.query(PNRRecord).filter(PNRRecord.pnr == pnr).first()
    return record.payload if record else None


def get_all_pnrs():
    """Returns list of all seeded PNRs"""
    records = session.query(PNRRecord).all()
    return [{"pnr": r.pnr, "message_id": r.message_id, "created_at": r.created_at} for r in records]


# Seed the database on module import
seed_database()
