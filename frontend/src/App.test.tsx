import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

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
