import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StoreProvider } from '../context/StoreContext';
import { IntentProposalCard } from '../components/IntentProposalCard';
import { CustomerDisambiguation } from '../components/CustomerDisambiguation';
import { apiClient } from '../api/client';
import {
  PendingProposalResponse,
  TransactionProposal,
  LedgerCommitResponse,
} from '../types/api';

vi.mock('../api/client', () => {
  return {
    DEFAULT_DEV_STORE_ID: '00000000-0000-0000-0000-000000000001',
    apiClient: {
      getHealth: vi.fn(),
      getStoreSummary: vi.fn(),
      setStoreId: vi.fn(),
      commitProposal: vi.fn(),
      rejectProposal: vi.fn(),
    },
  };
});

describe('HITL Proposal Confirmation & Safety Tests', () => {
  const baseCreditProposal: TransactionProposal = {
    proposal_id: 'prop_test_credit_01',
    intent: 'ADD_CREDIT',
    customer_name: 'Ramesh Kumar',
    amount: '340.00',
    currency: 'INR',
    language: 'kn-IN',
    confidence: 0.98,
    requires_clarification: false,
    requires_confirmation: true,
    summary: 'Add ₹340.00 credit for Ramesh Kumar',
    reasoning_code: 'CUSTOMER_AND_AMOUNT_IDENTIFIED',
  };

  const stagedCreditProposal: PendingProposalResponse = {
    proposal_id: 'prop_test_credit_01',
    store_id: '00000000-0000-0000-0000-000000000001',
    customer_name: 'Ramesh Kumar',
    intent: 'ADD_CREDIT',
    amount: '340.00',
    currency: 'INR',
    summary: 'Add ₹340.00 credit for Ramesh Kumar',
    status: 'PENDING',
    requires_confirmation: true,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
  };

  const mockSuccessCommit: LedgerCommitResponse = {
    transaction_id: 'tx_uuid_12345678',
    store_id: '00000000-0000-0000-0000-000000000001',
    customer_id: 'cust_uuid_87654321',
    customer_name: 'Ramesh Kumar',
    entry_type: 'CREDIT',
    amount: '340.00',
    currency: 'INR',
    resulting_balance: '340.00',
    total_credit: '340.00',
    total_payment: '0.00',
    created_at: new Date().toISOString(),
    is_duplicate: false,
    idempotency_key: 'test_key',
  };

  beforeEach(() => {
    localStorage.setItem('bolkhata_lang', 'en');
    vi.clearAllMocks();
  });

  it('renders authoritative proposal card with customer and amount', () => {
    render(
      <StoreProvider>
        <IntentProposalCard
          proposal={baseCreditProposal}
          stagedProposal={stagedCreditProposal}
          onCommitted={vi.fn()}
          onRejected={vi.fn()}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    expect(screen.getByText('Ramesh Kumar')).toBeInTheDocument();
    expect(screen.getByText('₹340.00')).toBeInTheDocument();
    expect(screen.getByText(/Add ₹340.00 credit for Ramesh Kumar/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm Transaction/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reject \/ Cancel/i })).toBeInTheDocument();
  });

  it('commits proposal with authoritative ID and prevents repeated double-clicks', async () => {
    vi.mocked(apiClient.commitProposal).mockResolvedValue(mockSuccessCommit);
    const handleCommitted = vi.fn();

    render(
      <StoreProvider>
        <IntentProposalCard
          proposal={baseCreditProposal}
          stagedProposal={stagedCreditProposal}
          onCommitted={handleCommitted}
          onRejected={vi.fn()}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    const confirmBtn = screen.getByRole('button', { name: /Confirm Transaction/i });
    fireEvent.click(confirmBtn);

    // Verify commit payload
    expect(apiClient.commitProposal).toHaveBeenCalledWith(
      expect.objectContaining({
        proposal_id: 'prop_test_credit_01',
        confirmed: true,
        actor_type: 'merchant',
      })
    );

    await waitFor(() => {
      expect(handleCommitted).toHaveBeenCalledWith(mockSuccessCommit);
      expect(screen.getByText(/Transaction Committed to Immutable Ledger/i)).toBeInTheDocument();
      expect(screen.getByText(/Updated Outstanding Balance:/i)).toBeInTheDocument();
    });
  });

  it('handles duplicate replay (is_duplicate: true) gracefully without duplicate state', async () => {
    const replayCommit: LedgerCommitResponse = {
      ...mockSuccessCommit,
      is_duplicate: true,
    };
    vi.mocked(apiClient.commitProposal).mockResolvedValue(replayCommit);

    render(
      <StoreProvider>
        <IntentProposalCard
          proposal={baseCreditProposal}
          stagedProposal={stagedCreditProposal}
          onCommitted={vi.fn()}
          onRejected={vi.fn()}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    const confirmBtn = screen.getByRole('button', { name: /Confirm Transaction/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByText(/Transaction already committed\. Replay response returned/i)).toBeInTheDocument();
    });
  });

  it('rejects proposal via reject endpoint and displays canceled status', async () => {
    vi.mocked(apiClient.rejectProposal).mockResolvedValue({
      ...stagedCreditProposal,
      status: 'REJECTED',
    });
    const handleRejected = vi.fn();

    render(
      <StoreProvider>
        <IntentProposalCard
          proposal={baseCreditProposal}
          stagedProposal={stagedCreditProposal}
          onCommitted={vi.fn()}
          onRejected={handleRejected}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    const rejectBtn = screen.getByRole('button', { name: /Reject \/ Cancel/i });
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(apiClient.rejectProposal).toHaveBeenCalledWith(
        'prop_test_credit_01',
        expect.stringContaining('Rejected by merchant')
      );
      expect(handleRejected).toHaveBeenCalledWith('prop_test_credit_01');
    });
  });

  it('does NOT render commit button for read-only QUERY_BALANCE intent', () => {
    const queryBalanceProposal: TransactionProposal = {
      proposal_id: 'prop_query_01',
      intent: 'QUERY_BALANCE',
      customer_name: 'Suresh Patel',
      amount: null,
      currency: 'INR',
      confidence: 0.95,
      requires_clarification: false,
      requires_confirmation: false,
      summary: 'Query balance for Suresh Patel',
      reasoning_code: 'CUSTOMER_IDENTIFIED_FOR_BALANCE',
    };

    render(
      <StoreProvider>
        <IntentProposalCard
          proposal={queryBalanceProposal}
          stagedProposal={null}
          onCommitted={vi.fn()}
          onRejected={vi.fn()}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    // Confirm button must NOT exist
    expect(screen.queryByRole('button', { name: /Confirm Transaction/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Informational query only\. No financial mutation will be performed\./i)).toBeInTheDocument();
  });

  it('renders clarification prompt and no commit button for UNKNOWN intent', () => {
    const unknownProposal: TransactionProposal = {
      proposal_id: 'prop_unknown_01',
      intent: 'UNKNOWN',
      customer_name: null,
      amount: null,
      currency: 'INR',
      confidence: 0.2,
      requires_clarification: true,
      requires_confirmation: false,
      clarification_question: 'Could not understand voice utterance. Please speak customer name and amount.',
      summary: 'Unknown voice utterance',
      reasoning_code: 'UNKNOWN_INTENT',
    };

    render(
      <StoreProvider>
        <IntentProposalCard
          proposal={unknownProposal}
          stagedProposal={null}
          onCommitted={vi.fn()}
          onRejected={vi.fn()}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    expect(screen.queryByRole('button', { name: /Confirm Transaction/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Could not understand voice utterance/i)).toBeInTheDocument();
  });

  it('renders CustomerDisambiguation and requires explicit merchant selection', () => {
    const candidates = [
      {
        id: 'cust_01',
        customer_name: 'Ramesh Kumar',
        phone_number: '9876543210',
        created_at: new Date().toISOString(),
      },
      {
        id: 'cust_02',
        customer_name: 'Ramesh Kumar',
        phone_number: '9123456789',
        created_at: new Date().toISOString(),
      },
    ];

    const handleSelect = vi.fn();
    render(
      <StoreProvider>
        <CustomerDisambiguation
          customerName="Ramesh Kumar"
          candidates={candidates}
          onSelectCustomer={handleSelect}
          onCreateNewCustomer={vi.fn()}
          onCancel={vi.fn()}
        />
      </StoreProvider>
    );

    expect(screen.getByText(/Multiple customers found matching this name/i)).toBeInTheDocument();
    expect(screen.getByText('9876543210')).toBeInTheDocument();
    expect(screen.getByText('9123456789')).toBeInTheDocument();

    const selectButtons = screen.getAllByRole('button', { name: /Select This Customer/i });
    expect(selectButtons.length).toBe(2);

    // Merchant clicks second candidate
    fireEvent.click(selectButtons[1]);
    expect(handleSelect).toHaveBeenCalledWith(candidates[1]);
  });
});
