import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Writes a 4 second mono WAV of one fundamental and its harmonics over faint noise, and returns
// the browser settings that play it, looped, as the microphone.
export function microphonePlaying(f0: number, harmonics = [0.3, 0.2, 0.12, 0.06]) {
  const rate = 48000;
  const samples = rate * 4;
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + samples * 2, 4);
  header.write("WAVEfmt ", 8);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(rate, 24);
  header.writeUInt32LE(rate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(samples * 2, 40);

  const data = Buffer.alloc(samples * 2);
  let seed = 12345;
  for (let i = 0; i < samples; i++) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    let v = (seed / 2 ** 32 - 0.5) * 0.004;
    harmonics.forEach((a, h) => (v += a * Math.sin((2 * Math.PI * f0 * (h + 1) * i) / rate)));
    data.writeInt16LE(Math.round(v * 32767), i * 2);
  }

  const dir = join(tmpdir(), "orbit-tones");
  mkdirSync(dir, { recursive: true });
  const file = join(dir, `tone-${f0}.wav`);
  writeFileSync(file, Buffer.concat([header, data]));
  return {
    permissions: ["microphone"],
    launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", `--use-file-for-fake-audio-capture=${file}`] },
  };
}
