from .schemas import Claim


def sample_claims() -> list[Claim]:
    common = dict(
        policy_number="AUTO-BASIC", incident_type="collision",
        description="Rear bumper damaged in a road collision.", estimated_loss=1800,
        documents=["statement", "repair_estimate"],
        required_documents=["statement", "repair_estimate"],
        damage_consistent=True, risk_flags=[],
    )
    variations = [
        {},
        {"policy_number": "AUTO-PREMIUM", "incident_type": "weather", "description": "Hail damaged the insured vehicle.", "risk_flags": ["medium_frequency"]},
        {"incident_type": "flood", "description": "Flood water damaged the vehicle."},
        {"incident_type": "personal_belongings_theft", "description": "A bag was stolen from the parked vehicle."},
        {"incident_type": "mechanical_breakdown", "description": "The engine stopped without an accident."},
        {"documents": ["statement"]},
        {"documents": ["repair_estimate"]},
        {"risk_flags": ["multiple_recent_claims", "conflicting_location"]},
        {"damage_consistent": False},
        {"policy_number": "UNKNOWN-POLICY"},
    ]
    return [
        Claim.model_validate({**common, **change, "claim_id": f"CL{index:03d}", "customer_id": f"CUSTOMER-{index:03d}"})
        for index, change in enumerate(variations, start=1)
    ]
