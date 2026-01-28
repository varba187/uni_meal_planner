import random
from logic.planning import pick_template_for_purpose

def test_pick_template_excludes_current_when_swapping():
    random.seed(0)

    templates = [
        {"name": "A", "purposes": ["dinner"], "items": []},
        {"name": "B", "purposes": ["dinner"], "items": []},
        {"name": "C", "purposes": ["breakfast"], "items": []},
    ]

    used = set()

    # pretend current dinner template is "A"
    picked = pick_template_for_purpose(
        templates=templates,
        purpose="dinner",
        used_templates=used,
        force_new=True,
        exclude_name="A",
    )

    assert picked is not None
    assert picked["name"] in ("B",)  # only other dinner option is B

def test_pick_template_returns_none_when_no_matching_purpose():
    templates = [{"name": "X", "purposes": ["breakfast"], "items": []}]
    picked = pick_template_for_purpose(templates, "dinner", set())
    assert picked is None
