export type FrameHandler = (data: Record<string, unknown>) => void;
export type StopFn = () => void;

// 采麦克风 → Int16 PCM 块 → WebSocket;每帧分析结果回调给 onFrame。
export async function startCapture(onFrame: FrameHandler): Promise<StopFn> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
  const ctx = new AudioContext();
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
  const source = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(2048, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0; // 接到 destination 让 onaudioprocess 触发,但不外放(避免回声)

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => ws.send(JSON.stringify({ type: "hello", sampleRate: ctx.sampleRate }));
  ws.onmessage = (e) => onFrame(JSON.parse(e.data));

  proc.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = Math.round(s * 32767);
    }
    // 线格式约定:Int16 小端(LE),与后端 np.frombuffer("<i2") 对齐。
    // 现代浏览器一律小端平台,故 i16.buffer 的原生字节序即 LE。
    ws.send(i16.buffer);
  };

  source.connect(proc);
  proc.connect(mute);
  mute.connect(ctx.destination);

  return () => {
    proc.disconnect();
    source.disconnect();
    mute.disconnect();
    ws.close();
    ctx.close();
    stream.getTracks().forEach((t) => t.stop());
  };
}
