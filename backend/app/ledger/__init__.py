"""Ledger engine package.

Design Requirement:
- Deterministic credit (udhaar) and payment calculation engine.
- Only this service may update financial balances in the database.
- Every transaction has a unique ID, idempotency protection, and auditable history.
- Never directly modified by LLM output.
"""
