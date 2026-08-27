import json


def get_housing_kpis():
    """Simulates a pre-aggregated query from Power BI."""
    mock_data = {
        "report_date": "2026-08-16",
        "business_unit": "Housing Operations",
        "metrics": {
            "total_active_tickets": 42,
            "overdue_tickets_74_hours": 3,
            "weekly_maintenance_spend": 4250.00,
            "average_resolution_time_days": 2.1
        },
        "critical_flags": [
            "Boiler failure reported at Unit 4A",
            "Contractor invoice #9921 missing approval"
        ]
    }
    return json.dumps(mock_data)
