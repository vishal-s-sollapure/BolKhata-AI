/**
 * Audio resampler and PCM conversion utilities for BolKhata AI real-time voice streaming.
 *
 * Converts browser microphone Float32 audio buffers (sampled at e.g. 44.1kHz or 48kHz)
 * to standard 16,000 Hz Mono Signed 16-bit Linear PCM Little-Endian chunks required
 * by Gnani Prisma v3.0 Speech-To-Text WebSocket interface.
 */

export const TARGET_SAMPLE_RATE = 16000;
export const CHUNK_SAMPLE_COUNT = 512; // 512 samples = 1024 bytes (32ms at 16kHz)

/**
 * Resamples a Float32Array from a source sample rate down (or up) to 16,000 Hz using linear interpolation.
 */
export function resampleTo16k(inputBuffer: Float32Array, sourceSampleRate: number): Float32Array {
  if (sourceSampleRate === TARGET_SAMPLE_RATE) {
    return inputBuffer;
  }

  if (inputBuffer.length === 0) {
    return new Float32Array(0);
  }

  const ratio = sourceSampleRate / TARGET_SAMPLE_RATE;
  const newLength = Math.round(inputBuffer.length / ratio);
  const result = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const originalPos = i * ratio;
    const index = Math.floor(originalPos);
    const fraction = originalPos - index;

    const sample1 = inputBuffer[index] || 0;
    const sample2 = inputBuffer[index + 1] !== undefined ? inputBuffer[index + 1] : sample1;

    // Linear interpolation
    result[i] = sample1 + (sample2 - sample1) * fraction;
  }

  return result;
}

/**
 * Converts Float32 audio samples [-1.0, 1.0] to Signed 16-bit Linear PCM Little-Endian ArrayBuffer.
 */
export function float32ToInt16PCM(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);

  for (let i = 0; i < float32Array.length; i++) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    // Convert to 16-bit signed integer [-32768, 32767]
    const pcmSample = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff);
    // Write little-endian signed 16-bit integer
    view.setInt16(i * 2, pcmSample, true);
  }

  return buffer;
}

/**
 * Chunks a 16-bit PCM ArrayBuffer into uniform slices (default 1024 bytes = 512 samples = 32ms).
 */
export function chunkPCMBuffer(buffer: ArrayBuffer, chunkSize: number = 1024): ArrayBuffer[] {
  const chunks: ArrayBuffer[] = [];
  let offset = 0;

  while (offset < buffer.byteLength) {
    const end = Math.min(offset + chunkSize, buffer.byteLength);
    const chunk = buffer.slice(offset, end);
    // Only yield even byte chunks (valid 16-bit alignment)
    if (chunk.byteLength % 2 === 0 && chunk.byteLength > 0) {
      chunks.push(chunk);
    }
    offset = end;
  }

  return chunks;
}
