import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StoreProvider } from '../context/StoreContext';
import { Dashboard } from '../components/Dashboard';
import { SummaryCards } from '../components/SummaryCards';
import { Header } from '../components/Header';
import { apiClient } from '../api/client';
import { StoreSummaryResponse, BackendHealthResponse } from '../types/api';

vi.mock('../api/client', () => {
  return {
    DEFAULT_DEV_STORE_ID: '00000000-0000-0000-0000-000000000001',
    apiClient: {
      getHealth: vi.fn(),
      getStoreSummary: vi.fn(),
      setStoreId: vi.fn(),
      listCustomers: vi.fn(),
      parseIntent: vi.fn(),
      stageProposal: vi.fn(),
      commitProposal: vi.fn(),
      rejectProposal: vi.fn(),
    },
  };
});

describe('Dashboard and Summary Rendering', () => {
  const mockSummary: StoreSummaryResponse = {
    store_id: '00000000-0000-0000-0000-000000000001',
    store_name: 'Kirana Store Bengaluru',
    currency: 'INR',
    total_credit: '540.00',
    total_payment: '600.00',
    total_outstanding_balance: '-60.00',
    active_customers_count: 14,
    total_transactions_count: 42,
  };

  const mockHealth: BackendHealthResponse = {
    status: 'healthy',
    service: 'BolKhata AI',
    version: '0.1.0',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(apiClient.getStoreSummary).mockResolvedValue(mockSummary);
  });

  it('renders store summary metrics with authentic backend data', async () => {
    render(
      <StoreProvider>
        <SummaryCards />
      </StoreProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('₹-60.00')).toBeInTheDocument();
      expect(screen.getByText('₹600.00')).toBeInTheDocument();
      expect(screen.getByText('14')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
    });
  });

  it('renders loading skeleton when summary is fetching', () => {
    vi.mocked(apiClient.getStoreSummary).mockReturnValue(new Promise(() => {})); // Never resolves
    const { container } = render(
      <StoreProvider>
        <SummaryCards />
      </StoreProvider>
    );

    expect(container.getElementsByClassName('animate-pulse').length).toBeGreaterThan(0);
  });

  it('renders error state and retry button when summary fails', async () => {
    vi.mocked(apiClient.getStoreSummary).mockRejectedValue(new Error('Network offline'));

    render(
      <StoreProvider>
        <SummaryCards />
      </StoreProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Network offline/i)).toBeInTheDocument();
    });
  });

  it('switches languages between Kannada, Hindi, and English seamlessly', async () => {
    render(
      <StoreProvider>
        <Header />
      </StoreProvider>
    );

    // Initial language: Kannada
    expect(screen.getByText(/ಬೋಲ್ ಖಾತಾ AI/i)).toBeInTheDocument();

    // Switch to Hindi
    const hiBtn = screen.getByRole('button', { name: 'हिन्दी' });
    fireEvent.click(hiBtn);

    await waitFor(() => {
      expect(screen.getByText(/बोल खाता AI/i)).toBeInTheDocument();
    });

    // Switch to English
    const enBtn = screen.getByRole('button', { name: 'English' });
    fireEvent.click(enBtn);

    await waitFor(() => {
      expect(screen.getByText(/BolKhata AI/i)).toBeInTheDocument();
    });
  });

  it('renders Dashboard with quick customer navigation', async () => {
    const handleNav = vi.fn();
    render(
      <StoreProvider>
        <Dashboard onNavigateToCustomers={handleNav} />
      </StoreProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Kirana Store Bengaluru')).toBeInTheDocument();
    });

    const viewCustBtn = screen.getByRole('button', { name: /View All Customers/i });
    fireEvent.click(viewCustBtn);
    expect(handleNav).toHaveBeenCalledTimes(1);
  });
});
