// 录一段定长 clip(Int16 PCM),返回字节与采样率。
async function recordClip(seconds: number): Promise<{ pcm: ArrayBuffer; sampleRate: number }> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
  const ctx = new AudioContext();
  if (ctx.state === "suspended") await ctx.resume();
  const source = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(2048, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0;
  const chunks: Int16Array[] = [];
  proc.onaudioprocess = (e) => {
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = Math.round(s * 32767);
    }
    chunks.push(i16);
  };
  source.connect(proc);
  proc.connect(mute);
  mute.connect(ctx.destination);

  await new Promise((r) => setTimeout(r, seconds * 1000));

  proc.disconnect();
  source.disconnect();
  mute.disconnect();
  const sampleRate = ctx.sampleRate;
  await ctx.close();
  stream.getTracks().forEach((t) => t.stop());

  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Int16Array(total);
  let off = 0;
  for (const c of chunks) {
    merged.set(c, off);
    off += c.length;
  }
  return { pcm: merged.buffer, sampleRate };
}

interface CalibResult {
  f1?: number;
  f2?: number;
  retake?: boolean;
}

async function calibrateOne(vowel: string, pcm: ArrayBuffer, sampleRate: number): Promise<CalibResult> {
  const r = await fetch(`/api/calibrate?vowel=${vowel}&sampleRate=${sampleRate}`, {
    method: "POST",
    body: pcm,
  });
  return r.json();
}

const VOWELS: { id: string; prompt: string }[] = [
  { id: "a", prompt: "啊(像 spa)" },
  { id: "e", prompt: "诶" },
  { id: "i", prompt: "衣" },
  { id: "o", prompt: "喔" },
  { id: "u", prompt: "呜" },
];

// 跑完整标定流;onStatus 用于把进度/提示显示给用户。成功返回 true。
export async function runCalibration(onStatus: (msg: string) => void): Promise<boolean> {
  const templates: Record<string, [number, number]> = {};
  for (let i = 0; i < VOWELS.length; i++) {
    const { id, prompt } = VOWELS[i];
    let ok = false;
    for (let attempt = 0; attempt < 3 && !ok; attempt++) {
      onStatus(`标定 ${i + 1}/5:拉长发「${prompt}」… 录音中`);
      const { pcm, sampleRate } = await recordClip(2.5);
      const res = await calibrateOne(id, pcm, sampleRate);
      if (res.retake || typeof res.f1 !== "number" || typeof res.f2 !== "number") {
        onStatus(`没录到稳定的「${prompt}」,再来一次…`);
        await new Promise((r) => setTimeout(r, 700));
        continue;
      }
      templates[id] = [res.f1, res.f2];
      ok = true;
      onStatus(`「${prompt}」✓ (F1 ${res.f1.toFixed(0)} · F2 ${res.f2.toFixed(0)})`);
      await new Promise((r) => setTimeout(r, 500));
    }
    if (!ok) {
      onStatus(`「${prompt}」多次未录到稳定元音,标定中止。`);
      return false;
    }
  }
  const r = await fetch("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vowel_templates: templates }),
  });
  if (!r.ok) {
    onStatus("保存个人模板失败。");
    return false;
  }
  onStatus("标定完成 ✓ 点「开始」即用个人模板。");
  return true;
}
