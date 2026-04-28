import type { GraphCandidate } from "../data/sampleData";
import { validateGraphCandidate } from "./graphValidation";

export type SimulationStep = {
  index: number;
  nodeId: string;
  label: string;
  isProtected: boolean;
  writesRepo: boolean;
  transitionReason: string;
  narration: string;
};

export type SimulationPlan = {
  steps: SimulationStep[];
  protectedInvariantErrors: string[];
};

const narrationByNodeId: Record<string, string> = {
  load_constitution:
    "Loading the product constitution to establish team context and non-negotiable constraints.",
  create_feature_spec:
    "Generating the feature specification from the Jira ticket description and repo context.",
  clarify: "Iterating on open questions with the spec until all ambiguity is resolved.",
  create_plan: "Building the implementation plan from the approved feature spec.",
  create_task_list: "Breaking the plan into ordered, testable implementation tasks.",
  readiness_gate: "Verifying spec readiness before allowing any repo-writing step.",
  coder: "Implementing the task list against the target branch. Writes are now active.",
  tester: "Running the test suite against the implementation. Failing tests block the PR path.",
  reviewer:
    "Performing code review: checking for regressions, policy violations, and diff quality.",
  pre_pr_sync:
    "Syncing the branch with the target, detecting merge conflicts, and verifying diff size.",
  pr_creator:
    "Opening the pull request on GitHub with signed commits and branch protections verified.",
};

export function simulateAgentNarration(nodeId: string): string {
  return narrationByNodeId[nodeId] ?? `Executing node: ${nodeId}.`;
}

export function buildSimulationPlan(candidate: GraphCandidate): SimulationPlan {
  const validation = validateGraphCandidate(JSON.stringify(candidate));
  if (!validation.valid) {
    return { steps: [], protectedInvariantErrors: validation.errors };
  }

  const successEdges = new Map<string, string>();
  for (const edge of candidate.edges) {
    if (edge.transition === "success") {
      successEdges.set(edge.from, edge.to);
    }
  }

  const nodeMap = new Map(candidate.nodes.map((n) => [n.id, n]));
  const steps: SimulationStep[] = [];
  let current = successEdges.get("START");

  while (current !== undefined && nodeMap.has(current)) {
    const node = nodeMap.get(current)!;
    steps.push({
      index: steps.length,
      nodeId: node.id,
      label: node.label,
      isProtected: node.protected,
      writesRepo: node.writesRepo ?? false,
      transitionReason: "success",
      narration: simulateAgentNarration(node.id),
    });
    current = successEdges.get(current);
  }

  const nodeOrder = steps.map((s) => s.nodeId);
  const protectedInvariantErrors: string[] = [];

  const coderIdx = nodeOrder.indexOf("coder");
  const readinessIdx = nodeOrder.indexOf("readiness_gate");
  if (coderIdx !== -1 && readinessIdx !== -1 && coderIdx < readinessIdx) {
    protectedInvariantErrors.push(
      'Traversal order violation: "coder" appears before "readiness_gate".',
    );
  }

  const prIdx = nodeOrder.indexOf("pr_creator");
  if (prIdx !== -1) {
    for (const required of ["tester", "reviewer", "pre_pr_sync"]) {
      const reqIdx = nodeOrder.indexOf(required);
      if (reqIdx === -1 || reqIdx > prIdx) {
        protectedInvariantErrors.push(
          `Traversal order violation: "pr_creator" reached without traversing "${required}".`,
        );
      }
    }
  }

  if (protectedInvariantErrors.length > 0) {
    return { steps: [], protectedInvariantErrors };
  }

  return { steps, protectedInvariantErrors: [] };
}
