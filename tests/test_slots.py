from datetime import datetime, timedelta
from logic.planning import generate_slots, TrainingSession

def test_generate_slots_sorted_and_has_main_meals():
    wake = datetime(2025, 12, 24, 7, 0)
    bed = datetime(2025, 12, 24, 23, 0)
    sessions = []

    slots = generate_slots(wake, bed, sessions, target_kcal=2000, day_type="rest")

    purposes = [s.purpose for s in slots]
    assert "breakfast" in purposes
    assert "lunch" in purposes
    assert "dinner" in purposes

    # must be sorted by time
    times = [s.time for s in slots]
    assert times == sorted(times)

def test_generate_slots_creates_pre_event_for_intense_sessions():
    wake = datetime(2025, 12, 24, 7, 0)
    bed = datetime(2025, 12, 24, 23, 0)

    sessions = [
        TrainingSession(
            label="Practice",
            start=datetime(2025, 12, 24, 18, 0),
            end=datetime(2025, 12, 24, 20, 0),
            session_type="skill",
            intensity="hard",
        )
    ]

    slots = generate_slots(wake, bed, sessions, target_kcal=2000, day_type="classes")
    purposes = [s.purpose for s in slots]

    assert "pre-event" in purposes
