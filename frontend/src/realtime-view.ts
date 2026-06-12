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
const levelHist: number[] = [];

// 显示范围(纵轴映射)
const F0_LO = 80, F0_HI = 300;        // Hz
const RES_LO = -0.4, RES_HI = 1.0;     // 八度
const LEVEL_FULL = 0.25;               // RMS 到此值时线最粗最实(强度满)

// 配色(与 CSS 仪表主题一致)
const C_IN = "#5fe39a";
const C_OUT = "#ff6a6a";
const C_GRID = "rgba(170,190,180,0.06)";
const C_GRID_STRONG = "rgba(170,190,180,0.10)";
const C_TICK = "rgba(127,138,131,0.65)";
const C_BAND = "rgba(95,227,154,0.09)";
const C_BAND_EDGE = "rgba(95,227,154,0.40)";

interface Tick { v: number; label: string; }

export function pushFrame(d: Record<string, any>): void {
  pitchHist.push(d.voiced ? (d.f0 as number) : null);
  resHist.push(typeof d.resonance === "number" ? d.resonance : null);
  f0InHist.push(Boolean(d.f0_in));
  resInHist.push(Boolean(d.resonance_in));
  levelHist.push(typeof d.level === "number" ? d.level : 0);
  if (pitchHist.length > MAXLEN) {
    pitchHist.shift();
    resHist.shift();
    f0InHist.shift();
    resInHist.shift();
    levelHist.shift();
  }
}

function mapY(v: number, lo: number, hi: number, top: number, h: number): number {
  const clamped = Math.max(lo, Math.min(hi, v));
  return top + h - ((clamped - lo) / (hi - lo)) * h;
}

export function render(cv: HTMLCanvasElement, band: TargetBand): void {
  const ctx = cv.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const W = cv.width / dpr;
  const H = cv.height / dpr;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const gap = 18;
  const trackH = (H - gap) / 2;

  drawTrack(
    ctx, "PITCH", "Hz", 0, trackH, W,
    pitchHist, f0InHist,
    (v) => mapY(v, F0_LO, F0_HI, 0, trackH),
    mapY(band.f0_min, F0_LO, F0_HI, 0, trackH),
    mapY(band.f0_max, F0_LO, F0_HI, 0, trackH),
    [
      { v: 250, label: "250" },
      { v: 200, label: "200" },
      { v: 150, label: "150" },
      { v: 100, label: "100" },
    ].map((t) => ({ y: mapY(t.v, F0_LO, F0_HI, 0, trackH), label: t.label })),
  );

  const top2 = trackH + gap;
  drawTrack(
    ctx, "RESONANCE", "oct", top2, trackH, W,
    resHist, resInHist,
    (v) => mapY(v, RES_LO, RES_HI, top2, trackH),
    mapY(band.resonance_min, RES_LO, RES_HI, top2, trackH),
    mapY(band.resonance_max, RES_LO, RES_HI, top2, trackH),
    [
      { v: 1.0, label: "+1.0" },
      { v: 0.5, label: "+0.5" },
      { v: 0.0, label: " 0.0" },
    ].map((t) => ({ y: mapY(t.v, RES_LO, RES_HI, top2, trackH), label: t.label })),
  );

  ctx.restore();
}

function drawTrack(
  ctx: CanvasRenderingContext2D,
  label: string,
  unit: string,
  top: number,
  h: number,
  W: number,
  hist: (number | null)[],
  inFlags: boolean[],
  yOf: (v: number) => number,
  bandTopY: number,
  bandBotY: number,
  ticks: { y: number; label: string }[],
): void {
  // 面板底
  ctx.fillStyle = "rgba(0,0,0,0.18)";
  roundRect(ctx, 0, top, W, h, 6);
  ctx.fill();

  // 垂直栅格(示波器 reticle)
  ctx.strokeStyle = C_GRID;
  ctx.lineWidth = 1;
  const cols = 16;
  for (let i = 1; i < cols; i++) {
    const x = (W / cols) * i;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + h);
    ctx.stroke();
  }
  // 水平刻度线 + 标签
  ctx.font = "10px 'IBM Plex Mono', monospace";
  ctx.textBaseline = "middle";
  for (const t of ticks) {
    ctx.strokeStyle = C_GRID_STRONG;
    ctx.beginPath();
    ctx.moveTo(34, t.y);
    ctx.lineTo(W, t.y);
    ctx.stroke();
    ctx.fillStyle = C_TICK;
    ctx.textAlign = "left";
    ctx.fillText(t.label, 4, t.y);
  }

  // 目标带
  ctx.fillStyle = C_BAND;
  ctx.fillRect(0, bandTopY, W, bandBotY - bandTopY);
  ctx.strokeStyle = C_BAND_EDGE;
  ctx.setLineDash([5, 5]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, bandTopY); ctx.lineTo(W, bandTopY);
  ctx.moveTo(0, bandBotY); ctx.lineTo(W, bandBotY);
  ctx.stroke();
  ctx.setLineDash([]);

  // 轨标签 + TARGET
  ctx.font = "600 10px 'IBM Plex Mono', monospace";
  ctx.fillStyle = "rgba(127,138,131,0.85)";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(`${label} · ${unit}`, 8, top + 7);
  ctx.fillStyle = C_BAND_EDGE;
  ctx.textAlign = "right";
  ctx.fillText("TARGET", W - 8, Math.min(bandTopY, bandBotY) + 3);

  // 连续辉光轮廓线:逐段连接相邻非空点,无声处断开;线宽+不透明度跟音量走
  const step = W / MAXLEN;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  let prevX = 0, prevY = 0, hasPrev = false;
  for (let i = 0; i < hist.length; i++) {
    const v = hist[i];
    if (v === null) { hasPrev = false; continue; }
    const x = i * step;
    const y = yOf(v);
    if (hasPrev) {
      const t = Math.max(0, Math.min(1, levelHist[i] / LEVEL_FULL));
      const color = inFlags[i] ? C_IN : C_OUT;
      ctx.lineWidth = 1.3 + 3.0 * t;
      ctx.globalAlpha = 0.4 + 0.6 * t;
      ctx.strokeStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 5 + 9 * t;
      ctx.beginPath();
      ctx.moveTo(prevX, prevY);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    prevX = x; prevY = y; hasPrev = true;
  }
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;

  // 当前位置辉光圆点(最近一个非空点)
  for (let i = hist.length - 1; i >= 0; i--) {
    const v = hist[i];
    if (v === null) continue;
    const x = i * step;
    const y = yOf(v);
    const color = inFlags[i] ? C_IN : C_OUT;
    ctx.shadowColor = color;
    ctx.shadowBlur = 14;
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#fff";
    ctx.beginPath(); ctx.arc(x, y, 1.6, 0, Math.PI * 2); ctx.fill();
    break;
  }
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
