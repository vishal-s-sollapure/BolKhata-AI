import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BolKhataApiClient, ApiError } from '../api/client';

describe('BolKhataApiClient Unit Tests', () => {
  let client: BolKhataApiClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    client = new BolKhataApiClient('http://127.0.0.1:8000', 'test_store_123', 5000);
  });

  it('injects X-Store-Id and Content-Type headers automatically', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'healthy', version: '0.1.0' }),
    });
    globalThis.fetch = mockFetch;

    await client.getHealth();

    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/health',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-Store-Id': 'test_store_123',
        }),
      })
    );
  });

  it('updates store context dynamically', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    });
    globalThis.fetch = mockFetch;

    client.setStoreId('new_store_999');
    expect(client.getStoreId()).toBe('new_store_999');

    await client.getStoreSummary();

    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/ledger/summary',
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-Store-Id': 'new_store_999',
        }),
      })
    );
  });

  it('parses structured backend error details on HTTP 400/409', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: vi.fn().mockResolvedValue({ detail: 'Proposal has already been committed' }),
    });
    globalThis.fetch = mockFetch;

    await expect(
      client.commitProposal({ proposal_id: 'prop_01', confirmed: true })
    ).rejects.toThrow(ApiError);

    try {
      await client.commitProposal({ proposal_id: 'prop_01', confirmed: true });
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(409);
      expect(apiErr.detail).toBe('Proposal has already been committed');
    }
  });

  it('handles network timeout error cleanly', async () => {
    const abortErr = new DOMException('The user aborted a request.', 'AbortError');
    const mockFetch = vi.fn().mockRejectedValue(abortErr);
    globalThis.fetch = mockFetch;

    await expect(client.getHealth()).rejects.toThrow(ApiError);
  });
});
