import { startTransition, useEffect, useState } from "react";

import {
  activeGraphCandidate,
  agentCards,
  initialRuns,
  invalidGraphCandidate,
  persistenceStatus,
  roles,
  spriteManifest,
  type OperatorRole,
  type RunCard,
  type RunStatus,
} from "./data/sampleData";
import { t } from "./i18n/messages";
import { validateGraphCandidate } from "./lib/graphValidation";

type TabKey = "dashboard" | "control-room" | "interrupts" | "graph-editor" | "admin";

const statusCycle: Record<RunStatus, RunStatus> = {
  planning: "active",
  active: "review",
  review: "completed",
  paused: "active",
  dlq: "paused",
  completed: "planning",
};

const roleTabs: Record<OperatorRole, TabKey[]> = {
  viewer: ["dashboard", "control-room"],
  operator: ["dashboard", "control-room", "interrupts"],
  admin: ["dashboard", "control-room", "interrupts", "graph-editor", "admin"],
  "super-admin": ["dashboard", "control-room", "interrupts", "graph-editor", "admin"],
};

const liveTabLabels: Record<TabKey, string> = {
  dashboard: "Dashboard",
  "control-room": "Control Room",
  interrupts: "Interrupts",
  "graph-editor": "Graph Editor",
  admin: "Admin",
};

function roleRank(role: OperatorRole): number {
  return roles.indexOf(role);
}

function statusTone(status: RunStatus): string {
  return `status-pill status-${status}`;
}

function runStatusLabel(run: RunCard): string {
  return `${run.ticket} is ${run.status} at ${run.agent}`;
}

export default function App() {
  const locale = "en";
  const [role, setRole] = useState<OperatorRole>("viewer");
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [runs, setRuns] = useState<RunCard[]>(initialRuns);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [liveAnnouncement, setLiveAnnouncement] = useState("Dashboard connected to live updates.");
  const [graphSource, setGraphSource] = useState(
    JSON.stringify(activeGraphCandidate, null, 2),
  );
  const [uploadNotice, setUploadNotice] = useState("");
  const [dryRunNotice, setDryRunNotice] = useState("");

  const visibleTabs = roleTabs[role];
  const graphValidation = validateGraphCandidate(graphSource);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      startTransition(() => {
        setRuns((currentRuns) => {
          const updatedRuns = currentRuns.map((run, index) =>
            index === 0
              ? { ...run, status: statusCycle[run.status] }
              : run,
          );
          setLiveAnnouncement(runStatusLabel(updatedRuns[0]));
          return updatedRuns;
        });
      });
    }, 3500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!visibleTabs.includes(tab)) {
      setTab(visibleTabs[0]);
    }
  }, [tab, visibleTabs]);

  const pausedRuns = runs.filter((run) => run.status === "paused");
  const dlqRuns = runs.filter((run) => run.status === "dlq");

  return (
    <div className={reducedMotion ? "app-shell reduced-motion" : "app-shell"}>
      <div aria-live="polite" className="sr-only">
        {liveAnnouncement}
      </div>
      <header className="top-bar">
        <div>
          <p className="eyebrow">{t(locale, "appSubtitle")}</p>
          <h1>{t(locale, "appTitle")}</h1>
        </div>
        <div className="toolbar">
          <label>
            <span>{t(locale, "roleLabel")}</span>
            <select
              aria-label={t(locale, "roleLabel")}
              value={role}
              onChange={(event) => setRole(event.target.value as OperatorRole)}
            >
              {roles.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="toggle">
            <input
              checked={reducedMotion}
              onChange={(event) => setReducedMotion(event.target.checked)}
              type="checkbox"
            />
            <span>{t(locale, "reducedMotion")}</span>
          </label>
          <div className="locale-chip" aria-label={t(locale, "localeLabel")}>
            {t(locale, "localeValue")}
          </div>
        </div>
      </header>

      <main className="layout-grid">
        <aside className="nav-panel" aria-label="Operator navigation">
          <p className="panel-title">{t(locale, "liveStatus")}</p>
          <nav>
            {visibleTabs.map((item) => (
              <button
                className={item === tab ? "nav-button active" : "nav-button"}
                key={item}
                onClick={() => {
                  setTab(item);
                  setLiveAnnouncement(`${liveTabLabels[item]} opened.`);
                }}
                type="button"
              >
                {liveTabLabels[item]}
              </button>
            ))}
          </nav>
          {role === "super-admin" ? (
            <div className="global-scope">{t(locale, "globalScope")}</div>
          ) : null}
          <p className="support-copy">{t(locale, "englishOnly")}</p>
        </aside>

        <section className="content-panel">
          {tab === "dashboard" ? (
            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "activeRuns")}</h2>
                  <span className="legend">{t(locale, "runLegend")}</span>
                </div>
                <div className="run-grid">
                  {runs.map((run) => (
                    <article className="run-card" key={run.id}>
                      <div className="run-card-top">
                        <strong>{run.ticket}</strong>
                        <span className={statusTone(run.status)}>{run.status}</span>
                      </div>
                      <p>{run.lane}</p>
                      <p>{run.agent}</p>
                      <p>Retries: {run.retryCount}</p>
                      <p>Cost: ${run.costUsd.toFixed(2)}</p>
                      {run.status === "paused" && roleRank(role) >= roleRank("operator") ? (
                        <div className="button-row">
                          <button type="button">{t(locale, "breakGlass")}</button>
                          <button type="button">{t(locale, "retry")}</button>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : null}

          {tab === "control-room" ? (
            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "controlRoomHeading")}</h2>
                  <span className="legend">{t(locale, "spriteBundledOnly")}</span>
                </div>
                <div className="control-room" role="list">
                  {runs.map((run) => (
                    <div
                      aria-label={`${run.ticket} ${run.agent} ${run.status}`}
                      className="desk-lane"
                      key={run.id}
                      role="listitem"
                    >
                      <div className={`sprite-tile sprite-${run.agent}`} aria-hidden="true" />
                      <div className="desk-copy">
                        <strong>{run.ticket}</strong>
                        <span>{run.agent}</span>
                        <span className={statusTone(run.status)}>{run.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "spriteHeading")}</h2>
                  <button
                    onClick={() => setUploadNotice(t(locale, "uploadDeferred"))}
                    type="button"
                  >
                    {t(locale, "uploadSprite")}
                  </button>
                </div>
                {uploadNotice ? <p className="notice">{uploadNotice}</p> : null}
                <ul className="manifest-list">
                  {spriteManifest.map((entry) => (
                    <li key={entry.spriteId}>
                      <code>{entry.spriteId}</code> - {entry.sourceKind} - {entry.path}
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          ) : null}

          {tab === "interrupts" ? (
            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "breakGlass")}</h2>
                  <span className="legend">{pausedRuns.length} pending</span>
                </div>
                <div className="run-grid">
                  {pausedRuns.map((run) => (
                    <article className="run-card" key={run.id}>
                      <strong>{run.ticket}</strong>
                      <p>{run.agent}</p>
                      <p className="notice">Paused on registered exception path.</p>
                      <div className="button-row">
                        <button type="button">{t(locale, "approve")}</button>
                        <button type="button">{t(locale, "dismiss")}</button>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "dlqTitle")}</h2>
                  <span className="legend">{dlqRuns.length} records</span>
                </div>
                <div className="run-grid">
                  {dlqRuns.map((run) => (
                    <article className="run-card" key={run.id}>
                      <strong>{run.ticket}</strong>
                      <p>Last stage: {run.agent}</p>
                      <div className="button-row">
                        <button type="button">{t(locale, "retry")}</button>
                        <button type="button">{t(locale, "dismiss")}</button>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : null}

          {tab === "graph-editor" ? (
            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "graphEditor")}</h2>
                  <span className="legend">{t(locale, "readOnlyGraph")}</span>
                </div>
                <p className="notice">{t(locale, "graphParityGap")}</p>
                <div className="button-row">
                  <button
                    onClick={() =>
                      setGraphSource(JSON.stringify(activeGraphCandidate, null, 2))
                    }
                    type="button"
                  >
                    {t(locale, "loadActiveGraph")}
                  </button>
                  <button
                    onClick={() =>
                      setGraphSource(JSON.stringify(invalidGraphCandidate, null, 2))
                    }
                    type="button"
                  >
                    {t(locale, "loadInvalidGraph")}
                  </button>
                </div>
                <div className="graph-layout">
                  <textarea
                    aria-label={t(locale, "exportHeading")}
                    className="graph-source"
                    onChange={(event) => setGraphSource(event.target.value)}
                    value={graphSource}
                  />
                  <div className="graph-summary">
                    <h3>{t(locale, "validationHeading")}</h3>
                    {graphValidation.valid ? (
                      <p className="success">Candidate matches protected invariants.</p>
                    ) : (
                      <ul className="error-list">
                        {graphValidation.errors.map((error) => (
                          <li key={error}>{error}</li>
                        ))}
                      </ul>
                    )}
                    <div className="protected-note">
                      <strong>{t(locale, "graphProtected")}</strong>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          ) : null}

          {tab === "admin" ? (
            <div className="stack">
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "admin")}</h2>
                  <span className="legend">{t(locale, "shadowEvidence")}</span>
                </div>
                <div className="run-grid">
                  {agentCards.map((card) => (
                    <article className="run-card" key={card.role}>
                      <strong>{card.role}</strong>
                      <p>{card.model}</p>
                      <p>{card.retryBudget}</p>
                      <p>{card.tools.join(", ")}</p>
                      <button
                        onClick={() =>
                          setDryRunNotice(t(locale, "dryRunSuccess"))
                        }
                        type="button"
                      >
                        Dry-run
                      </button>
                    </article>
                  ))}
                </div>
                {dryRunNotice ? <p className="notice">{dryRunNotice}</p> : null}
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "metrics")}</h2>
                  <span className="legend">{t(locale, "costs")}</span>
                </div>
                <div className="metrics-grid">
                  <div className="metric-card">
                    <span>Shadow pass rate</span>
                    <strong>96%</strong>
                  </div>
                  <div className="metric-card">
                    <span>Ticket budget burn</span>
                    <strong>$12.00</strong>
                  </div>
                  <div className="metric-card">
                    <span>Fallbacks today</span>
                    <strong>4</strong>
                  </div>
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>{t(locale, "persistenceStatus")}</h2>
                  <span className="legend">Text labels mirror color state.</span>
                </div>
                <div className="status-grid">
                  <article className="metric-card">
                    <span>{t(locale, "migrationVersion")}</span>
                    <strong>{persistenceStatus.migrationVersion}</strong>
                  </article>
                  <article className="metric-card">
                    <span>{t(locale, "appliedVersion")}</span>
                    <strong>{persistenceStatus.appliedVersion}</strong>
                  </article>
                  <article className="metric-card">
                    <span>{t(locale, "activeSnapshot")}</span>
                    <strong>{persistenceStatus.activeSnapshotId}</strong>
                  </article>
                </div>
                <h3>{t(locale, "adapterReadiness")}</h3>
                <div className="status-grid" role="list">
                  {persistenceStatus.adapters.map((adapter) => (
                    <article className="run-card" key={adapter.name} role="listitem">
                      <strong>{adapter.name}</strong>
                      <p>
                        {t(locale, "configured")}: {adapter.configured ? "yes" : "no"}
                      </p>
                      <p>
                        {t(locale, "healthy")}: {adapter.healthy ? "yes" : "no"}
                      </p>
                      <span
                        className={
                          adapter.healthy ? "status-pill status-completed" : "status-pill status-paused"
                        }
                      >
                        {adapter.healthy ? t(locale, "healthy") : t(locale, "degraded")}
                      </span>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}
