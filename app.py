import json
from datetime import datetime, time 

import streamlit as st
import pandas as pd


from logic.planning import (
    UserConstraints,
    TrainingSession,
    generate_daily_plan
)

# ---- session state init (must be before any reads) ----
if "sessions" not in st.session_state:
    st.session_state.sessions = []

if "generate_now" not in st.session_state:
    st.session_state.generate_now = False

if "force_swap" not in st.session_state:
    st.session_state.force_swap = None

def default_sessions_for_day(selected_date, day_type: str):
    # only used on "Reset to template"
    return get_template_sessions(selected_date, day_type)

def build_datetime(date, t:time) -> datetime:
    return datetime.combine(date, t)

def get_template_sessions(selected_date, day_type: str):
    sessions = []

    if day_type == "tournament":
        sessions.append(
            TrainingSession(
                label="Competition Block 1",
                start=build_datetime(selected_date, time(9, 0)),
                end=build_datetime(selected_date, time(11, 0)),
                session_type="tournament",
                intensity="hard",
            )
        )
        sessions.append(
            TrainingSession(
                label="Competition Block 2",
                start=build_datetime(selected_date, time(14, 0)),
                end=build_datetime(selected_date, time(18, 0)),
                session_type="tournament",
                intensity="hard",
            )
        )

    elif day_type == "classes":
        # classes affect timing, training affects fueling
        sessions.append(
            TrainingSession(
                label="Classes",
                start=build_datetime(selected_date, time(10, 0)),
                end=build_datetime(selected_date, time(15, 0)),
                session_type="class",
                intensity="easy",
            )
        )
        sessions.append(
            TrainingSession(
                label="Clases",
                start=build_datetime(selected_date, time(19, 0)),
                end=build_datetime(selected_date, time(21, 0)),
                session_type="skill",   # or "strength"/"endurance"/"mixed"
                intensity="moderate",
            )
        )

    elif day_type == "rest":
        # optional: still include classes on rest days if you want
        sessions.append(
            TrainingSession(
                label="Classes",
                start=build_datetime(selected_date, time(10, 0)),
                end=build_datetime(selected_date, time(15, 0)),
                session_type="class",
                intensity="easy",
            )
        )

    return sessions


# UI

st.set_page_config(page_title="Uni Meal Planner", page_icon="🍱", layout="wide")

st.markdown("""
<style>
/* tighten page width + spacing */
.block-container { padding-top: 2.2rem; max-width: 1100px; }

/* nice section headers */
h1, h2, h3 { letter-spacing: -0.02em; }

/* card */
.card {
  background: white;
  border: 1px solid rgba(17,24,39,.08);
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 8px 24px rgba(17,24,39,.06);
  margin-bottom: 14px;
}

/* pill badges */
.pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(17,24,39,.10);
  background: #f3f4f6;
  margin-left: 10px;
}
.pill-green { background: #ecfdf5; border-color:#bbf7d0; color:#065f46; }
.pill-blue  { background: #eff6ff; border-color:#bfdbfe; color:#1e40af; }
.pill-amber { background: #fffbeb; border-color:#fde68a; color:#92400e; }

/* make dataframe look less plain */
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid rgba(17,24,39,.08); }

/* remove the weird top padding in sidebar */
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)


st.title("🍱 Uni Meal Planner (Student Athlete Edition)")
st.markdown("Plan your day of **meals and snacks** around classes, practice, or a tournament.")

# Sidebar
st.sidebar.header("Uni Meal Planner")

tab_setup, tab_sessions, tab_diet = st.sidebar.tabs(["Setup", "Sessions", "Diet"])

with tab_setup:
    with st.expander("Body Info & Goals", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            weight_kg = st.number_input("Weight (kg)", 30.0, 120.0, 60.0, 1.0)
            height_cm = st.number_input("Height (cm)", 130.0, 220.0, 160.0, 1.0)
        with c2:
            age = st.number_input("Age", 12, 80, 19, 1)
            sex = st.selectbox("Sex", ["female", "male"], index=0)

        goal = st.selectbox("Goal", ["maintain", "cut", "gain"], index=0)

    with st.expander("Schedule", expanded=True):
        date = st.date_input("Date", datetime.now().date())
        c1, c2 = st.columns(2)
        with c1:
            wake_time = st.time_input("Wake", time(6, 30))
        with c2:
            bed_time = st.time_input("Bed", time(23, 0))

        activity_level = st.selectbox(
            "Daily activity (outside training)",
            ["low", "normal", "high"],
            index=1,
            help="Low = mostly sitting; Normal = lots of walking; High = very active day.",
        )

        day_type = st.selectbox("Day type", ["tournament", "classes", "rest"], index=0)

with tab_sessions:
    st.caption("Add training/classes/competition blocks. These drive fueling + calories.")

    # Quick actions
    cA, cB = st.columns(2)
    with cA:
        if st.button("Reset to template", use_container_width=True):
            st.session_state.sessions = default_sessions_for_day(date, day_type)
    with cB:
        if st.button("Clear", use_container_width=True):
            st.session_state.sessions = []

    with st.expander("➕ Add session", expanded=True):
        new_label = st.text_input("Label", value="Training")
        c1, c2 = st.columns(2)
        with c1:
            new_start = st.time_input("Start", value=time(19, 0), key="new_start")
        with c2:
            new_end = st.time_input("End", value=time(21, 0), key="new_end")

        c1, c2 = st.columns(2)
        with c1:
            new_type = st.selectbox(
                "Type",
                ["class", "skill", "strength", "endurance", "mixed", "tournament"],
                index=1,
                key="new_type",
            )
        with c2:
            new_intensity = st.selectbox(
                "Intensity",
                ["easy", "moderate", "hard"],
                index=1,
                key="new_intensity",
            )

        if st.button("Add session", use_container_width=True):
            st.session_state.sessions.append(
                TrainingSession(
                    label=new_label,
                    start=build_datetime(date, new_start),
                    end=build_datetime(date, new_end),
                    session_type=new_type,
                    intensity=new_intensity,
                )
            )

    # Edit existing sessions
    if st.session_state.sessions:
        st.markdown("**Current sessions**")
        remove_idx = None

        for i, s in enumerate(st.session_state.sessions):
            with st.expander(f"{i+1}) {s.label}", expanded=False):
                lbl = st.text_input("Label", value=s.label, key=f"lbl_{i}")

                c1, c2 = st.columns(2)
                with c1:
                    st_time = st.time_input("Start", value=s.start.time(), key=f"st_{i}")
                with c2:
                    en_time = st.time_input("End", value=s.end.time(), key=f"en_{i}")

                c1, c2 = st.columns(2)
                with c1:
                    typ = st.selectbox(
                        "Type",
                        ["class", "skill", "strength", "endurance", "mixed", "tournament"],
                        index=["class","skill","strength","endurance","mixed","tournament"].index(s.session_type),
                        key=f"typ_{i}",
                    )
                with c2:
                    inten = st.selectbox(
                        "Intensity",
                        ["easy", "moderate", "hard"],
                        index=["easy","moderate","hard"].index(s.intensity),
                        key=f"inten_{i}",
                    )

                st.session_state.sessions[i] = TrainingSession(
                    label=lbl,
                    start=build_datetime(date, st_time),
                    end=build_datetime(date, en_time),
                    session_type=typ,
                    intensity=inten,
                )

                if st.button("Remove", key=f"rm_{i}", use_container_width=True):
                    remove_idx = i

        if remove_idx is not None:
            st.session_state.sessions.pop(remove_idx)
            st.rerun()
    else:
        st.info("No sessions yet — add one above or reset to a template.")

with tab_diet:
    lactose_intolerant = st.checkbox("Lactose intolerant", value=True)

    disliked_foods_input = st.text_input(
        "Disliked foods (comma-separated)",
        value="",
        help="Example: tuna, broccoli",
    )
    disliked_foods = [x.strip() for x in disliked_foods_input.split(",") if x.strip()]

    allergies_input = st.text_input(
        "Allergies (comma-separated, match tags/allergens)",
        value="",
        help="Example: peanuts, tree_nuts, gluten",
    )
    allergies = [x.strip() for x in allergies_input.split(",") if x.strip()]

st.sidebar.divider()

# ---- Generate button logic ----
generate_clicked = st.sidebar.button("Generate plan", use_container_width=True)
generate = generate_clicked or st.session_state.generate_now
st.sidebar.caption("Add training/classes/competition blocks. These drive fueling + calories.")

# ---- Run generation if triggered ----
if generate:
    # consume the trigger so it doesn't loop forever
    st.session_state.generate_now = False

    wake_dt = build_datetime(date, wake_time)
    bed_dt  = build_datetime(date, bed_time)

    constraints = UserConstraints(
        lactose_intolerant=lactose_intolerant,
        disliked_foods=disliked_foods,
        allergies=allergies,
    )

    try:
        with open("data/foods.json", "r") as f:
            foods = json.load(f)
    except FileNotFoundError:
        st.error("Could not find data/foods.json. Make sure it exists.")
        st.stop()

    try:
        with open("data/templates.json", "r") as f:
            templates = json.load(f)
    except FileNotFoundError:
        st.error("Could not find data/templates.json. Make sure it exists.")
        st.stop()

    sessions = st.session_state.sessions

    bad = [s for s in sessions if s.end <= s.start]
    if bad:
        st.error("One or more sessions has End <= Start. Fix the times.")
        st.stop()

    force_swap = st.session_state.force_swap  # could be None

    try:
        result = generate_daily_plan(
            weight_kg=weight_kg,
            height_cm=height_cm,
            age=age,
            sex=sex,
            activity_level=activity_level,
            goal=goal,
            day_type=day_type,
            wake=wake_dt,
            bed=bed_dt,
            sessions=sessions,
            constraints=constraints,
            foods=foods,
            templates=templates,
            force_swap=force_swap,
        )
    except Exception as e:
        st.error(f"Error while generating plan: {e}")
        st.stop()

    # clear swap after consuming it
    st.session_state.force_swap = None

    # persist latest result so it stays visible on refresh
    st.session_state.generated = result


# ---- Display the last generated result (if it exists) ----
if "generated" not in st.session_state:
    st.info("Set your parameters in the sidebar and click **Generate plan.**")
    st.stop()

result = st.session_state.generated
meals = result["meals"]
targets = result["targets"]
hydration = result.get("hydration", [])

# daily totals from generated meals
total_kcal = round(sum(m["kcal_target"] for m in meals))

actual_protein = round(sum(m.get("totals", {}).get("protein", 0) for m in meals), 1)
actual_carbs   = round(sum(m.get("totals", {}).get("carbs", 0) for m in meals), 1)
actual_fat     = round(sum(m.get("totals", {}).get("fat", 0) for m in meals), 1)

# targets from estimate_daily_targets
target_protein = targets.get("protein_g", 0)
target_carbs   = targets.get("carbs_g", 0)
target_fat     = targets.get("fat_g", 0)

training_burn = targets.get("session_kcal", 0)
bmr = targets.get("bmr", 0)

# ---- Display overview ----
st.subheader("Daily Overview")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Calories", f"{total_kcal} kcal")
c2.metric("Training burn", f"{round(training_burn)} kcal")
c3.metric("BMR", f"{round(bmr)} kcal")
c4.metric("Goal", goal)

c1, c2, c3 = st.columns(3)
c1.metric("Protein", f"{actual_protein} g", f"target {target_protein} g")
c2.metric("Carbs", f"{actual_carbs} g", f"target {target_carbs} g")
c3.metric("Fat", f"{actual_fat} g", f"target {target_fat} g")

# ---- Export ----
export_rows = []
for m in meals:
    export_rows.append({
        "time": m["time"].strftime("%H:%M"),
        "label": m["label"],
        "purpose": m.get("purpose", ""),
        "kcal_target": round(m["kcal_target"], 1),
        "items": ", ".join([f"{it['name']} ({it['grams']}g)" for it in m.get("items", [])]),
        "kcal_actual": m.get("totals", {}).get("kcal", 0),
        "carbs_g": m.get("totals", {}).get("carbs", 0),
        "protein_g": m.get("totals", {}).get("protein", 0),
        "fat_g": m.get("totals", {}).get("fat", 0),
        "note": m.get("note", ""),
    })

export_df = pd.DataFrame(export_rows)

st.markdown("### Export")
colA, colB = st.columns(2)

with colA:
    st.download_button(
        "⬇️ Download CSV",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name=f"meal_plan_{date}.csv",
        mime="text/csv",
    )

with colB:
    st.download_button(
        "⬇️ Download JSON",
        data=json.dumps({"targets": targets, "meals": meals}, default=str, indent=2).encode("utf-8"),
        file_name=f"meal_plan_{date}.json",
        mime="application/json",
    )

water_L = targets["water_ml"] / 1000
st.write(f"**Hydration target:** `{water_L:.1f} L`")
st.caption(
    f"Water baseline: {targets['baseline_water_ml']:.0f} ml • "
    f"Training add-on: {targets['training_water_ml']:.0f} ml"
)

# ---- Hydration reminders ----
st.markdown("___")
st.subheader("Today’s Plan")
st.subheader("Hydration reminders")

if hydration:
    dfw = pd.DataFrame([{
        "Time": r.time.strftime("%H:%M"),
        "Reminder": r.label,
        "Amount (ml)": r.ml,
    } for r in hydration])
    st.dataframe(dfw, hide_index=True, use_container_width=True)
else:
    st.caption("No hydration reminders for this schedule.")

# ---- Meals + Swap buttons ----
for i, meal in enumerate(meals):
    time_str = meal["time"].strftime("%H:%M")
    totals = meal.get("totals", {})
    items = meal.get("items", [])
    purpose = meal.get("purpose", "")

    badge = {
        "breakfast": "pill-blue",
        "lunch": "pill-green",
        "dinner": "pill-green",
        "pre-event": "pill-amber",
        "snack": "pill-amber",
        "post-workout": "pill-amber",
    }.get(purpose, "pill")

    st.markdown(f"""
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:baseline;">
        <div style="font-size:20px; font-weight:700;">
          {time_str} — {meal['label']}
          <span class="pill {badge}">{purpose}</span>
        </div>
        <div class="pill pill-green">
          target: {round(meal['kcal_target'])} kcal
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if items:
        df = pd.DataFrame(items).rename(columns={
            "name": "Food",
            "grams": "Grams",
            "kcal": "kcal",
            "carbs": "Carbs (g)",
            "protein": "Protein (g)",
            "fat": "Fat (g)",
        })
        df = df[["Food", "Grams", "kcal", "Carbs (g)", "Protein (g)", "Fat (g)"]]
        st.dataframe(df, hide_index=True, use_container_width=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Kcal", f"{totals.get('kcal',0)} kcal")
        c2.metric("Carbs", f"{totals.get('carbs',0)} g")
        c3.metric("Protein", f"{totals.get('protein',0)} g")
        c4.metric("Fat", f"{totals.get('fat',0)} g")

    # IMPORTANT: stable unique key
    swap_key = f"swap_{meal['time'].isoformat()}_{meal['label']}_{i}"

    if st.button("🔄 Swap this meal", key=swap_key):
        st.session_state.force_swap = {
            "purpose": meal["purpose"],
            "time": meal["time"].isoformat(),          # must match planning.py compare
            "exclude_template": meal.get("template"),  # name to avoid (can be None)
        }
        st.session_state.generate_now = True
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
else:
    st.info("Set your parameters in the sidebar and click **Generate plan.**")
