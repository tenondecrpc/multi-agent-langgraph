import { useEffect, useRef, useState } from "react";

import type { GraphCandidate } from "../data/sampleData";
import { t } from "../i18n/messages";
import { buildSimulationPlan, type SimulationPlan } from "../lib/graphSimulator";
import DynamicPixelOffice from "./DynamicPixelOffice";

type SimState = "idle" | "running" | "paused" | "blocked" | "completed";

type Props = {
  candidate: GraphCandidate;
  reducedMotion: boolean;
};

const locale = "en";
const SIM_STEP_DELAY_MS = 5000;

const simStateLabel: Record<SimState, string> = {
  idle: "simulatorIdle",
  running: "simulatorRunning",
  paused: "simulatorPaused",
  blocked: "simulatorInvariantBlocked",
  completed: "simulatorCompleted",
} as const;

export default function FlowSimulator({ candidate, reducedMotion }: Props) {
  const [plan] = useState<SimulationPlan>(() => buildSimulationPlan(candidate));
  const isBlocked = plan.protectedInvariantErrors.length > 0;

  const [simState, setSimState] = useState<SimState>(isBlocked ? "blocked" : "idle");
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [log, setLog] = useState<string[]>([]);
  const [slowMode, setSlowMode] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startButtonRef = useRef<HTMLButtonElement>(null);
  const simStateRef = useRef<SimState>(isBlocked ? "blocked" : "idle");
  const slowModeRef = useRef(false);
  const reducedMotionRef = useRef(reducedMotion);

  useEffect(() => {
    reducedMotionRef.current = reducedMotion;
    if (reducedMotion && simStateRef.current === "running") {
      clearTimer();
      setSimState("paused");
      simStateRef.current = "paused";
    }
  }, [reducedMotion]);

  useEffect(() => {
    slowModeRef.current = slowMode;
  }, [slowMode]);

  useEffect(() => {
    return clearTimer;
  }, []);

  function clearTimer() {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function formatLogEntry(index: number) {
    const step = plan.steps[index];
    const protectedLabel = step.isProtected ? "protected workflow node" : "unprotected node";
    return `Step ${index + 1}: ${step.nodeId} (${step.label}) - transition ${step.transitionReason} - ${protectedLabel} - ${step.narration}`;
  }

  function appendLog(index: number) {
    setLog((prev) => [formatLogEntry(index), ...prev]);
  }

  function advanceFrom(fromIndex: number) {
    if (simStateRef.current !== "running") return;

    const nextIndex = fromIndex + 1;
    if (nextIndex >= plan.steps.length) {
      setSimState("completed");
      simStateRef.current = "completed";
      return;
    }

    setCurrentIndex(nextIndex);
    appendLog(nextIndex);

    if (slowModeRef.current && !reducedMotionRef.current) {
      timerRef.current = setTimeout(() => advanceFrom(nextIndex), SIM_STEP_DELAY_MS);
    }
  }

  function instantRunFrom(fromIndex: number) {
    const remaining = plan.steps.slice(fromIndex + 1);
    if (remaining.length === 0) {
      setSimState("completed");
      simStateRef.current = "completed";
      return;
    }
    const newEntries = remaining.map(
      (_s, i) => formatLogEntry(fromIndex + i + 1),
    );
    setLog((prev) => [...newEntries.reverse(), ...prev]);
    setCurrentIndex(plan.steps.length - 1);
    setSimState("completed");
    simStateRef.current = "completed";
  }

  function handleStart() {
    if (isBlocked || plan.steps.length === 0) return;
    clearTimer();
    setCurrentIndex(0);
    setLog([formatLogEntry(0)]);

    const slowAutoAdvance = slowModeRef.current && !reducedMotionRef.current;

    if (!slowModeRef.current) {
      // Instant mode: run all steps now
      instantRunFrom(0);
      return;
    }

    if (!slowAutoAdvance) {
      // Slow mode + reduced motion: show step 0, stay paused for manual stepping
      setSimState("paused");
      simStateRef.current = "paused";
      return;
    }

    // Slow mode + auto-advance
    setSimState("running");
    simStateRef.current = "running";
    if (plan.steps.length > 1) {
      timerRef.current = setTimeout(() => advanceFrom(0), SIM_STEP_DELAY_MS);
    } else {
      setSimState("completed");
      simStateRef.current = "completed";
    }
  }

  function handlePause() {
    clearTimer();
    setSimState("paused");
    simStateRef.current = "paused";
  }

  function handleResume() {
    if (isBlocked || simState !== "paused") return;

    if (!slowModeRef.current) {
      // Instant mode: run remaining steps now
      instantRunFrom(currentIndex);
      return;
    }

    if (reducedMotionRef.current) {
      // Slow mode + reduced motion: Resume is disabled; nothing to schedule
      return;
    }

    // Slow mode + auto-advance
    setSimState("running");
    simStateRef.current = "running";
    timerRef.current = setTimeout(() => advanceFrom(currentIndex), SIM_STEP_DELAY_MS);
  }

  function handleStep() {
    if (isBlocked || simState === "completed") return;
    clearTimer();

    const fromIndex = simState === "idle" ? -1 : currentIndex;
    const nextIndex = fromIndex + 1;

    if (nextIndex >= plan.steps.length) {
      setSimState("completed");
      simStateRef.current = "completed";
      return;
    }

    setCurrentIndex(nextIndex);
    if (nextIndex === 0) {
      setLog([formatLogEntry(0)]);
    } else {
      appendLog(nextIndex);
    }

    const newState = nextIndex === plan.steps.length - 1 ? "completed" : "paused";
    setSimState(newState);
    simStateRef.current = newState;
  }

  function handleReset() {
    clearTimer();
    setCurrentIndex(-1);
    setLog([]);
    const newState: SimState = isBlocked ? "blocked" : "idle";
    setSimState(newState);
    simStateRef.current = newState;
    setTimeout(() => {
      startButtonRef.current?.focus();
    }, 0);
  }

  const canStart = !isBlocked && (simState === "idle" || simState === "completed");
  const canPause = simState === "running";
  const canResume = !isBlocked && simState === "paused" && !(slowMode && reducedMotion);
  const canStep = !isBlocked && simState !== "completed" && simState !== "blocked";
  const canReset = simState !== "idle" && simState !== "blocked";
  const currentStep =
    currentIndex >= 0 && currentIndex < plan.steps.length ? plan.steps[currentIndex] : null;

  return (
    <div className="flow-simulator">
      <p className="flow-simulator-notice" role="note">
        {t(locale, "flowSimulatorOnlyNotice")}
      </p>

      {isBlocked ? (
        <div className="flow-simulator-errors" role="alert">
          <p>{t(locale, "simulatorInvariantBlocked")}</p>
          <ul className="error-list">
            {plan.protectedInvariantErrors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flow-simulator-status">
        <span className={`status-pill sim-state-${simState}`}>
          {t(locale, simStateLabel[simState] as Parameters<typeof t>[1])}
        </span>
        {currentIndex >= 0 && currentIndex < plan.steps.length ? (
          <span className="sim-current-step">
            {`Current step: ${plan.steps[currentIndex].nodeId} (${plan.steps[currentIndex].label}) - transition ${plan.steps[currentIndex].transitionReason}`}
          </span>
        ) : null}
      </div>

      {currentStep ? (
        <>
          <DynamicPixelOffice
            currentStep={currentStep}
            reducedMotion={reducedMotion}
            running={simState === "running"}
          />
          <section className="agent-step-summary" aria-label="Current step details">
            <dl className="agent-step-facts">
              <div>
                <dt>Node</dt>
                <dd>{currentStep.nodeId}</dd>
              </div>
              <div>
                <dt>Transition</dt>
                <dd>{currentStep.transitionReason}</dd>
              </div>
              <div>
                <dt>Protection</dt>
                <dd>
                  {currentStep.isProtected ? "Protected workflow node" : "Unprotected node"}
                </dd>
              </div>
              <div>
                <dt>Repository write</dt>
                <dd>{currentStep.writesRepo ? "Writes repository" : "Read-only step"}</dd>
              </div>
            </dl>
            <p>{currentStep.narration}</p>
          </section>
        </>
      ) : null}

      {plan.steps.length > 0 ? (
        <div className="flow-simulator-node-strip" role="list" aria-label="Pipeline nodes">
          {plan.steps.map((step, i) => (
            <div
              key={step.nodeId}
              className={`sim-node${i === currentIndex ? " sim-node-current" : ""}`}
              role="listitem"
              aria-current={i === currentIndex ? "step" : undefined}
            >
              <span className="sim-node-label">{step.label}</span>
              {i === currentIndex ? (
                <span className="sim-node-current-indicator">[current]</span>
              ) : null}
              {step.isProtected ? (
                <span className="sim-node-protected" aria-label="protected workflow node">
                  P
                </span>
              ) : null}
              {step.writesRepo ? (
                <span className="sim-node-writes-repo" aria-label="writes to repository">
                  W
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <label className="flow-simulator-slow-mode toggle">
        <input
          type="checkbox"
          checked={slowMode}
          onChange={(e) => setSlowMode(e.target.checked)}
          disabled={simState === "running"}
        />
        <span>{t(locale, "slowModeLabel")}</span>
      </label>

      {slowMode && reducedMotion ? (
        <p className="flow-simulator-reduced-notice notice">
          {t(locale, "simulatorReducedMotionNotice")}
        </p>
      ) : null}

      <div className="flow-simulator-controls button-row">
        <button
          ref={startButtonRef}
          type="button"
          onClick={handleStart}
          disabled={!canStart}
        >
          {t(locale, "simulatorStart")}
        </button>
        <button type="button" onClick={handlePause} disabled={!canPause}>
          {t(locale, "simulatorPause")}
        </button>
        <button type="button" onClick={handleResume} disabled={!canResume}>
          {t(locale, "simulatorResume")}
        </button>
        <button type="button" onClick={handleStep} disabled={!canStep}>
          {t(locale, "simulatorStep")}
        </button>
        <button type="button" onClick={handleReset} disabled={!canReset}>
          {t(locale, "simulatorReset")}
        </button>
      </div>

      <div className="flow-simulator-log">
        <h3>{t(locale, "simulatorLogHeading")}</h3>
        <ol className="sim-log-list" role="log" aria-live="polite">
          {log.map((entry, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <li key={i}>{entry}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
