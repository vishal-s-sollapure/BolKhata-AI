/**
 * Unit tests for useVoiceWebSocket React hook.
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';

describe('useVoiceWebSocket Hook', () => {
  let mockWsInstance: any = null;

  class MockWebSocket {
    static OPEN = 1;
    static CONNECTING = 0;
    static CLOSING = 2;
    static CLOSED = 3;

    readyState = MockWebSocket.OPEN;
    binaryType = 'arraybuffer';
    send = vi.fn();
    close = vi.fn();
    onopen: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: ((err: any) => void) | null = null;
    onclose: (() => void) | null = null;

    constructor(_url: string) {
      mockWsInstance = this;
      setTimeout(() => {
        if (this.onopen) this.onopen();
      }, 0);
    }
  }

  beforeEach(() => {
    mockWsInstance = null;
    // @ts-expect-error Mocking window.WebSocket
    window.WebSocket = MockWebSocket;

    // Mock HTML5 Audio constructor
    window.Audio = vi.fn().mockImplementation(function (this: any) {
      this.play = vi.fn().mockResolvedValue(undefined);
      this.pause = vi.fn();
      this.currentTime = 0;
      this.onplay = null;
      this.onended = null;
      this.onerror = null;
      return this;
    }) as any;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts in disconnected state and connects on demand', async () => {
    const { result } = renderHook(() =>
      useVoiceWebSocket({ storeId: '00000000-0000-0000-0000-000000000001', language: 'kn-IN' })
    );

    expect(result.current.status).toBe('disconnected');
    expect(result.current.sessionId).toBeNull();

    act(() => {
      result.current.connect();
    });

    expect(result.current.status).toBe('connecting');

    // Simulate open and SESSION_STARTED event
    await act(async () => {
      if (mockWsInstance?.onopen) {
        mockWsInstance.onopen();
      }
      if (mockWsInstance?.onmessage) {
        mockWsInstance.onmessage({
          data: JSON.stringify({
            event: 'SESSION_STARTED',
            session_id: 'session-xyz-123',
            store_id: '00000000-0000-0000-0000-000000000001',
            sample_rate: 16000,
            format: 's16le',
            channels: 1,
            language: 'kn-IN',
          }),
        });
      }
    });

    expect(result.current.status).toBe('ready');
    expect(result.current.sessionId).toBe('session-xyz-123');
  });

  it('handles PARTIAL_TRANSCRIPT and FINAL_TRANSCRIPT streaming events', async () => {
    const { result } = renderHook(() =>
      useVoiceWebSocket({ storeId: '00000000-0000-0000-0000-000000000001', language: 'kn-IN' })
    );

    act(() => {
      result.current.connect();
    });

    // Send partial transcript
    await act(async () => {
      if (mockWsInstance?.onmessage) {
        mockWsInstance.onmessage({
          data: JSON.stringify({
            event: 'PARTIAL_TRANSCRIPT',
            session_id: 'session-xyz-123',
            transcript: 'ರಮೇಶ್ ಅವರಿಗೆ',
            is_final: false,
          }),
        });
      }
    });

    expect(result.current.partialTranscript).toBe('ರಮೇಶ್ ಅವರಿಗೆ');
    expect(result.current.finalTranscript).toBe('');

    // Send final transcript
    await act(async () => {
      if (mockWsInstance?.onmessage) {
        mockWsInstance.onmessage({
          data: JSON.stringify({
            event: 'FINAL_TRANSCRIPT',
            session_id: 'session-xyz-123',
            transcript: 'ರಮೇಶ್ ಅವರಿಗೆ 340 ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ',
            is_final: true,
          }),
        });
      }
    });

    expect(result.current.finalTranscript).toBe('ರಮೇಶ್ ಅವರಿಗೆ 340 ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ');
    expect(result.current.partialTranscript).toBe('');
  });

  it('handles PROPOSAL_READY event with staged proposal and spoken prompt', async () => {
    const { result } = renderHook(() =>
      useVoiceWebSocket({ storeId: '00000000-0000-0000-0000-000000000001', language: 'kn-IN' })
    );

    act(() => {
      result.current.connect();
    });

    const proposalReadyPayload = {
      event: 'PROPOSAL_READY',
      session_id: 'session-xyz-123',
      proposal: {
        proposal_id: 'prop-ws-999',
        intent: 'ADD_CREDIT',
        customer_name: 'Ramesh',
        amount: '340.00',
        currency: 'INR',
        confidence: 0.95,
        requires_clarification: false,
        requires_confirmation: true,
        summary: 'Add ₹340.00 credit for Ramesh',
        reasoning_code: 'CUSTOMER_AND_AMOUNT_IDENTIFIED',
      },
      staged_proposal: {
        proposal_id: 'prop-ws-999',
        store_id: '00000000-0000-0000-0000-000000000001',
        customer_name: 'Ramesh',
        intent: 'ADD_CREDIT',
        amount: '340.00',
        currency: 'INR',
        summary: 'Add ₹340.00 credit for Ramesh',
        status: 'PENDING',
        requires_confirmation: true,
        created_at: '2026-11-22T00:00:00Z',
        expires_at: '2026-11-22T00:15:00Z',
      },
      spoken_response: 'Ramesh ಅವರಿಗೆ ₹340.00 ಸಾಲ ದಾಖಲಿಸಲು ಸಿದ್ಧವಾಗಿದೆ. ದಯವಿಟ್ಟು ಖಚಿತಪಡಿಸಿ.',
      audio_b64: 'UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=',
      audio_format: 'audio/wav',
    };

    await act(async () => {
      if (mockWsInstance?.onmessage) {
        mockWsInstance.onmessage({
          data: JSON.stringify(proposalReadyPayload),
        });
      }
    });

    expect(result.current.proposalReady).not.toBeNull();
    expect(result.current.proposalReady?.proposal.amount).toBe('340.00');
    expect(result.current.proposalReady?.staged_proposal.status).toBe('PENDING');
    expect(result.current.proposalReady?.spoken_response).toContain('340.00');

    // Reset proposal
    act(() => {
      result.current.clearProposal();
    });

    expect(result.current.proposalReady).toBeNull();
    expect(result.current.finalTranscript).toBe('');
  });

  it('handles READ_ONLY_RESPONSE for balance inquiries with 0 mutations', async () => {
    const { result } = renderHook(() =>
      useVoiceWebSocket({ storeId: '00000000-0000-0000-0000-000000000001', language: 'kn-IN' })
    );

    act(() => {
      result.current.connect();
    });

    const readOnlyPayload = {
      event: 'READ_ONLY_RESPONSE',
      session_id: 'session-xyz-123',
      intent: 'QUERY_BALANCE',
      data: {
        found: true,
        customer_name: 'Suresh',
        outstanding_balance: '500.00',
      },
      spoken_response: 'Suresh ಅವರ ಬಾಕಿ ಮೊತ್ತ ₹500.00 ಆಗಿದೆ.',
      audio_format: 'audio/wav',
    };

    await act(async () => {
      if (mockWsInstance?.onmessage) {
        mockWsInstance.onmessage({
          data: JSON.stringify(readOnlyPayload),
        });
      }
    });

    expect(result.current.readOnlyResponse).not.toBeNull();
    expect(result.current.readOnlyResponse?.data.outstanding_balance).toBe('500.00');
  });

  it('disconnects and clears state gracefully', () => {
    const { result } = renderHook(() =>
      useVoiceWebSocket({ storeId: '00000000-0000-0000-0000-000000000001', language: 'kn-IN' })
    );

    act(() => {
      result.current.connect();
    });

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.status).toBe('disconnected');
    expect(mockWsInstance?.close).toHaveBeenCalled();
  });
});
