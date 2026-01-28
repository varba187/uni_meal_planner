from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import List, Dict, Any


@dataclass
class UserConstraints:
    lactose_intolerant: bool
    disliked_foods: List[str]
    allergies: List[str]


@dataclass
class TrainingSession:
    label: str
    start: datetime
    end: datetime
    session_type: str  # e.g. "competition", "class", "practice"
    intensity: str # e.g. "easy", "moderate", "hard"


@dataclass
class MealSlot:
    label: str
    time: datetime
    purpose: str  # "breakfast", "lunch", "dinner", "pre_event", "snack", "recovery"
    kcal_target: float

@dataclass
class HydrationReminder:
    time: datetime
    label: str
    ml: int

def estimate_daily_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,  # "female" or "male"
    activity_level: str,  # "low", "normal", "high"
    goal: str,  # "cut", "maintain", "gain"
    sessions: List[TrainingSession],
) -> Dict[str, float]:
    # --- BMR (Mifflin-St Jeor) ---
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)

    # --- Daily activity factor (NEAT) ---
    af = {"low": 1.2, "normal": 1.35, "high": 1.5}[activity_level]
    base = bmr * af

    # --- MET table (very reasonable defaults) ---
    MET = {
        "strength": {"easy": 3.5, "moderate": 5.0, "hard": 6.0},
        "endurance": {"easy": 6.0, "moderate": 8.0, "hard": 10.0},
        "skill": {"easy": 3.0, "moderate": 4.0, "hard": 5.0},
        "mixed": {"easy": 5.0, "moderate": 7.0, "hard": 9.0},
        "tournament": {"easy": 9.0, "moderate": 11.0, "hard": 12.0},
        "class": {"easy": 1.5, "moderate": 1.5, "hard": 1.5},
    }

    # --- Session calories ---
    session_kcal = 0.0
    for s in sessions:
        hours = max(0.0, (s.end - s.start).total_seconds() / 3600.0)
        met = MET.get(s.session_type, MET["mixed"]).get(s.intensity, 6.0)
        session_kcal += met * weight_kg * hours

    # --- Goal adjustment ---
    goal_adj = {"cut": -300.0, "maintain": 0.0, "gain": 250.0}[goal]

    total_kcal = base + session_kcal + goal_adj
    total_kcal = round(total_kcal / 50) * 50  # nice rounding

    # --- Macros ---
    # Protein: 1.8 g/kg maintain/gain, 2.1 g/kg cut
    protein_g = (2.1 if goal == "cut" else 1.8) * weight_kg
    protein_kcal = protein_g * 4

    # Fat: 0.8 g/kg
    fat_g = 0.8 * weight_kg
    fat_kcal = fat_g * 9

    # Carbs: remainder
    carbs_kcal = max(0.0, total_kcal - protein_kcal - fat_kcal)
    carbs_g = carbs_kcal / 4

    # baseline: 35 ml per kg (common sports-nutrition heuristic)
    baseline_water_ml = 35 * weight_kg

    # training add-on: ~500 ml per hour of training (moderate default)
    training_hours = sum(max(0.0, (s.end - s.start).total_seconds() / 3600.0) for s in sessions)
    training_water_ml = 500 * training_hours

    # intensity bump for hard sessions
    hard_hours = sum(
        max(0.0, (s.end - s.start).total_seconds() / 3600.0)
        for s in sessions
        if s.intensity == "hard" and s.session_type != "class"
    )
    training_water_ml += 250 * hard_hours  # +250 ml per hard hour

    total_water_ml = int(round(baseline_water_ml + training_water_ml, -1))  # round to nearest 10ml


    return {
        "kcal": float(total_kcal),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
        "session_kcal": round(session_kcal, 1),
        "bmr": round(bmr, 1),
        "water_ml": total_water_ml,
        "baseline_water_ml": round(baseline_water_ml, 0),
        "training_water_ml": round(training_water_ml, 0),
    }


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute

def minutes_to_time(m: int) -> time:
    m = m % (24 * 60)
    return time(m // 60, m % 60)

def add_minutes(t: time, mins: int) -> time:
    return minutes_to_time(time_to_minutes(t) + mins)

def generate_slots(
    wake: datetime,
    bed: datetime,
    sessions: List[TrainingSession],
    target_kcal: float,
    day_type: str
) -> List[MealSlot]:
    """
    Create meal slots (breakfast, lunch, dinner, pre-event snacks, etc.)
    and assign rough kcal targets to each.
    Datetime-based version.
    """
    slots: List[MealSlot] = []

    #  intense events 
    fuel_sessions = [
    s for s in sessions
    if (
        s.session_type in ("tournament", "strength", "endurance", "mixed", "skill")
        and s.intensity in ("moderate", "hard")
    )
]

    last_intense_end = max((e.end for e in sessions), default=None)


    #  breakfast / lunch / dinner 

    # Breakfast ~1 hour after wake
    breakfast_time = wake + timedelta(hours=1)
    slots.append(
        MealSlot(label="Breakfast", time=breakfast_time, purpose="breakfast", kcal_target=0.0)
    )

    # Dinner: 1h after last intense event, else 3h before bed
    if last_intense_end:
        dinner_time = last_intense_end + timedelta(hours=1)
    else:
        dinner_time = bed - timedelta(hours=3)
    slots.append(
        MealSlot(label="Dinner", time=dinner_time, purpose="dinner", kcal_target=0.0)
    )

    # Lunch halfway between breakfast and dinner
    lunch_time = breakfast_time + (dinner_time - breakfast_time) / 2
    slots.append(
        MealSlot(label="Lunch", time=lunch_time, purpose="lunch", kcal_target=0.0)
    )

    # pre-event snacks 
    for e in fuel_sessions:
        proposed_time = e.start - timedelta(hours=1, minutes=30)

        # too early? (before wake + 30 min)
        if proposed_time < wake + timedelta(minutes=30):
            continue

        # check if within 1h of existing slots
        too_close = any(
            abs((s.time - proposed_time).total_seconds()) < 60 * 60
            for s in slots
        )

        new_time = proposed_time
        if too_close:
            new_time = proposed_time - timedelta(hours=1)
            if new_time >= wake + timedelta(minutes=10):
                too_close = any(
                    abs((s.time - new_time).total_seconds()) < 60 * 60
                    for s in slots
                )

        if too_close:
            continue
        else:
            proposed_time = new_time

        slots.append(
            MealSlot(
                label=f"Pre-{e.label} snack",
                time=proposed_time,
                purpose="pre-event",  
                kcal_target=0.0,
            )
        )

    # post-workout recovery slots (30 min after training)
    for e in fuel_sessions:
        proposed_time = e.end + timedelta(minutes=30)

        # too late (close to bed)
        if proposed_time > bed - timedelta(minutes=45):
            continue

        # too close to existing slots (< 1h)
        too_close = any(
            abs((s.time - proposed_time).total_seconds()) < 60 * 60
            for s in slots
        )
        if too_close:
            continue

        slots.append(
            MealSlot(
                label=f"Post-{e.label} recovery",
                time=proposed_time,
                purpose="post-workout",
                kcal_target=0.0,
            )
        )


    # big gap snacks
    slots.sort(key=lambda s: s.time)
    gap_snacks: List[MealSlot] = []
    for i in range(len(slots) - 1):
        current_event = slots[i]
        next_event = slots[i + 1]
        gap_hours = (next_event.time - current_event.time).total_seconds() / 3600.0

        if gap_hours > 4.0:
            snack_time = current_event.time + (next_event.time - current_event.time) / 2
            gap_snacks.append(
                MealSlot(label="Snack", time=snack_time, purpose="snack", kcal_target=0.0)
            )

    slots.extend(gap_snacks)
    slots.sort(key=lambda s: s.time)

    # --- calories assignment ---
    raw_fractions: List[float] = []

    for s in slots:
        if day_type == "tournament":
            if s.purpose == "breakfast":
                f = 0.25
            elif s.purpose == "lunch":
                f = 0.25
            elif s.purpose == "dinner":
                f = 0.25
            elif s.purpose == "pre-event":
                f = 0.12
            elif s.purpose == "post-workout":
                f = 0.10
            else:  # snack
                f = 0.06

        elif day_type == "classes":
            if s.purpose == "breakfast":
                f = 0.22
            elif s.purpose == "lunch":
                f = 0.30
            elif s.purpose == "dinner":
                f = 0.30
            elif s.purpose == "pre-event":
                f = 0.10
            elif s.purpose == "post-workout":
                f = 0.10
            else:  # snack
                f = 0.04

        else:  # rest / default
            if s.purpose == "breakfast":
                f = 0.25
            elif s.purpose == "lunch":
                f = 0.35
            elif s.purpose == "dinner":
                f = 0.30
            elif s.purpose == "pre-event":
                f = 0.05
            elif s.purpose == "post-workout":
                f = 0.00
            else:  # snack
                f = 0.05

        raw_fractions.append(f)

    sum_f = sum(raw_fractions) if raw_fractions else 1.0
    scale = 1.0 / sum_f

    for s, f in zip(slots, raw_fractions):
        s.kcal_target = target_kcal * f * scale

    return slots


def filter_foods_by_constraints(
        foods: List[Dict[str, Any]],
        constraints: UserConstraints
) -> List[Dict[str, Any]]:
    safe_foods = []
    disliked = set(constraints.disliked_foods or [])
    allergies = set(constraints.allergies or [])

    for f in foods:
        if constraints.lactose_intolerant and not f.get("lactose_free", True):
            continue
        food_allergens = set(f.get("allergens", []))
        if (allergies & food_allergens): continue
        if (f.get("name") in disliked): continue

        safe_foods.append(f)
    
    return safe_foods

def filter_foods_by_purpose(
        foods: List[Dict[str, Any]],
        purpose: str
) -> List[Dict[str, Any]]:
    if purpose == "breakfast":
        needed_tags = {"breakfast"}
    elif purpose == "lunch" or purpose == "dinner":
        needed_tags = {"lunch", "dinner", "snack", "recovery"}
    elif purpose == "pre-event":
        needed_tags = {"pre-event", "easy_digest", "quick_sugar", "snack"}
    elif purpose == "post-workout":
        needed_tags = {"dinner", "recovery", "lunch", "snack"}
    else:
        needed_tags = {"pre-event", "post-workout", "quick_sugar", "snack"}

    result = []
    for f in foods: 
        tags = set(f.get("tags", []))
        if tags & needed_tags:
            result.append(f)

    return result or foods

def build_item_entry(
        food: Dict[str, Any], 
        grams: float
) -> Dict[str, float | str]:
    factor = grams / 100.0
    return {
        "name": food["name"],
        "grams": round(grams, 1),
        "kcal": round(food["kcal_per_100g"] * factor, 1),
        "carbs": round(food["carbs_per_100g"] * factor, 1),
        "protein": round(food["protein_per_100g"] * factor, 1),
        "fat": round(food["fat_per_100g"] * factor, 1),
    }

import random
def pick_template_for_purpose(
    templates: list[dict[str, Any]],
    purpose: str,
    used_templates: set[str],
    force_new: bool = False,
    exclude_name: str | None = None,
) -> dict[str, Any] | None:
    matching = [
        t for t in templates
        if t.get("purpose") == purpose
        or (isinstance(t.get("purposes"), list) and purpose in t.get("purposes"))
    ]
    if not matching:
        return None

    # try to exclude current template when swapping
    if exclude_name:
        matching_excl = [t for t in matching if t.get("name") != exclude_name]
    else:
        matching_excl = matching

    if force_new:
        pool = matching_excl if matching_excl else matching
        return random.choice(pool)

    unused = [t for t in matching_excl if t.get("name") not in used_templates]
    pool = unused if unused else matching_excl
    return random.choice(pool)

def default_grams_for_role(role: str) -> float:
    role = role.lower()
    if role in ("carb", "base", "grain"):
        return 180.0
    if role in ("protein",):
        return 140.0
    if role in ("fat",):
        return 20.0
    if role in ("fruit",):
        return 150.0
    if role in ("dairy",):
        return 170.0
    if role in ("veg", "vegetable"):
        return 150.0
    if role in ("drink",):
        return 500.0
    return 120.0


def plan_meal_for_slot(
    slot: MealSlot,
    foods: List[Dict[str, Any]],
    constraints: UserConstraints,
    used_today: set,
    templates: List[Dict[str, Any]],
    used_templates: set[str],
    force_new_template: bool = False,
    exclude_name: str | None = None,
) -> Dict[str, Any]:
    """
    For a given slot, choose foods and portion sizes that hit kcal_target
    and respect constraints.
    Returns a structure containing items, macros, and a note.
    """
    def pick(cands):
        for f in cands:
            if f["name"] not in used_today:
                used_today.add(f["name"])
                return f
        # fallback if everything already used
        f = cands[0]
        used_today.add(f["name"])
        return f


    safe_foods = filter_foods_by_constraints(foods, constraints)
    if not safe_foods:
        return {
            "items": [],
            "totals": {"kcal": 0, "carbs": 0, "protein": 0, "fat": 0},
            "note": "No foods available that match your constraints."
        }
    
    purpose_foods = filter_foods_by_purpose(safe_foods, slot.purpose)

    if templates:
        foods_by_name = {f["name"]: f for f in safe_foods}

        template = pick_template_for_purpose(
            templates=templates,
            purpose=slot.purpose,
            used_templates=used_templates,
            force_new=force_new_template,
            exclude_name=exclude_name,
        )

        if template:
            # inside plan_meal_for_slot, after `if template:`
            base_items = []
            ok = True

            for it in template.get("items", []):
                food_name = it.get("name")
                role = it.get("role", "carb")
                grams = float(it.get("grams", default_grams_for_role(role)))

                food = foods_by_name.get(food_name)
                if not food:
                    ok = False
                    break

                base_items.append((food, grams))

            if ok and base_items:
                base_entries = [build_item_entry(food, grams) for food, grams in base_items]
                base_kcal = sum(e["kcal"] for e in base_entries)

                if base_kcal > 0:
                    scale = slot.kcal_target / base_kcal

                    items = []
                    for food, grams in base_items:
                        g2 = max(20.0, round((grams * scale) / 10.0) * 10.0)
                        items.append(build_item_entry(food, g2))

                    totals = {
                        "kcal": round(sum(i["kcal"] for i in items), 1),
                        "carbs": round(sum(i["carbs"] for i in items), 1),
                        "protein": round(sum(i["protein"] for i in items), 1),
                        "fat": round(sum(i["fat"] for i in items), 1),
                    }

                    tname = template.get("name", "template")
                    used_templates.add(tname)

                    return {
                        "items": items,
                        "totals": totals,
                        "note": f"{tname} (template).",
                        "template": tname,  # <-- IMPORTANT for swap exclude
                    }



    carb_candidates = sorted(purpose_foods, key=lambda f:f.get("carbs_per_100g", 0), reverse = True)
    protein_candidates = sorted(purpose_foods, key=lambda f:f.get("protein_per_100g", 0), reverse = True)
    fat_candidates = sorted(purpose_foods, key=lambda f:f.get("fat_per_100g", 0), reverse = True)

    carb_base = pick(carb_candidates[:10])
    protein_source = pick(protein_candidates[:10])
    fat_source = pick(fat_candidates[:10])


    K = slot.kcal_target

    items: List[Dict[str, Any]] = []

    if (slot.purpose in ("pre-event", "snack", "post-workout")):
        carb_k = K * 0.8
        second_k = K * 0.2

        carb_grams = carb_k / carb_base["kcal_per_100g"] * 100.0
        second_food = protein_source if slot.purpose in ("pre-event", "post-workout") else fat_source
        second_grams = second_k / second_food["kcal_per_100g"] * 100.0

        # making proportions
        carb_grams = max(20.0, round(carb_grams/10.0)*10.0)
        second_grams = max(20.0, round(second_grams/10.0)*10.0)

        items.append(build_item_entry(carb_base, carb_grams))
        if (second_food["name"]!= carb_base["name"]):
            items.append(build_item_entry(second_food, second_grams))
    else:
        carb_k = K * 0.6
        protein_k = K * 0.25 
        fat_k = K * 0.15

        carb_grams = carb_k / carb_base["kcal_per_100g"] * 100.0
        protein_grams = protein_k / protein_source["kcal_per_100g"] * 100.0
        fat_grams = fat_k / fat_source["kcal_per_100g"] * 100.0
        items.append(build_item_entry(carb_base, carb_grams))
        if (protein_source["name"]!= carb_base["name"]):
            items.append(build_item_entry(protein_source, protein_grams))
        if (fat_source["name"]!= carb_base["name"] and fat_source["name"] != protein_source["name"]):
            items.append(build_item_entry(fat_source, fat_grams))
    
    total_kcal = sum(i["kcal"] for i in items)
    total_carbs = sum(i["carbs"] for i in items)
    total_protein = sum(i["protein"] for i in items)
    total_fat = sum(i["fat"] for i in items)

    totals = {
        "kcal": round(total_kcal, 1),
        "carbs": round(total_carbs, 1),
        "protein": round(total_protein, 1),
        "fat": round(total_fat, 1) 
    }

    if slot.purpose == "breakfast":
        note = "High-carb breakfast with some protein and fat to fuel the morning."
    elif slot.purpose == "lunch":
        note = "Balanced lunch for sustained energy through the day."
    elif slot.purpose == "dinner":
        note = "Evening meal with extra protein to support recovery."
    elif slot.purpose == "pre-event":
        note = "Mostly fast-digesting carbs before your session to give quick energy."
    elif slot.purpose == "post-workout":
        note = "Post-workout recovery: carbs to refill glycogen + protein to support muscle repair."
    else:  # snack
        note = "Quick snack to top up energy between meals."

    return {
        "items": items,
        "totals": totals,
        "note": note
    }

def guess_role(food: Dict[str, Any]) -> str:
    c = food.get("carbs_per_100g", 0)
    p = food.get("protein_per_100g", 0)
    f = food.get("fat_per_100g", 0)
    if p >= c and p >= f:
        return "protein"
    if f >= c and f >= p:
        return "fat"
    return "carb"

def generate_hydration_reminders(
    wake: datetime,
    bed: datetime,
    sessions: List[TrainingSession],
    total_water_ml: float,
    interval_minutes: int = 120,  # every 2 hours
) -> List[HydrationReminder]:
    start = wake + timedelta(minutes=30)
    end = bed - timedelta(minutes=45)
    if end <= start:
        return []


    reminders: List[HydrationReminder] = []
    t = start
    while t <= end:
        reminders.append(HydrationReminder(time=t, label="Drink water", ml=0))
        t += timedelta(minutes=interval_minutes)

    # add training-biased reminders
    for s in sessions:
        if s.session_type == "class":
            continue
        reminders.append(HydrationReminder(time=s.start - timedelta(minutes=20), label=f"Hydrate before {s.label}", ml=0))
        reminders.append(HydrationReminder(time=s.end + timedelta(minutes=15), label=f"Hydrate after {s.label}", ml=0))

    # de-dupe times within 20 minutes (keep earliest)
    reminders.sort(key=lambda r: r.time)
    deduped: List[HydrationReminder] = []
    for r in reminders:
        if not deduped:
            deduped.append(r)
            continue
        if (r.time - deduped[-1].time).total_seconds() < 20 * 60:
            continue
        deduped.append(r)

    if deduped:
        per = int(round(total_water_ml / len(deduped), -1))  # nearest 10 ml
        for r in deduped:
            r.ml = max(100, per)  # minimum 100 ml reminder

    return deduped

def generate_daily_plan(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,  # "female" or "male"
    activity_level: str,  # "low", "normal", "high"
    goal: str,  # "cut", "maintain", "gain"
    day_type: str,
    wake: datetime,
    bed: datetime,
    sessions: List[TrainingSession],
    constraints: UserConstraints,
    foods: List[Dict[str, Any]],
    templates: List[Dict[str, Any]],
    force_swap: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    High-level orchestration: estimate calories, create slots, plan each meal,
    and return a sorted list of meals for the day.
    """
    targets = estimate_daily_targets(weight_kg, height_cm, age, sex, activity_level, goal, sessions)
    target_kcal = targets["kcal"]
    slots = generate_slots(wake, bed, sessions, target_kcal, day_type)
    used_templates = set()

    meals = []
    used_today = set()
    for slot in slots:
        force_new_template = False
        exclude_template = None

        if (force_swap and force_swap.get("purpose") == slot.purpose and force_swap.get("time") == slot.time.isoformat()
        ):
            force_new_template = True
            exclude_template = force_swap.get("exclude_template")


        meal_plan = plan_meal_for_slot(
            slot, foods, constraints, used_today,
            templates, used_templates,
            force_new_template=force_new_template,
            exclude_name=exclude_template,
        )

        meals.append({
            "time": slot.time,
            "label": slot.label,
            "purpose": slot.purpose,
            "kcal_target": slot.kcal_target,
            **meal_plan
        })

    meals.sort(key=lambda m: m["time"])
    reminders = generate_hydration_reminders(
        wake=wake,
        bed=bed,
        sessions=sessions,
        total_water_ml=targets["water_ml"],
        interval_minutes=120,
    )
    return {"targets": targets, "meals": meals, "hydration": reminders}

