/**
 * Custom React hook managing real-time bidirectional WebSocket voice streaming
 * with 16kHz PCM audio resampling, push-to-talk capture, and TTS playback.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  VoiceStreamStatus,
  VoiceProposalReadyEvent,
  VoiceReadOnlyResponseEvent,
  VoiceClarificationRequiredEvent,
  VoiceServerEvent,
} from '../types/api';
import { resampleTo16k, float32ToInt16PCM } from '../utils/audioResampler';

export interface UseVoiceWebSocketOptions {
  storeId?: string;
  language?: string;
  autoConnect?: boolean;
}

export interface UseVoiceWebSocketResult {
  status: VoiceStreamStatus;
  sessionId: string | null;
  partialTranscript: string;
  finalTranscript: string;
  proposalReady: VoiceProposalReadyEvent | null;
  readOnlyResponse: VoiceReadOnlyResponseEvent | null;
  clarification: VoiceClarificationRequiredEvent | null;
  isPlayingTTS: boolean;
  errorMessage: string | null;
  connect: () => void;
  disconnect: () => void;
  startStreaming: () => Promise<void>;
  stopStreaming: () => void;
  cancelStreaming: () => void;
  stopAudioPlayback: () => void;
  clearProposal: () => void;
}

export const useVoiceWebSocket = (options: UseVoiceWebSocketOptions = {}): UseVoiceWebSocketResult => {
  const { storeId, language = 'indic-auto', autoConnect = false } = options;

  const [status, setStatus] = useState<VoiceStreamStatus>('disconnected');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [partialTranscript, setPartialTranscript] = useState<string>('');
  const [finalTranscript, setFinalTranscript] = useState<string>('');
  const [proposalReady, setProposalReady] = useState<VoiceProposalReadyEvent | null>(null);
  const [readOnlyResponse, setReadOnlyResponse] = useState<VoiceReadOnlyResponseEvent | null>(null);
  const [clarification, setClarification] = useState<VoiceClarificationRequiredEvent | null>(null);
  const [isPlayingTTS, setIsPlayingTTS] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const isRecordingRef = useRef<boolean>(false);

  // Stop any ongoing TTS audio playback
  const stopAudioPlayback = useCallback(() => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
      audioElementRef.current = null;
    }
    setIsPlayingTTS(false);
  }, []);

  // Helper to play synthesized TTS base64 audio
  const playTTSAudio = useCallback((audioB64: string) => {
    try {
      stopAudioPlayback();
      const audioUrl = `data:audio/wav;base64,${audioB64}`;
      const audio = new Audio(audioUrl);
      audioElementRef.current = audio;

      audio.onplay = () => setIsPlayingTTS(true);
      audio.onended = () => {
        setIsPlayingTTS(false);
        audioElementRef.current = null;
      };
      audio.onerror = () => {
        setIsPlayingTTS(false);
        audioElementRef.current = null;
      };

      audio.play().catch((playErr) => {
        // Autoplay may be blocked if no user gesture
        console.warn('Autoplay prevented or failed:', playErr);
        setIsPlayingTTS(false);
      });
    } catch (err) {
      console.warn('Failed to initialize audio playback:', err);
      setIsPlayingTTS(false);
    }
  }, [stopAudioPlayback]);

  // Clean up microphone capture pipeline
  const cleanupMedia = useCallback(() => {
    isRecordingRef.current = false;
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
  }, []);

  // Connect to the backend streaming WebSocket
  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus('connecting');
    setErrorMessage(null);

    const wsBaseUrl = import.meta.env.VITE_WS_URL;
    let url: string;
    if (wsBaseUrl) {
      const sep = wsBaseUrl.includes('?') ? '&' : '?';
      url = `${wsBaseUrl}${sep}lang=${encodeURIComponent(language)}`;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      url = `${protocol}//${host}/api/v1/voice/stream?lang=${encodeURIComponent(language)}`;
    }
    if (storeId) {
      url += `&store_id=${encodeURIComponent(storeId)}`;
    }

    try {
      const ws = new WebSocket(url);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('ready');
      };

      ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
          try {
            const serverEvent: VoiceServerEvent = JSON.parse(event.data);

            switch (serverEvent.event) {
              case 'SESSION_STARTED':
                setSessionId(serverEvent.session_id);
                setStatus('ready');
                break;

              case 'PARTIAL_TRANSCRIPT':
                setPartialTranscript(serverEvent.transcript);
                break;

              case 'FINAL_TRANSCRIPT':
                setFinalTranscript(serverEvent.transcript);
                setPartialTranscript('');
                break;

              case 'PROCESSING':
                setStatus('processing');
                break;

              case 'PROPOSAL_READY':
                setStatus('ready');
                setProposalReady(serverEvent);
                if (serverEvent.audio_b64) {
                  playTTSAudio(serverEvent.audio_b64);
                }
                break;

              case 'READ_ONLY_RESPONSE':
                setStatus('ready');
                setReadOnlyResponse(serverEvent);
                if (serverEvent.audio_b64) {
                  playTTSAudio(serverEvent.audio_b64);
                }
                break;

              case 'CLARIFICATION_REQUIRED':
                setStatus('ready');
                setClarification(serverEvent);
                if (serverEvent.audio_b64) {
                  playTTSAudio(serverEvent.audio_b64);
                }
                break;

              case 'TTS_AUDIO':
                if (serverEvent.audio_b64 && !audioElementRef.current) {
                  playTTSAudio(serverEvent.audio_b64);
                }
                break;

              case 'ERROR':
                setStatus('error');
                setErrorMessage(serverEvent.message || 'Voice engine error occurred.');
                break;
            }
          } catch (jsonErr) {
            console.error('Failed to parse WebSocket JSON event:', jsonErr);
          }
        }
      };

      ws.onerror = () => {
        setStatus('error');
        setErrorMessage('WebSocket connection failed.');
      };

      ws.onclose = () => {
        setStatus('disconnected');
        cleanupMedia();
      };
    } catch (connErr) {
      setStatus('error');
      setErrorMessage(`Failed to open WebSocket: ${connErr}`);
    }
  }, [storeId, language, cleanupMedia, playTTSAudio]);

  const disconnect = useCallback(() => {
    cleanupMedia();
    stopAudioPlayback();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, [cleanupMedia, stopAudioPlayback]);

  // Start real-time audio streaming (Push-to-Talk press)
  const startStreaming = useCallback(async () => {
    stopAudioPlayback();
    setErrorMessage(null);
    setPartialTranscript('');
    setProposalReady(null);
    setReadOnlyResponse(null);
    setClarification(null);

    // Ensure WebSocket is open; connect if necessary
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
    }

    try {
      // 1. Request microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Set up WebAudio pipeline
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      // ScriptProcessor bufferSize 2048 gives ~46ms blocks at 44.1k/48k
      const processor = audioCtx.createScriptProcessor(2048, 1, 1);
      processorRef.current = processor;

      isRecordingRef.current = true;
      setStatus('recording');

      // Send START_SESSION frame to reset server-side state
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            action: 'START_SESSION',
            language,
            store_id: storeId,
          })
        );
      }

      processor.onaudioprocess = (e) => {
        if (!isRecordingRef.current) return;

        const inputChannelData = e.inputBuffer.getChannelData(0);
        // Resample input buffer to 16,000 Hz
        const resampled = resampleTo16k(inputChannelData, audioCtx.sampleRate);
        // Convert to 16-bit linear PCM little-endian
        const pcmBuffer = float32ToInt16PCM(resampled);

        // Send over WebSocket as binary frame
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(pcmBuffer);
        }
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);
    } catch (micErr) {
      setStatus('error');
      setErrorMessage(
        micErr instanceof Error
          ? `Microphone error: ${micErr.message}`
          : 'Unable to access microphone. Please grant permission.'
      );
      cleanupMedia();
    }
  }, [connect, cleanupMedia, language, storeId, stopAudioPlayback]);

  // Stop streaming audio (Push-to-Talk release)
  const stopStreaming = useCallback(() => {
    if (!isRecordingRef.current) return;

    cleanupMedia();
    setStatus('processing');

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'END_AUDIO' }));
    }
  }, [cleanupMedia]);

  // Cancel streaming and discard audio
  const cancelStreaming = useCallback(() => {
    cleanupMedia();
    setPartialTranscript('');
    setStatus('ready');

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'CANCEL_SESSION' }));
    }
  }, [cleanupMedia]);

  const clearProposal = useCallback(() => {
    setProposalReady(null);
    setReadOnlyResponse(null);
    setClarification(null);
    setFinalTranscript('');
    setPartialTranscript('');
  }, []);

  // Auto-connect on mount if requested
  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    status,
    sessionId,
    partialTranscript,
    finalTranscript,
    proposalReady,
    readOnlyResponse,
    clarification,
    isPlayingTTS,
    errorMessage,
    connect,
    disconnect,
    startStreaming,
    stopStreaming,
    cancelStreaming,
    stopAudioPlayback,
    clearProposal,
  };
};
