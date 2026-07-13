import { useEffect } from "react";
import { MemoryRouter } from "react-router-dom";
import OmniApp from "../omni/App";
import { AuthProvider } from "../omni/auth/AuthProvider";
import { startHealthMonitor } from "../omni/lib/health";
import { autoSyncOnLaunch } from "../omni/lib/autoSync";
import "../omni/styles/index.css";

let omniStarted = false;

/**
 * The complete MUSE Atlas command center, bundled natively inside the desktop
 * webview. MemoryRouter keeps its twenty internal destinations isolated from
 * the desktop shell's hash route while preserving every Omni workflow.
 */
export function Omni() {
  useEffect(() => {
    if (!omniStarted) {
      omniStarted = true;
      startHealthMonitor();
      void autoSyncOnLaunch();
    }

    // Drive the global light pool from the real pointer position. CSS variables
    // keep every route synchronized without causing React renders on pointermove.
    const root = document.querySelector<HTMLElement>(".omni-workspace");
    if (!root) return;
    let frame = 0;
    let x = 50;
    let y = 36;
    const paint = () => {
      frame = 0;
      root.style.setProperty("--pointer-x", `${x.toFixed(2)}%`);
      root.style.setProperty("--pointer-y", `${y.toFixed(2)}%`);
    };
    const move = (event: PointerEvent) => {
      x = (event.clientX / Math.max(window.innerWidth, 1)) * 100;
      y = (event.clientY / Math.max(window.innerHeight, 1)) * 100;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      window.removeEventListener("pointermove", move);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="omni-workspace" aria-label="MUSE Atlas command center">
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <OmniApp />
        </AuthProvider>
      </MemoryRouter>
    </div>
  );
}

export default Omni;
