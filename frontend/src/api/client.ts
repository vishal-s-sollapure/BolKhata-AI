/**
 * Centralized typed API client for BolKhata AI backend.
 * Provides resilient network handling, request timeouts, and store tenant scoping.
 */

import {
  BackendHealthResponse,
  CommitProposalRequest,
  Customer,
  CustomerBalanceResponse,
  CustomerCreateRequest,
  CustomerEntriesResponse,
  CustomerListResponse,
  LedgerCommitResponse,
  ParseIntentResponse,
  PendingProposalResponse,
  StageProposalRequest,
  StoreSummaryResponse,
} from '../types/api';

export const DEFAULT_DEV_STORE_ID = '00000000-0000-0000-0000-000000000001';

export class ApiError extends Error {
  status: number;
  detail: string;
  data?: unknown;

  constructor(status: number, detail: string, data?: unknown) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

export class BolKhataApiClient {
  private baseUrl: string;
  private storeId: string;
  private defaultTimeoutMs: number;

  constructor(
    baseUrl: string = import.meta.env.VITE_API_BASE_URL || '',
    storeId: string = DEFAULT_DEV_STORE_ID,
    defaultTimeoutMs: number = 15000
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.storeId = storeId;
    this.defaultTimeoutMs = defaultTimeoutMs;
  }

  public setStoreId(storeId: string): void {
    this.storeId = storeId;
  }

  public getStoreId(): string {
    return this.storeId;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    customTimeoutMs?: number
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      customTimeoutMs || this.defaultTimeoutMs
    );

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Store-Id': this.storeId,
      ...((options.headers as Record<string, string>) || {}),
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorDetail = `Request failed with status ${response.status}`;
        let parsedData: unknown = null;
        try {
          const errorJson = await response.json();
          parsedData = errorJson;
          if (errorJson && typeof errorJson === 'object' && 'detail' in errorJson) {
            errorDetail = String(errorJson.detail);
          }
        } catch {
          // If response body is not JSON, use default status message
        }
        throw new ApiError(response.status, errorDetail, parsedData);
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      if (err instanceof ApiError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiError(408, 'Request timed out. Please check your network connection.');
      }
      const message = err instanceof Error ? err.message : 'Unknown network failure';
      throw new ApiError(0, `Network communication error: ${message}`);
    }
  }

  // --- Health Endpoint ---
  public async getHealth(): Promise<BackendHealthResponse> {
    return this.request<BackendHealthResponse>('/health');
  }

  // --- Store Metrics ---
  public async getStoreSummary(): Promise<StoreSummaryResponse> {
    return this.request<StoreSummaryResponse>('/api/v1/ledger/summary');
  }

  // --- Customer Management ---
  public async listCustomers(
    query?: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<CustomerListResponse> {
    const params = new URLSearchParams();
    if (query && query.trim()) params.append('q', query.trim());
    params.append('limit', String(limit));
    params.append('offset', String(offset));
    return this.request<CustomerListResponse>(`/api/v1/customers?${params.toString()}`);
  }

  public async getCustomer(customerId: string): Promise<Customer> {
    return this.request<Customer>(`/api/v1/customers/${encodeURIComponent(customerId)}`);
  }

  public async createCustomer(data: CustomerCreateRequest): Promise<Customer> {
    return this.request<Customer>('/api/v1/customers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // --- Customer Balances and Ledger History ---
  public async getCustomerBalance(customerId: string): Promise<CustomerBalanceResponse> {
    return this.request<CustomerBalanceResponse>(
      `/api/v1/ledger/customers/${encodeURIComponent(customerId)}/balance`
    );
  }

  public async getCustomerEntries(
    customerId: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<CustomerEntriesResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    return this.request<CustomerEntriesResponse>(
      `/api/v1/ledger/customers/${encodeURIComponent(customerId)}/entries?${params.toString()}`
    );
  }

  // --- Voice Intent Parsing ---
  public async parseIntent(
    transcript: string,
    language: string = 'indic-auto'
  ): Promise<ParseIntentResponse> {
    return this.request<ParseIntentResponse>('/api/v1/intent/parse', {
      method: 'POST',
      body: JSON.stringify({ transcript, language }),
    });
  }

  // --- HITL Proposal Staging & Confirmation ---
  public async stageProposal(data: StageProposalRequest): Promise<PendingProposalResponse> {
    return this.request<PendingProposalResponse>('/api/v1/ledger/proposals', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  public async commitProposal(data: CommitProposalRequest): Promise<LedgerCommitResponse> {
    return this.request<LedgerCommitResponse>('/api/v1/ledger/commit', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  public async rejectProposal(
    proposalId: string,
    reason?: string
  ): Promise<PendingProposalResponse> {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return this.request<PendingProposalResponse>(
      `/api/v1/ledger/proposals/${encodeURIComponent(proposalId)}/reject${params}`,
      { method: 'POST' }
    );
  }
}

// Default singleton instance
export const apiClient = new BolKhataApiClient();
