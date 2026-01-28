from logic.planning import filter_foods_by_constraints, UserConstraints

def test_filter_foods_by_constraints_lactose():
    foods = [
        {"name": "Milk", "lactose_free": False, "allergens": []},
        {"name": "Rice", "lactose_free": True, "allergens": []},
    ]
    c = UserConstraints(lactose_intolerant=True, disliked_foods=[], allergies=[])

    safe = filter_foods_by_constraints(foods, c)
    names = [f["name"] for f in safe]
    assert "Milk" not in names
    assert "Rice" in names

def test_filter_foods_by_constraints_disliked_and_allergy():
    foods = [
        {"name": "Peanut butter", "lactose_free": True, "allergens": ["peanuts"]},
        {"name": "Apple", "lactose_free": True, "allergens": []},
    ]
    c = UserConstraints(lactose_intolerant=False, disliked_foods=["Apple"], allergies=["peanuts"])

    safe = filter_foods_by_constraints(foods, c)
    names = [f["name"] for f in safe]
    assert names == []  # both excluded
