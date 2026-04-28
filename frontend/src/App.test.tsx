import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import FlowSimulator from "./components/FlowSimulator";
import { activeGraphCandidate, invalidGraphCandidate } from "./data/sampleData";

const statusPagePayload = {
  schema_version: "public-status.v1",
  generated_at: "2026-04-26T12:00:00Z",
  status: "degraded",
  components: [
    {
      component: "api",
      status: "operational",
      message: "API health and readiness probes are available.",
    },
    {
      component: "workers",
      status: "degraded",
      message: "Worker dead-letter queue has pending failures.",
    },
  ],
};

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(statusPagePayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("filters navigation by role", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Graph Editor" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "admin" },
    });

    expect(screen.getByRole("button", { name: "Graph Editor" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Admin" })).toBeInTheDocument();
  });

  it("shows graph validation feedback for an invalid candidate", () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Graph Editor" }));
    fireEvent.click(screen.getByRole("button", { name: "Load invalid candidate" }));

    expect(
      screen.getByText(/Protected path is missing required node "reviewer"/),
    ).toBeInTheDocument();
  });

  it("surfaces the explicit sprite upload deferral message", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Control Room" }));
    fireEvent.click(screen.getByRole("button", { name: "Upload sprite" }));

    expect(
      screen.getByText("Upload API not implemented yet. Request would return 501."),
    ).toBeInTheDocument();
  });

  it("shows persistence status details in the admin panel", () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Admin" }));

    expect(screen.getByText("Persistence status")).toBeInTheDocument();
    expect(screen.getAllByText("20260418_0006")).toHaveLength(2);
    expect(screen.getByText("snapshot-prod-0042")).toBeInTheDocument();
    expect(screen.getAllByText("Healthy")).toHaveLength(3);
  });

  it("shows the deployment profile banner in the admin panel", () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Admin" }));

    expect(screen.getByRole("status", { name: "Deployment profile" })).toBeInTheDocument();
    expect(screen.getByText("air gapped")).toBeInTheDocument();
    expect(screen.getByText("OpenCode Go")).toBeInTheDocument();
    expect(screen.getByText("External telemetry disabled")).toBeInTheDocument();
    expect(screen.getByText("Internal status only")).toBeInTheDocument();
  });

  it("shows API deprecation timeline in the admin panel", () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Admin" }));

    expect(screen.getByText("API deprecations")).toBeInTheDocument();
    expect(screen.getByText("POST /api/v1/runtime/simulate")).toBeInTheDocument();
    expect(screen.getByText("/api/v2/runtime/simulations")).toBeInTheDocument();
  });

  it("flow-simulator tab is hidden from viewer and visible to admin", () => {
    render(<App />);

    // viewer (default) should not see Flow Simulator nav button
    expect(screen.queryByRole("button", { name: "Flow Simulator" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "admin" } });

    expect(screen.getByRole("button", { name: "Flow Simulator" })).toBeInTheDocument();
  });

  it("reads public status from the backend endpoint in the admin panel", async () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Admin" }));

    expect(await screen.findByText("Public status")).toBeInTheDocument();
    expect(screen.getByText("public-status.v1")).toBeInTheDocument();
    expect(screen.getByText("Overall status")).toBeInTheDocument();
    expect(screen.getAllByText("degraded")).toHaveLength(2);
    expect(screen.getByText("api")).toBeInTheDocument();
    expect(screen.getByText("workers")).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/v1/status-page",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});

describe("FlowSimulator", () => {
  it("shows invariant-blocked message and disables Start for an invalid candidate", () => {
    render(<FlowSimulator candidate={invalidGraphCandidate} reducedMotion={false} />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain(
      "Simulation blocked: protected workflow invariants are violated.",
    );
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Step" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resume" })).toBeDisabled();
  });

  it("auto-advances every 1s in slow mode with fake timers", () => {
    vi.useFakeTimers();

    render(<FlowSimulator candidate={activeGraphCandidate} reducedMotion={false} />);

    // Enable slow mode then start
    fireEvent.click(screen.getByLabelText("Slow mode (1s delay)"));
    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    // Step 1 (load_constitution) should be in the log immediately
    expect(screen.getByRole("log").textContent).toContain("Load Constitution");

    // Advance 1 second - should move to step 2 (Feature Spec)
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    const items = screen.getByRole("log").querySelectorAll("li");
    expect(items[0].textContent).toContain("Feature Spec");

    vi.useRealTimers();
  });

  it("does not auto-advance when reduced motion is true even with slow mode enabled", () => {
    vi.useFakeTimers();

    render(<FlowSimulator candidate={activeGraphCandidate} reducedMotion={true} />);

    // Enable slow mode - should show reduced motion notice
    fireEvent.click(screen.getByLabelText("Slow mode (1s delay)"));
    expect(
      screen.getByText(
        "Automatic pacing is disabled (reduced motion). Use Step to advance.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    // Advance 1 second - should NOT auto-advance
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    const items = screen.getByRole("log").querySelectorAll("li");
    expect(items).toHaveLength(1);

    vi.useRealTimers();
  });

  it("does not call fetch during simulator interactions", () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<FlowSimulator candidate={activeGraphCandidate} reducedMotion={false} />);
    const callsBefore = fetchMock.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    fireEvent.click(screen.getByRole("button", { name: "Step" }));
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    expect(fetchMock.mock.calls.length).toBe(callsBefore);

    vi.unstubAllGlobals();
  });
});
