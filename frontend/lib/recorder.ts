// Browser audio capture for transcription.
//
// Captures microphone (and optionally system/tab audio), accumulates PCM, and
// every `intervalMs` encodes a 16 kHz mono WAV chunk and POSTs it to the
// backend /transcribe proxy. Encoding WAV in-browser means the external
// whisper.cpp server receives a format it accepts directly — no server-side
// conversion needed, which suits air-gapped deployments.

import { api } from "./api";

const TARGET_RATE = 16000;

function downsampleTo16k(input: Float32Array, inputRate: number): Float32Array {
  if (inputRate === TARGET_RATE) return input;
  const ratio = inputRate / TARGET_RATE;
  const outLength = Math.floor(input.length / ratio);
  const output = new Float32Array(outLength);
  for (let i = 0; i < outLength; i++) {
    output[i] = input[Math.floor(i * ratio)];
  }
  return output;
}

function encodeWav(samples: Float32Array): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, TARGET_RATE, true);
  view.setUint32(28, TARGET_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([view], { type: "audio/wav" });
}

export interface RecorderOptions {
  captureSystemAudio?: boolean;
  intervalMs?: number;
  onTranscript: (text: string) => void;
  onError?: (err: string) => void;
}

export class Recorder {
  private ctx?: AudioContext;
  private processor?: ScriptProcessorNode;
  private streams: MediaStream[] = [];
  private buffer: Float32Array[] = [];
  private timer?: ReturnType<typeof setInterval>;
  private opts: RecorderOptions;

  constructor(opts: RecorderOptions) {
    this.opts = opts;
  }

  async start() {
    const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.streams.push(mic);

    this.ctx = new AudioContext();
    const sources = [this.ctx.createMediaStreamSource(mic)];

    if (this.opts.captureSystemAudio) {
      try {
        const display = await navigator.mediaDevices.getDisplayMedia({
          audio: true,
          video: true,
        });
        this.streams.push(display);
        if (display.getAudioTracks().length > 0) {
          sources.push(this.ctx.createMediaStreamSource(display));
        }
      } catch (e) {
        this.opts.onError?.(`System audio capture declined: ${e}`);
      }
    }

    const merger = this.ctx.createGain();
    sources.forEach((s) => s.connect(merger));
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);
    merger.connect(this.processor);
    this.processor.connect(this.ctx.destination);

    const inputRate = this.ctx.sampleRate;
    this.processor.onaudioprocess = (e) => {
      const data = e.inputBuffer.getChannelData(0);
      this.buffer.push(downsampleTo16k(new Float32Array(data), inputRate));
    };

    this.timer = setInterval(() => this.flush(), this.opts.intervalMs ?? 6000);
  }

  private async flush() {
    if (this.buffer.length === 0) return;
    const total = this.buffer.reduce((n, b) => n + b.length, 0);
    const merged = new Float32Array(total);
    let off = 0;
    for (const b of this.buffer) {
      merged.set(b, off);
      off += b.length;
    }
    this.buffer = [];
    const wav = encodeWav(merged);
    try {
      const form = new FormData();
      form.append("file", wav, "chunk.wav");
      const res = await fetch(api.transcribeUrl(), {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const { text } = await res.json();
      if (text && text.trim()) this.opts.onTranscript(text.trim());
    } catch (e) {
      this.opts.onError?.(`Transcription failed: ${e}`);
    }
  }

  async stop() {
    if (this.timer) clearInterval(this.timer);
    await this.flush();
    this.processor?.disconnect();
    this.streams.forEach((s) => s.getTracks().forEach((t) => t.stop()));
    await this.ctx?.close();
  }
}
