import { startCapture, type StopFn } from "./capture";
import { pushFrame, render, type TargetBand } from "./realtime-view";
import { runCalibration } from "./calibrate";

const startBtn = document.getElementById("start") as HTMLButtonElement;
const startLabel = startBtn.querySelector(".btn-label") as HTMLSpanElement;
const calibrateBtn = document.getElementById("calibrate") as HTMLButtonElement;
const canvas = document.getElementById("view") as HTMLCanvasElement;

const rdF0 = document.getElementById("rd-f0") as HTMLSpanElement;
const rdRes = document.getElementById("rd-res") as HTMLSpanElement;
const stateEl = document.getElementById("rd-state") as HTMLDivElement;
const stateText = document.getElementById("rd-state-text") as HTMLSpanElement;
const levelFill = document.getElementById("level-fill") as HTMLSpanElement;

const chip = document.getElementById("profile-chip") as HTMLDivElement;
const profileLabel = document.getElementById("profile-label") as HTMLSpanElement;

const calibBanner = document.getElementById("calib-banner") as HTMLDivElement;
const calibText = document.getElementById("calib-text") as HTMLSpanElement;

let stop: StopFn | null = null;
let band: TargetBand = { f0_min: 165, f0_max: 220, resonance_min: 0.15, resonance_max: 0.7 };

const LEVEL_FULL = 0.25;

// ---------- canvas sizing (crisp on HiDPI) ----------
const BASE_H = 320;
function fitCanvas(): void {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 800;
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(BASE_H * dpr);
}

// ---------- readouts ----------
type StateKind = "in" | "out" | "breathy" | "idle";
function setState(kind: StateKind, text: string): void {
  stateEl.className = `readout-value state state--${kind}`;
  stateText.textContent = text;
}

function updateReadouts(d: Record<string, any>): void {
  rdF0.textContent = d.voiced && typeof d.f0 === "number" ? Math.round(d.f0 as number).toString() : "—";
  rdRes.textContent =
    typeof d.resonance === "number" ? (d.resonance >= 0 ? "+" : "") + (d.resonance as number).toFixed(2) : "—";
  const t = Math.max(0, Math.min(1, (typeof d.level === "number" ? d.level : 0) / LEVEL_FULL));
  levelFill.style.width = `${(t * 100).toFixed(0)}%`;
  if (d.voiced) setState(d.in_target ? "in" : "out", d.in_target ? "在区" : "出区");
  else if (typeof d.resonance === "number") setState("breathy", "气声");
  else setState("idle", "听不到");
}

function resetReadouts(): void {
  rdF0.textContent = "—";
  rdRes.textContent = "—";
  levelFill.style.width = "0%";
  setState("idle", "待机");
}

async function loadTarget(): Promise<void> {
  try {
    const t = await (await fetch("/api/target")).json();
    band = { f0_min: t.f0_min, f0_max: t.f0_max, resonance_min: t.resonance_min, resonance_max: t.resonance_max };
  } catch {
    /* keep default band */
  }
}

async function loadProfileChip(): Promise<void> {
  try {
    const p = await (await fetch("/api/profile")).json();
    const calibrated = p.source === "calibrated";
    chip.className = `chip ${calibrated ? "chip--calibrated" : "chip--builtin"}`;
    profileLabel.textContent = calibrated ? "个人模板" : "通用模板";
  } catch {
    /* leave default chip */
  }
}

// ---------- render loop ----------
function loop(): void {
  render(canvas, band);
  requestAnimationFrame(loop);
}

// ---------- controls ----------
function stopListening(): void {
  if (stop) {
    stop();
    stop = null;
  }
  startBtn.classList.remove("listening");
  startLabel.textContent = "开始";
}

startBtn.addEventListener("click", async () => {
  if (stop) {
    stopListening();
    resetReadouts();
    return;
  }
  await loadTarget();
  try {
    stop = await startCapture((d) => {
      pushFrame(d);
      updateReadouts(d);
    });
    startBtn.classList.add("listening");
    startLabel.textContent = "停止";
  } catch (e) {
    setState("idle", "麦克风打不开");
  }
});

calibrateBtn.addEventListener("click", async () => {
  stopListening();
  resetReadouts();
  calibrateBtn.disabled = true;
  startBtn.disabled = true;
  calibBanner.hidden = false;
  let ok = false;
  try {
    ok = await runCalibration((msg) => {
      calibText.textContent = msg;
    });
    await loadTarget();
    await loadProfileChip();
  } catch (e) {
    calibText.textContent = "标定出错,请检查麦克风权限。";
  } finally {
    await new Promise((r) => setTimeout(r, ok ? 1200 : 1500));
    calibBanner.hidden = true;
    calibrateBtn.disabled = false;
    startBtn.disabled = false;
  }
});

// ---------- init ----------
fitCanvas();
window.addEventListener("resize", fitCanvas);
resetReadouts();
loadProfileChip();
loop();
