/**
 * WelcomeOnboarding — First-run experience for new MUSE users.
 *
 * Shows a beautiful welcome screen with quick setup:
 * - Model selection
 * - Key features tour
 * - Quick start tips
 * - Dismissible (saved in localStorage)
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  Terminal,
  Zap,
  Package,
  Clock,
  X,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "muse-onboarding-dismissed";

const FEATURES = [
  {
    icon: Terminal,
    title: "Chat Controls Everything",
    desc: "Type commands or use quick actions. MUSE can navigate, configure, and manage the entire dashboard.",
  },
  {
    icon: Zap,
    title: "Multi-Model Fusion",
    desc: "NVIDIA aggregator fuses responses from GPT-5.5, GLM-5.2, LongCat-2.0, and Gemini for best results.",
  },
  {
    icon: Package,
    title: "133 Skills Built-in",
    desc: "From coding to research to creative writing. Browse, search, and enable skills from the marketplace.",
  },
  {
    icon: Clock,
    title: "Autonomous Cron Jobs",
    desc: "Schedule recurring tasks, monitor systems, and run agents on autopilot 24/7.",
  },
];

const TIPS = [
  "Press Cmd+K anytime to open the command palette",
  "Type /status in chat to check system health",
  "Click Studio for the full-screen cockpit view",
  "Use /model to switch AI models on the fly",
];

export function WelcomeOnboarding() {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    // Do not auto-open an overlay on dashboard load. It sits above the
    // navigation rail and makes the tabs feel broken in fresh browsers.
    // Keep the dismiss marker so older sessions with the first-run overlay
    // also stop seeing it after this build.
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* storage may be blocked */
    }
    setVisible(false);
  }, []);

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* storage may be blocked */
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 backdrop-blur-lg">
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/10 bg-zinc-950 shadow-2xl"
        style={{ animation: "museOnboardIn 0.3s cubic-bezier(0.16,1,0.3,1)" }}
      >
        {/* Close button */}
        <button
          onClick={dismiss}
          className="absolute right-4 top-4 z-10 rounded-full p-1.5 text-zinc-600 transition-colors hover:bg-white/10 hover:text-zinc-300"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Content per step */}
        {step === 0 && (
          <div className="p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-500/10">
                <Sparkles className="h-6 w-6 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-zinc-100">MUSE</h1>
                <p className="text-xs uppercase tracking-widest text-zinc-500">
                  Multi-Use Synaptic Entity
                </p>
              </div>
            </div>

            <p className="mb-6 text-sm leading-relaxed text-zinc-400">
              Your autonomous AI partner. Chat controls everything — from
              navigating the dashboard to switching models, managing cron jobs,
              and generating content. Powered by multi-model fusion for the
              best possible results.
            </p>

            <div className="grid grid-cols-2 gap-3">
              {FEATURES.map((f) => {
                const Icon = f.icon;
                return (
                  <div
                    key={f.title}
                    className="rounded-xl border border-white/5 bg-white/[0.02] p-3"
                  >
                    <Icon className="mb-2 h-4 w-4 text-cyan-400/70" />
                    <div className="mb-1 text-xs font-semibold text-zinc-200">
                      {f.title}
                    </div>
                    <p className="text-[0.65rem] leading-relaxed text-zinc-500">
                      {f.desc}
                    </p>
                  </div>
                );
              })}
            </div>

            <button
              onClick={() => setStep(1)}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 py-3 text-sm font-semibold text-zinc-950 transition-all hover:bg-cyan-400"
            >
              Quick Tips
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {step === 1 && (
          <div className="p-8">
            <h2 className="mb-1 text-xl font-bold text-zinc-100">
              Power User Tips
            </h2>
            <p className="mb-6 text-xs text-zinc-500">
              Get the most out of MUSE from day one.
            </p>

            <div className="space-y-3">
              {TIPS.map((tip, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3"
                >
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-500/10 text-[0.65rem] font-bold text-cyan-400">
                    {i + 1}
                  </div>
                  <span className="text-xs text-zinc-300">{tip}</span>
                </div>
              ))}
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setStep(0)}
                className="flex-1 rounded-xl border border-white/10 bg-white/5 py-3 text-sm font-medium text-zinc-400 transition-colors hover:bg-white/10"
              >
                Back
              </button>
              <button
                onClick={() => {
                  dismiss();
                  navigate("/chat");
                }}
                className="flex flex-[2] items-center justify-center gap-2 rounded-xl bg-cyan-500 py-3 text-sm font-semibold text-zinc-950 transition-all hover:bg-cyan-400"
              >
                <Terminal className="h-4 w-4" />
                Start Chatting
              </button>
            </div>
          </div>
        )}

        {/* Progress dots */}
        <div className="flex justify-center gap-1.5 border-t border-white/[0.04] py-3">
          {[0, 1].map((s) => (
            <div
              key={s}
              className={cn(
                "h-1 rounded-full transition-all duration-200",
                s === step ? "w-6 bg-cyan-400" : "w-1.5 bg-zinc-700",
              )}
            />
          ))}
        </div>
      </div>

      <style>{`
        @keyframes museOnboardIn {
          from { transform: scale(0.95) translateY(8px); opacity: 0; }
          to { transform: scale(1) translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
