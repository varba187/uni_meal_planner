from datetime import datetime, timedelta
from logic.planning import estimate_daily_targets, TrainingSession

def test_estimate_daily_targets_returns_expected_keys():
    sessions = [
        TrainingSession(
            label="Practice",
            start=datetime(2025, 12, 24, 18, 0),
            end=datetime(2025, 12, 24, 20, 0),
            session_type="mixed",
            intensity="hard",
        )
    ]

    t = estimate_daily_targets(
        weight_kg=60,
        height_cm=160,
        age=19,
        sex="female",
        activity_level="normal",
        goal="maintain",
        sessions=sessions,
    )

    for k in ["kcal", "protein_g", "carbs_g", "fat_g", "water_ml", "bmr", "session_kcal"]:
        assert k in t

    assert t["kcal"] > 0
    assert t["protein_g"] > 0
    assert t["fat_g"] > 0
    assert t["water_ml"] > 0

def test_harder_or_longer_sessions_increase_session_kcal():
    base_sessions = [
        TrainingSession(
            label="Easy",
            start=datetime(2025, 12, 24, 18, 0),
            end=datetime(2025, 12, 24, 19, 0),
            session_type="mixed",
            intensity="easy",
        )
    ]
    hard_sessions = [
        TrainingSession(
            label="Hard",
            start=datetime(2025, 12, 24, 18, 0),
            end=datetime(2025, 12, 24, 19, 0),
            session_type="mixed",
            intensity="hard",
        )
    ]

    t_easy = estimate_daily_targets(60, 160, 19, "female", "normal", "maintain", base_sessions)
    t_hard = estimate_daily_targets(60, 160, 19, "female", "normal", "maintain", hard_sessions)

    assert t_hard["session_kcal"] > t_easy["session_kcal"]
