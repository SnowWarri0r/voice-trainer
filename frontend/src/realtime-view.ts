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

  // 连续轮廓线:逐段连接相邻非空点,无声处断开;
  // 线宽 + 不透明度跟音量(level)走;在区绿、出区红(按当前点)。
  const step = W / MAXLEN;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  let prevX = 0, prevY = 0, hasPrev = false;
  for (let i = 0; i < hist.length; i++) {
    const v = hist[i];
    if (v === null) {
      hasPrev = false;
      continue;
    }
    const x = i * step;
    const y = yOf(v);
    if (hasPrev) {
      const t = Math.max(0, Math.min(1, levelHist[i] / LEVEL_FULL));
      ctx.lineWidth = 1.2 + 3.0 * t;
      ctx.globalAlpha = 0.35 + 0.65 * t;
      ctx.strokeStyle = inFlags[i] ? "#40c878" : "#ff5a6a";
      ctx.beginPath();
      ctx.moveTo(prevX, prevY);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    prevX = x;
    prevY = y;
    hasPrev = true;
  }
  ctx.globalAlpha = 1;

  // 当前位置圆点(最近一个非空点)
  for (let i = hist.length - 1; i >= 0; i--) {
    const v = hist[i];
    if (v === null) continue;
    const x = i * step;
    const y = yOf(v);
    ctx.fillStyle = inFlags[i] ? "#40c878" : "#ff5a6a";
    ctx.beginPath(); ctx.arc(x, y, 3.8, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.beginPath(); ctx.arc(x, y, 1.5, 0, Math.PI * 2); ctx.fill();
    break;
  }
}
