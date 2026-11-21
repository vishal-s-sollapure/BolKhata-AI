"""API integration tests for customer and ledger endpoints in BolKhata AI."""

import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.kirana_store import KiranaStore


class TestLedgerAPI:
    """Verifies HTTP API endpoints for customer management and the deterministic ledger."""

    def test_customer_crud_api(self, client: TestClient, test_store: KiranaStore):
        # 1. Create Customer
        create_payload = {
            "customer_name": "Naveen Reddy",
            "phone_number": "+919888877777",
        }
        res = client.post(
            "/api/v1/customers",
            json=create_payload,
            headers={"X-Store-Id": test_store.id},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["customer_name"] == "Naveen Reddy"
        assert data["store_id"] == test_store.id
        customer_id = data["id"]

        # 2. List Customers
        list_res = client.get(
            "/api/v1/customers",
            headers={"X-Store-Id": test_store.id},
        )
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert any(c["id"] == customer_id for c in list_data["customers"])

        # 3. Search Customer
        search_res = client.get(
            "/api/v1/customers?q=Naveen",
            headers={"X-Store-Id": test_store.id},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert len(search_data["customers"]) >= 1

        # 4. Get Customer by ID
        get_res = client.get(
            f"/api/v1/customers/{customer_id}",
            headers={"X-Store-Id": test_store.id},
        )
        assert get_res.status_code == 200
        assert get_res.json()["id"] == customer_id

    def test_stage_and_commit_proposal_flow(
        self,
        client: TestClient,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        # 1. Stage proposal
        stage_payload = {
            "customer_name": test_customer.customer_name,
            "intent": "ADD_CREDIT",
            "amount": "340.00",
            "currency": "INR",
            "summary": "Add ₹340.00 credit for Ramesh Kumar",
            "raw_transcript": "Ramesh ke naam 340 rupaye likho",
        }
        stage_res = client.post(
            "/api/v1/ledger/proposals",
            json=stage_payload,
            headers={"X-Store-Id": test_store.id},
        )
        assert stage_res.status_code == 201
        stage_data = stage_res.json()
        proposal_id = stage_data["proposal_id"]
        assert stage_data["status"] == "PENDING"
        assert stage_data["requires_confirmation"] is True

        # 2. Commit proposal with merchant confirmation
        commit_payload = {
            "proposal_id": proposal_id,
            "confirmed": True,
            "idempotency_key": "api_commit_test_01",
            "notes": "Verified by merchant",
        }
        commit_res = client.post(
            "/api/v1/ledger/commit",
            json=commit_payload,
            headers={"X-Store-Id": test_store.id},
        )
        assert commit_res.status_code == 200
        commit_data = commit_res.json()
        assert commit_data["amount"] == "340.00"
        assert commit_data["resulting_balance"] == "340.00"
        assert commit_data["entry_type"] == "CREDIT"
        assert commit_data["is_duplicate"] is False

        # 3. Check Customer Balance
        balance_res = client.get(
            f"/api/v1/ledger/customers/{test_customer.id}/balance",
            headers={"X-Store-Id": test_store.id},
        )
        assert balance_res.status_code == 200
        bdata = balance_res.json()
        assert bdata["outstanding_balance"] == "340.00"
        assert bdata["total_credit"] == "340.00"

        # 4. Check Customer Ledger History
        entries_res = client.get(
            f"/api/v1/ledger/customers/{test_customer.id}/entries",
            headers={"X-Store-Id": test_store.id},
        )
        assert entries_res.status_code == 200
        edata = entries_res.json()
        assert edata["total"] >= 1
        assert edata["entries"][0]["amount"] == "340.00"

    def test_store_isolation_via_api(
        self,
        client: TestClient,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """Store B cannot access Store A's customer balance or history."""
        # Create Store B
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Independent Store B",
            owner_name="Owner B",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        # Store B tries to get balance of test_customer (belongs to test_store)
        res = client.get(
            f"/api/v1/ledger/customers/{test_customer.id}/balance",
            headers={"X-Store-Id": store_b.id},
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_unconfirmed_proposal_rejected_by_api(
        self,
        client: TestClient,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        stage_res = client.post(
            "/api/v1/ledger/proposals",
            json={
                "customer_name": test_customer.customer_name,
                "intent": "ADD_CREDIT",
                "amount": "150.00",
                "currency": "INR",
            },
            headers={"X-Store-Id": test_store.id},
        )
        proposal_id = stage_res.json()["proposal_id"]

        commit_res = client.post(
            "/api/v1/ledger/commit",
            json={
                "proposal_id": proposal_id,
                "confirmed": False,  # Not confirmed
            },
            headers={"X-Store-Id": test_store.id},
        )
        assert commit_res.status_code == 400
        assert "confirmed" in commit_res.json()["detail"].lower()

    def test_summary_api(
        self,
        client: TestClient,
        test_store: KiranaStore,
    ):
        res = client.get(
            "/api/v1/ledger/summary",
            headers={"X-Store-Id": test_store.id},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["store_id"] == test_store.id
        assert "total_outstanding_balance" in data
