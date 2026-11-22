import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAudioRecorder } from '../hooks/useAudioRecorder';

describe('useAudioRecorder Hook', () => {
  let mockTracks: { stop: ReturnType<typeof vi.fn> }[];
  let mockStream: { getTracks: () => typeof mockTracks };

  beforeEach(() => {
    mockTracks = [{ stop: vi.fn() }];
    mockStream = {
      getTracks: () => mockTracks,
    };

    // Mock URL.createObjectURL and revokeObjectURL
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/test-audio');
    window.URL.revokeObjectURL = vi.fn();

    // Mock MediaRecorder
    class MockMediaRecorder {
      state = 'inactive';
      mimeType = 'audio/webm';
      ondataavailable: ((e: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      onerror: (() => void) | null = null;

      start() {
        this.state = 'recording';
      }

      stop() {
        this.state = 'inactive';
        if (this.ondataavailable) {
          this.ondataavailable({ data: new Blob(['fake-audio-bytes'], { type: 'audio/webm' }) });
        }
        if (this.onstop) {
          this.onstop();
        }
      }

      static isTypeSupported() {
        return true;
      }
    }

    // @ts-expect-error Mocking window.MediaRecorder
    window.MediaRecorder = MockMediaRecorder;

    // Mock getUserMedia
    Object.defineProperty(navigator, 'mediaDevices', {
      writable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(mockStream),
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes in IDLE state with 0 duration', () => {
    const { result } = renderHook(() => useAudioRecorder());
    expect(result.current.recordingState).toBe('IDLE');
    expect(result.current.durationSeconds).toBe(0);
    expect(result.current.audioBlob).toBeNull();
    expect(result.current.audioUrl).toBeNull();
    expect(result.current.errorMessage).toBeNull();
  });

  it('handles microphone permission denial gracefully', async () => {
    const permError = new DOMException('Permission denied', 'NotAllowedError');
    // @ts-expect-error Mocking getUserMedia rejection
    navigator.mediaDevices.getUserMedia = vi.fn().mockRejectedValue(permError);

    const { result } = renderHook(() => useAudioRecorder());

    await act(async () => {
      await result.current.startRecording();
    });

    expect(result.current.recordingState).toBe('ERROR');
    expect(result.current.errorMessage).toContain('Microphone permission denied');
  });

  it('records audio and transitions to TRANSCRIPT_READY when stopped', async () => {
    const { result } = renderHook(() => useAudioRecorder());

    await act(async () => {
      await result.current.startRecording();
    });

    expect(result.current.recordingState).toBe('RECORDING');

    // Simulate stopping after recording
    await act(async () => {
      await result.current.stopRecording();
    });

    expect(result.current.recordingState).toBe('TRANSCRIPT_READY');
    expect(result.current.audioBlob).not.toBeNull();
    expect(result.current.audioUrl).toBe('blob:http://localhost/test-audio');
    expect(mockTracks[0].stop).toHaveBeenCalled();
  });

  it('cleans up stream tracks and state on cancel', async () => {
    const { result } = renderHook(() => useAudioRecorder());

    await act(async () => {
      await result.current.startRecording();
    });

    act(() => {
      result.current.cancelRecording();
    });

    expect(result.current.recordingState).toBe('IDLE');
    expect(result.current.audioBlob).toBeNull();
    expect(result.current.audioUrl).toBeNull();
    expect(mockTracks[0].stop).toHaveBeenCalled();
  });
});
