"""AI Agent package.

Design Requirement:
- Groq LLM integration for multilingual voice command intent parsing.
- Outputs structured TransactionProposal schema.
- NEVER modifies ledger balances or executes raw SQL queries directly.
- All proposals require explicit validation and user confirmation before committing.
"""
