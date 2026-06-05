export interface TargetBand {
  f0_min: number;
  f0_max: number;
  resonance_min: number;
  resonance_max: number;
}

const MAXLEN = 300;
const pitchHist: (number | null)[] = [];
const resHist: (number | null)[] = [];
const f0InHist: boolean[] = [];
const resInHist: boolean[] = [];

// 显示范围(纵轴映射)
const F0_LO = 80, F0_HI = 300;        // Hz
const RES_LO = -0.4, RES_HI = 1.0;     // 八度

export function pushFrame(d: Record<string, any>): void {
  pitchHist.push(d.voiced ? (d.f0 as number) : null);
  resHist.push(typeof d.resonance === "number" ? d.resonance : null);
  f0InHist.push(Boolean(d.f0_in));
  resInHist.push(Boolean(d.resonance_in));
  if (pitchHist.length > MAXLEN) {
    pitchHist.shift();
    resHist.shift();
    f0InHist.shift();
    resInHist.shift();
  }
}

function mapY(v: number, lo: number, hi: number, top: number, h: number): number {
  const clamped = Math.max(lo, Math.min(hi, v));
  return top + h - ((clamped - lo) / (hi - lo)) * h;
}

export function render(cv: HTMLCanvasElement, band: TargetBand): void {
  const ctx = cv.getContext("2d");
  if (!ctx) return;
  const W = cv.width, H = cv.height;
  const trackH = H / 2 - 24;
  ctx.clearRect(0, 0, W, H);

  drawTrack(ctx, "音高 PITCH (Hz)", 8, trackH, W, pitchHist, f0InHist,
    (v) => mapY(v, F0_LO, F0_HI, 8, trackH),
    mapY(band.f0_min, F0_LO, F0_HI, 8, trackH),
    mapY(band.f0_max, F0_LO, F0_HI, 8, trackH));

  const top2 = H / 2 + 8;
  drawTrack(ctx, "共鸣 RESONANCE (八度)", top2, trackH, W, resHist, resInHist,
    (v) => mapY(v, RES_LO, RES_HI, top2, trackH),
    mapY(band.resonance_min, RES_LO, RES_HI, top2, trackH),
    mapY(band.resonance_max, RES_LO, RES_HI, top2, trackH));
}

function drawTrack(
  ctx: CanvasRenderingContext2D,
  label: string,
  top: number,
  h: number,
  W: number,
  hist: (number | null)[],
  inFlags: boolean[],
  yOf: (v: number) => number,
  bandTopY: number,
  bandBotY: number,
): void {
  // 目标带(绿色)
  ctx.fillStyle = "rgba(64,200,120,0.16)";
  ctx.fillRect(0, bandTopY, W, bandBotY - bandTopY);
  ctx.strokeStyle = "rgba(64,200,120,0.6)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(0, bandTopY); ctx.lineTo(W, bandTopY);
  ctx.moveTo(0, bandBotY); ctx.lineTo(W, bandBotY); ctx.stroke();
  ctx.setLineDash([]);
  // 标签
  ctx.fillStyle = "#8a93a3";
  ctx.font = "11px system-ui";
  ctx.fillText(label, 8, top + 14);
  // 曲线(逐点上色:该轨在区绿、出区红)
  const step = W / MAXLEN;
  for (let i = 0; i < hist.length; i++) {
    const v = hist[i];
    if (v === null) continue;
    const x = i * step;
    const y = yOf(v);
    ctx.fillStyle = inFlags[i] ? "#40c878" : "#ff5a6a";
    ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
  }
}
