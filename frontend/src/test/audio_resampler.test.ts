/**
 * Unit tests for audio resampling and PCM conversion utilities.
 */

import { describe, it, expect } from 'vitest';
import {
  resampleTo16k,
  float32ToInt16PCM,
  chunkPCMBuffer,
  TARGET_SAMPLE_RATE,
} from '../utils/audioResampler';

describe('Audio Resampler Utilities', () => {
  describe('resampleTo16k', () => {
    it('returns original buffer unchanged if already 16kHz', () => {
      const input = new Float32Array([0.1, -0.2, 0.5, -0.8]);
      const resampled = resampleTo16k(input, 16000);
      expect(resampled).toBe(input);
    });

    it('returns empty buffer for empty input', () => {
      const empty = new Float32Array(0);
      const resampled = resampleTo16k(empty, 48000);
      expect(resampled.length).toBe(0);
    });

    it('correctly downsamples from 48kHz to 16kHz (3:1 ratio)', () => {
      // 48,000 samples at 48kHz = 1 second
      const input = new Float32Array(48000);
      for (let i = 0; i < input.length; i++) {
        input[i] = Math.sin((2 * Math.PI * 440 * i) / 48000);
      }

      const resampled = resampleTo16k(input, 48000);
      // Downsampled buffer should have 16,000 samples (1 second)
      expect(resampled.length).toBe(16000);
      expect(TARGET_SAMPLE_RATE).toBe(16000);
    });

    it('correctly downsamples from 44.1kHz to 16kHz', () => {
      const input = new Float32Array(44100);
      const resampled = resampleTo16k(input, 44100);
      expect(resampled.length).toBe(16000);
    });
  });

  describe('float32ToInt16PCM', () => {
    it('converts float values to 16-bit signed PCM little-endian', () => {
      // 0.0 -> 0
      // 1.0 -> 32767
      // -1.0 -> -32768
      const input = new Float32Array([0.0, 1.0, -1.0, 0.5]);
      const pcmBuffer = float32ToInt16PCM(input);

      expect(pcmBuffer.byteLength).toBe(input.length * 2);

      const view = new DataView(pcmBuffer);
      expect(view.getInt16(0, true)).toBe(0);
      expect(view.getInt16(2, true)).toBe(32767);
      expect(view.getInt16(4, true)).toBe(-32768);
      expect(view.getInt16(6, true)).toBe(16384);
    });

    it('clamps values exceeding [-1.0, 1.0] to prevent overflow', () => {
      const input = new Float32Array([1.5, -2.0]);
      const pcmBuffer = float32ToInt16PCM(input);
      const view = new DataView(pcmBuffer);

      expect(view.getInt16(0, true)).toBe(32767);
      expect(view.getInt16(2, true)).toBe(-32768);
    });
  });

  describe('chunkPCMBuffer', () => {
    it('slices a buffer into 1024-byte uniform chunks', () => {
      // 2560 bytes = 2 full 1024-byte chunks + 1 512-byte chunk
      const buffer = new ArrayBuffer(2560);
      const chunks = chunkPCMBuffer(buffer, 1024);

      expect(chunks.length).toBe(3);
      expect(chunks[0].byteLength).toBe(1024);
      expect(chunks[1].byteLength).toBe(1024);
      expect(chunks[2].byteLength).toBe(512);
    });

    it('preserves 16-bit alignment for all emitted chunks', () => {
      const buffer = new ArrayBuffer(1024);
      const chunks = chunkPCMBuffer(buffer, 512);

      chunks.forEach((chunk) => {
        expect(chunk.byteLength % 2).toBe(0);
      });
    });
  });
});
