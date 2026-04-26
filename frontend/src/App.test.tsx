import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
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
});
