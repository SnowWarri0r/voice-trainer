import { startCapture, type StopFn } from "./capture";
import { pushFrame, render, type TargetBand } from "./realtime-view";

const startBtn = document.getElementById("start") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLDivElement;
const canvas = document.getElementById("view") as HTMLCanvasElement;

let stop: StopFn | null = null;
let band: TargetBand = { f0_min: 165, f0_max: 220, resonance_min: 0.15, resonance_max: 0.7 };

async function loadTarget(): Promise<void> {
  try {
    const r = await fetch("/api/target");
    const t = await r.json();
    band = {
      f0_min: t.f0_min, f0_max: t.f0_max,
      resonance_min: t.resonance_min, resonance_max: t.resonance_max,
    };
  } catch {
    /* 用默认 band */
  }
}

function loop(): void {
  render(canvas, band);
  requestAnimationFrame(loop);
}

startBtn.addEventListener("click", async () => {
  if (stop) {
    stop();
    stop = null;
    startBtn.textContent = "开始";
    statusEl.textContent = "已停止";
    return;
  }
  await loadTarget();
  try {
    stop = await startCapture((d) => {
      pushFrame(d);
      statusEl.textContent = d.voiced
        ? `F0 ${d.f0 ? (d.f0 as number).toFixed(0) : "-"}Hz · 共鸣 ${
            typeof d.resonance === "number" ? (d.resonance as number).toFixed(2) : "-"
          } · ${d.in_target ? "在区 ✓" : "出区"}`
        : "听不到,说大声点";
    });
    startBtn.textContent = "停止";
    statusEl.textContent = "正在听…";
  } catch (e) {
    statusEl.textContent = "麦克风打不开,请检查权限";
  }
});

loop();
