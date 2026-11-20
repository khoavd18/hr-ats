"""HTTP boundaries of the draft reports, using the hand-built T26 fixture."""

from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from app.models.users import UserRole
from tests.api.test_reports import ENDPOINTS, PARAMS
from tests.api.test_reports import dataset as dataset
from tests.auth_helpers import sign_in


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_own_report_and_revoked_job_access(client, account, dataset, db_session, endpoint):
    # Keep the fixture A credentials, use the ordinary authentication path.
    sign_in(client, email=dataset.a.email)
    response = client.get(f"/api/v1/reports/{endpoint}", params=PARAMS)
    assert response.status_code == 200, response.text
    if endpoint == "summary":
        assert response.json()["metrics"]["new_cvs"] == 3
        assert response.json()["metrics"]["placements"] == 2
    elif endpoint == "funnel":
        assert [row["count"] for row in response.json()["stages"]] == [1, 1, 1, 1, 0, 0, 1, 0]
    elif endpoint == "recruiters":
        assert [row["recruiter_id"] for row in response.json()["items"]] == [str(dataset.a.id)]
    elif endpoint == "ai-agreement":
        assert response.json()["agreement"]["rate"] == 0.5
    else:
        book = load_workbook(BytesIO(response.content))
        assert book["Tổng hợp"].cell(2, 1).value == 3
        assert book["Theo người phụ trách"].max_row == 2
    db_session.delete(dataset.membership)
    db_session.commit()
    denied = client.get(f"/api/v1/reports/{endpoint}", params=PARAMS | {"job_id": dataset.j2.id})
    assert denied.status_code == 403


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_lead_can_view_team_and_filter_by_job_and_unit(
    client, account, dataset, db_session, endpoint
):
    account.role = UserRole.lead
    db_session.commit()
    sign_in(client)
    response = client.get(f"/api/v1/reports/{endpoint}", params=PARAMS | {"job_id": dataset.j1.id})
    assert response.status_code == 200, response.text
    mismatch = client.get(
        f"/api/v1/reports/{endpoint}",
        params=PARAMS
        | {
            "job_id": dataset.j1.id,
            "hiring_unit_id": dataset.u2.id,
        },
    )
    assert mismatch.status_code == 200
    if endpoint == "summary":
        assert response.json()["metrics"]["new_cvs"] == 2
        assert mismatch.json()["metrics"]["new_cvs"] == 0


@pytest.mark.parametrize("field", ["job_id", "recruiter_id"])
def test_missing_explicit_resource(client, account, field):
    sign_in(client)
    assert (
        client.get("/api/v1/reports/summary", params=PARAMS | {field: uuid4()}).status_code == 404
    )


def test_missing_range_and_inactive_account(client, account, db_session):
    sign_in(client)
    assert client.get("/api/v1/reports/summary").status_code == 422
    account.is_active = False
    db_session.commit()
    assert client.get("/api/v1/reports/summary", params=PARAMS).status_code == 401


def test_openapi_exposes_binary_export_and_required_date_filters(client):
    paths = client.get("/openapi.json").json()["paths"]
    route = paths["/api/v1/reports/export.xlsx"]["get"]
    content = route["responses"]["200"]["content"]
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert content == {mime: {"schema": {"type": "string", "format": "binary"}}}
    required = {p["name"] for p in route["parameters"] if p.get("required")}
    assert required == {"from", "to"}
