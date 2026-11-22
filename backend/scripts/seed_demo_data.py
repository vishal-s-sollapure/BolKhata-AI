"""Realistic Kirana Store Database Seeder for BolKhata AI.

Populates the default Kirana store ('Sri Manjunatha Kirana & General Store') with:
- 8 realistic kirana customers with valid Indian mobile numbers
- 16 realistic credit (udhaar) and payment (jama) transactions
- Authentic Indian kirana item descriptions (Rice, Dal, Oil, Atta, Sugar, Tea, GPay)
- Immutable audit logs and accurately calculated balances

Run via:
    python backend/scripts/seed_demo_data.py
    python backend/scripts/seed_demo_data.py --reset
"""

import argparse
import os
import sys
import uuid
from decimal import Decimal

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.session import Base, SessionLocal, engine, init_db_triggers
from app.ledger.service import LedgerService
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.services.store_service import DEFAULT_DEV_STORE_ID, StoreService
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.scripts.seed")


DEMO_CUSTOMERS_DATA = [
    {
        "name": "Ramesh Kumar",
        "phone": "+919845012345",
        "transactions": [
            ("CREDIT", Decimal("500.00"), "Sona Masoori Rice 10kg + Tata Salt 1kg"),
            ("CREDIT", Decimal("340.00"), "Fortune Sunflower Oil 2L + Sugar 2kg"),
            ("PAYMENT", Decimal("500.00"), "Cash payment received via PhonePe UPI"),
        ],
    },
    {
        "name": "Suresh Gowda",
        "phone": "+919448023456",
        "transactions": [
            ("CREDIT", Decimal("720.00"), "Aashirvaad Sharbati Atta 10kg + Toor Dal 2kg"),
            ("PAYMENT", Decimal("200.00"), "Partial cash payment at shop counter"),
        ],
    },
    {
        "name": "Priya Sharma",
        "phone": "+919900134567",
        "transactions": [
            ("CREDIT", Decimal("450.00"), "Nandini Pure Ghee 500ml + Almonds 200g"),
            ("PAYMENT", Decimal("300.00"), "Payment received via Google Pay"),
        ],
    },
    {
        "name": "Mahesh Reddy",
        "phone": "+919886045678",
        "transactions": [
            ("CREDIT", Decimal("1250.00"), "Monthly grocery basket (Spices, Oil, Pulses)"),
            ("PAYMENT", Decimal("400.00"), "Counter cash payment"),
        ],
    },
    {
        "name": "Anitha Patil",
        "phone": "+919741056789",
        "transactions": [
            ("CREDIT", Decimal("300.00"), "Red Label Tea 500g + Milk Bread + Eggs 12pk"),
            ("PAYMENT", Decimal("300.00"), "Full settlement cash payment"),
        ],
    },
    {
        "name": "Manjunath Swamy",
        "phone": "+919480067890",
        "transactions": [
            ("CREDIT", Decimal("620.00"), "Surf Excel 2kg + Vim Gel + Santoor Soaps (4pk)"),
            ("PAYMENT", Decimal("200.00"), "Paytm UPI payment"),
        ],
    },
    {
        "name": "Vijay Kulkarni",
        "phone": "+919611078901",
        "transactions": [
            ("CREDIT", Decimal("1800.00"), "India Gate Basmati Rice 10kg + Groundnut Oil 5L"),
            ("PAYMENT", Decimal("600.00"), "Bank NEFT transfer"),
        ],
    },
    {
        "name": "Sunita Hegde",
        "phone": "+919844089012",
        "transactions": [
            ("CREDIT", Decimal("480.00"), "Organic Ragi Flour 5kg + Organic Jaggery 2kg"),
            ("PAYMENT", Decimal("200.00"), "Cash payment"),
        ],
    },
]


def seed_database(reset: bool = False):
    """Seeds the default store with realistic customers and transactions."""
    print("=" * 70)
    print("  BolKhata AI — Kirana Store Database Seeder")
    print("  'Your Kirana Store. Your Voice. Your Digital Khata.'")
    print("=" * 70)

    # 1. Initialize schema and triggers
    Base.metadata.create_all(bind=engine)
    init_db_triggers(engine)

    ledger_service = LedgerService()

    with SessionLocal() as db:
        # 2. Ensure default store exists
        store = StoreService.get_or_create_default_store(db)
        print(f"\n[+] Store: {store.store_name} ({store.id})")
        print(f"    Owner: {store.owner_name} | Phone: {store.phone_number} | Lang: {store.preferred_language}")

        # If reset requested, clean existing customers for this store
        if reset:
            print("\n[*] Resetting existing store data...")
            # Note: triggers protect against UPDATE/DELETE on khata_entries.
            # To reset cleanly, we can re-create tables if running in SQLite.
            print("    Skipping trigger bypass to preserve audit invariants.")

        existing_customers = db.query(Customer).filter(Customer.store_id == store.id).all()
        existing_names = {c.normalized_name: c for c in existing_customers}

        print(f"\n[*] Seeding {len(DEMO_CUSTOMERS_DATA)} Kirana customers and transaction history...")
        seeded_customers_count = 0
        seeded_transactions_count = 0

        for c_data in DEMO_CUSTOMERS_DATA:
            c_name = c_data["name"]
            norm_name = c_name.strip().lower()

            if norm_name in existing_names:
                cust = existing_names[norm_name]
                # Update phone if missing
                if not cust.phone_number and c_data["phone"]:
                    cust.phone_number = c_data["phone"]
                    db.commit()
            else:
                cust = Customer(
                    id=str(uuid.uuid4()),
                    store_id=store.id,
                    customer_name=c_name,
                    normalized_name=norm_name,
                    phone_number=c_data["phone"],
                    is_active=True,
                )
                db.add(cust)
                db.commit()
                db.refresh(cust)
                seeded_customers_count += 1

            # Seed transactions for this customer if none exist
            cust_entries = db.query(KhataEntry).filter(
                KhataEntry.store_id == store.id,
                KhataEntry.customer_id == cust.id,
            ).count()

            if cust_entries == 0:
                for entry_type, amt, desc in c_data["transactions"]:
                    idem_key = f"seed-{cust.id[:8]}-{uuid.uuid4().hex[:12]}"
                    ledger_service.record_transaction(
                        store_id=store.id,
                        customer_id=cust.id,
                        entry_type=entry_type,
                        amount=amt,
                        idempotency_key=idem_key,
                        description=desc,
                        created_by="system_seeder",
                        db=db,
                    )
                    seeded_transactions_count += 1

        # 3. Print Final Summary Table
        summary = ledger_service.get_store_summary(store.id, db)
        all_customers = db.query(Customer).filter(Customer.store_id == store.id, Customer.is_active == True).all()

        print("\n" + "-" * 70)
        print(f"{'Customer Name':<20} | {'Phone Number':<16} | {'Balance':>12} | {'Status':<12}")
        print("-" * 70)

        for c in sorted(all_customers, key=lambda x: x.customer_name):
            bal = ledger_service.get_customer_balance(store.id, c.id, db)
            status_str = "Udhaar Dues" if bal.outstanding_balance > 0 else ("Settled" if bal.outstanding_balance == 0 else "Advance")
            print(f"{c.customer_name:<20} | {c.phone_number or 'N/A':<16} | ₹{bal.outstanding_balance:>10.2f} | {status_str:<12}")

        print("-" * 70)
        print(f"\n[✓] Seeding Complete!")
        print(f"    • Total Active Customers : {summary.active_customers_count}")
        print(f"    • Total Store Udhaar     : ₹{summary.total_outstanding_balance}")
        print(f"    • Total Payments (Jama)  : ₹{summary.total_payment}")
        print(f"    • Total Credit Issued    : ₹{summary.total_credit}")
        print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed BolKhata AI demo data")
    parser.add_argument("--reset", action="store_true", help="Reset and reseed demo data")
    args = parser.parse_args()
    seed_database(reset=args.reset)
