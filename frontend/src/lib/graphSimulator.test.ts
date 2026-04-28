import { describe, expect, it } from "vitest";

import { activeGraphCandidate, invalidGraphCandidate } from "../data/sampleData";
import { buildSimulationPlan, simulateAgentNarration } from "./graphSimulator";
import type { GraphCandidate } from "../data/sampleData";

const emptyCandidate: GraphCandidate = {
  profileId: "empty",
  nodes: [],
  edges: [],
};

describe("buildSimulationPlan", () => {
  it("produces a valid plan from the active graph candidate", () => {
    const plan = buildSimulationPlan(activeGraphCandidate);
    expect(plan.protectedInvariantErrors).toHaveLength(0);
    expect(plan.steps).toHaveLength(11);
    expect(plan.steps[0].nodeId).toBe("load_constitution");
    expect(plan.steps[plan.steps.length - 1].nodeId).toBe("pr_creator");
  });

  it("orders readiness_gate before coder in the plan", () => {
    const plan = buildSimulationPlan(activeGraphCandidate);
    const readinessIdx = plan.steps.findIndex((s) => s.nodeId === "readiness_gate");
    const coderIdx = plan.steps.findIndex((s) => s.nodeId === "coder");
    expect(readinessIdx).toBeGreaterThanOrEqual(0);
    expect(coderIdx).toBeGreaterThan(readinessIdx);
  });

  it("orders tester, reviewer, and pre_pr_sync before pr_creator", () => {
    const plan = buildSimulationPlan(activeGraphCandidate);
    const prIdx = plan.steps.findIndex((s) => s.nodeId === "pr_creator");
    expect(prIdx).toBeGreaterThan(0);
    for (const required of ["tester", "reviewer", "pre_pr_sync"]) {
      const reqIdx = plan.steps.findIndex((s) => s.nodeId === required);
      expect(reqIdx).toBeGreaterThanOrEqual(0);
      expect(reqIdx).toBeLessThan(prIdx);
    }
  });

  it("returns errors and empty steps for the invalid graph candidate", () => {
    const plan = buildSimulationPlan(invalidGraphCandidate);
    expect(plan.steps).toHaveLength(0);
    expect(plan.protectedInvariantErrors.length).toBeGreaterThan(0);
  });

  it("short-circuits on structural failure with empty candidate", () => {
    const plan = buildSimulationPlan(emptyCandidate);
    expect(plan.steps).toHaveLength(0);
    expect(plan.protectedInvariantErrors.length).toBeGreaterThan(0);
  });

  it("returns errors for a candidate that violates traversal order", () => {
    const swapped: GraphCandidate = {
      ...activeGraphCandidate,
      nodes: activeGraphCandidate.nodes.map((n) => {
        if (n.id === "coder") return { ...n, id: "readiness_gate", label: "Readiness Gate" };
        if (n.id === "readiness_gate") return { ...n, id: "coder", label: "Coder", writesRepo: true };
        return n;
      }),
      edges: activeGraphCandidate.edges.map((e) => {
        const flip = (v: string) =>
          v === "coder" ? "readiness_gate" : v === "readiness_gate" ? "coder" : v;
        return { ...e, from: flip(e.from), to: flip(e.to) };
      }),
    };
    const plan = buildSimulationPlan(swapped);
    expect(plan.steps).toHaveLength(0);
    expect(
      plan.protectedInvariantErrors.some((e) => e.includes("coder") && e.includes("readiness_gate")),
    ).toBe(true);
  });
});

describe("simulateAgentNarration", () => {
  const knownNodeIds = [
    "load_constitution",
    "create_feature_spec",
    "clarify",
    "create_plan",
    "create_task_list",
    "readiness_gate",
    "coder",
    "tester",
    "reviewer",
    "pre_pr_sync",
    "pr_creator",
  ];

  it("returns a non-empty stable string for each known node ID", () => {
    for (const nodeId of knownNodeIds) {
      const first = simulateAgentNarration(nodeId);
      const second = simulateAgentNarration(nodeId);
      expect(first).toBe(second);
      expect(first.length).toBeGreaterThan(0);
    }
  });

  it("returns a fallback that includes the node ID for unknown nodes", () => {
    const narration = simulateAgentNarration("unknown_node_xyz");
    expect(narration).toContain("unknown_node_xyz");
  });
});
