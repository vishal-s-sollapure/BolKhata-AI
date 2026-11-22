/**
 * Resilient browser microphone hook using the standard MediaRecorder API.
 * Handles permissions, stream cleanup, state transitions, audio previewing,
 * and duration tracking for push-to-talk interactions.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { AudioRecordingState } from '../types/api';

export interface UseAudioRecorderResult {
  recordingState: AudioRecordingState;
  durationSeconds: number;
  audioBlob: Blob | null;
  audioUrl: string | null;
  errorMessage: string | null;
  isSupported: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  cancelRecording: () => void;
  resetAudio: () => void;
}

export const useAudioRecorder = (): UseAudioRecorderResult => {
  const [recordingState, setRecordingState] = useState<AudioRecordingState>('IDLE');
  const [durationSeconds, setDurationSeconds] = useState<number>(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  const isSupported = typeof window !== 'undefined' &&
    Boolean(navigator?.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function' && window.MediaRecorder);

  // Stop all active tracks on the microphone stream
  const cleanupStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop();
      });
      streamRef.current = null;
    }
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimer();
      cleanupStream();
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [clearTimer, cleanupStream, audioUrl]);

  const startRecording = useCallback(async () => {
    setErrorMessage(null);

    if (!isSupported) {
      setRecordingState('ERROR');
      setErrorMessage('Microphone recording is not supported in this browser.');
      return;
    }

    try {
      // 1. Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, // Mono
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;
      chunksRef.current = [];

      // Determine best supported mimeType
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : '';

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        clearTimer();
        cleanupStream();

        const duration = (Date.now() - startTimeRef.current) / 1000;

        // Empty or too short recording detection (< 300ms)
        if (chunksRef.current.length === 0 || duration < 0.3) {
          setRecordingState('ERROR');
          setErrorMessage('Empty or too short audio recording. Please speak clearly.');
          setAudioBlob(null);
          setAudioUrl(null);
          return;
        }

        const combinedBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        });

        const newAudioUrl = URL.createObjectURL(combinedBlob);
        setAudioBlob(combinedBlob);
        setAudioUrl(newAudioUrl);
        setRecordingState('TRANSCRIPT_READY');
      };

      recorder.onerror = () => {
        clearTimer();
        cleanupStream();
        setRecordingState('ERROR');
        setErrorMessage('An error occurred during microphone recording.');
      };

      // Start recording
      recorder.start(100); // 100ms time slices
      startTimeRef.current = Date.now();
      setRecordingState('RECORDING');
      setDurationSeconds(0);

      // Duration timer
      timerRef.current = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
        setDurationSeconds(elapsed);
      }, 500);
    } catch (err: unknown) {
      cleanupStream();
      clearTimer();
      setRecordingState('ERROR');

      if (err instanceof DOMException) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setErrorMessage('Microphone permission denied. Please allow microphone access in your browser.');
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          setErrorMessage('No microphone device found on this system.');
        } else {
          setErrorMessage(`Microphone error: ${err.message}`);
        }
      } else {
        setErrorMessage('Failed to access microphone.');
      }
    }
  }, [isSupported, cleanupStream, clearTimer]);

  const stopRecording = useCallback(async (): Promise<void> => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
      return;
    }

    setRecordingState('STOPPING');
    try {
      mediaRecorderRef.current.stop();
    } catch {
      cleanupStream();
      clearTimer();
      setRecordingState('IDLE');
    }
  }, [cleanupStream, clearTimer]);

  const cancelRecording = useCallback(() => {
    clearTimer();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // Ignore stop error on cancel
      }
    }
    cleanupStream();
    chunksRef.current = [];
    setAudioBlob(null);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    setDurationSeconds(0);
    setRecordingState('IDLE');
    setErrorMessage(null);
  }, [clearTimer, cleanupStream, audioUrl]);

  const resetAudio = useCallback(() => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    setAudioBlob(null);
    setAudioUrl(null);
    setDurationSeconds(0);
    setRecordingState('IDLE');
    setErrorMessage(null);
  }, [audioUrl]);

  return {
    recordingState,
    durationSeconds,
    audioBlob,
    audioUrl,
    errorMessage,
    isSupported,
    startRecording,
    stopRecording,
    cancelRecording,
    resetAudio,
  };
};
