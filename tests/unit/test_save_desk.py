from app.services.save_desk import save_desk_fields, save_lane, save_priority_score


def test_near_term_high_risk_outranks_distant_risk_with_the_same_revenue() -> None:
    near = save_priority_score(0.8, 100_000, 20)
    later = save_priority_score(0.8, 100_000, 200)

    assert near > later
    assert save_lane("high", 20) == "call_today"
    assert save_lane("high", 200) == "watch"


def test_save_desk_fields_keep_the_scoring_contract() -> None:
    fields = save_desk_fields(
        lapse_probability=0.5,
        value_at_risk=10_000,
        days_to_term=45,
        risk_band="medium",
    )

    assert fields["renewal_pressure"] == 0.75
    assert fields["save_priority"] == 3_750.0
    assert fields["save_lane"] == "this_cycle"
