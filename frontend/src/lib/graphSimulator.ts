import type { GraphCandidate } from "../data/sampleData";
import { validateGraphCandidate } from "./graphValidation";

export type SimulationAgentRole = "planner" | "coder" | "tester" | "reviewer" | "pr_creator";

export type SimulationAgentVisual = {
  role: SimulationAgentRole;
  title: string;
  spritePath: string;
  facing: "front" | "back" | "left" | "right";
};

export type SimulationOfficePhase =
  | "concept"
  | "planning"
  | "plan-review"
  | "coding"
  | "testing"
  | "code-review"
  | "pre-pr"
  | "pr-creation"
  | "complete";

export type SimulationOfficeState = {
  phase: SimulationOfficePhase;
  label: string;
  interaction: string;
  activeAgents: SimulationAgentRole[];
  carrier?: SimulationAgentRole;
  speech: Partial<Record<SimulationAgentRole, string>>;
};

export type SimulationStep = {
  index: number;
  nodeId: string;
  label: string;
  isProtected: boolean;
  writesRepo: boolean;
  transitionReason: string;
  narration: string;
  visualAgent: SimulationAgentVisual;
  office: SimulationOfficeState;
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

const visualAgentByRole: Record<SimulationAgentRole, Omit<SimulationAgentVisual, "role">> = {
  planner: {
    title: "Planner",
    spritePath: "/assets/sprites/agent_a.png",
    facing: "back",
  },
  reviewer: {
    title: "Reviewer",
    spritePath: "/assets/sprites/agent_b.png",
    facing: "left",
  },
  coder: {
    title: "Coder",
    spritePath: "/assets/sprites/agent_c.png",
    facing: "back",
  },
  tester: {
    title: "Tester",
    spritePath: "/assets/sprites/agent_d.png",
    facing: "right",
  },
  pr_creator: {
    title: "PR Creator",
    spritePath: "/assets/sprites/agent_s.png",
    facing: "front",
  },
};

const nodeAgentRole: Record<string, SimulationAgentRole> = {
  load_constitution: "planner",
  create_feature_spec: "planner",
  clarify: "planner",
  create_plan: "planner",
  create_task_list: "planner",
  readiness_gate: "planner",
  coder: "coder",
  tester: "tester",
  reviewer: "reviewer",
  pre_pr_sync: "pr_creator",
  pr_creator: "pr_creator",
};

const officeByNodeId: Record<string, SimulationOfficeState> = {
  load_constitution: {
    phase: "concept",
    label: "Reading the rules",
    interaction: "Planner starts at the constitution desk and establishes the non-negotiables.",
    activeAgents: ["planner"],
    speech: {
      planner: "Loading the constitution.",
      pr_creator: "Standing by.",
    },
  },
  create_feature_spec: {
    phase: "planning",
    label: "Drafting the feature spec",
    interaction: "Planner writes the runtime spec while the rest of the office stays available.",
    activeAgents: ["planner"],
    carrier: "planner",
    speech: {
      planner: "Turning the ticket into a spec.",
    },
  },
  clarify: {
    phase: "plan-review",
    label: "Clarifying the plan",
    interaction: "Planner walks the spec to Reviewer so gaps can be challenged before code starts.",
    activeAgents: ["planner", "reviewer"],
    carrier: "planner",
    speech: {
      planner: "Answering the open questions.",
      reviewer: "Checking assumptions.",
    },
  },
  create_plan: {
    phase: "planning",
    label: "Planning implementation",
    interaction: "Planner returns to the desk and turns the accepted spec into an implementation plan.",
    activeAgents: ["planner"],
    carrier: "planner",
    speech: {
      planner: "Building the implementation plan.",
    },
  },
  create_task_list: {
    phase: "planning",
    label: "Breaking down tasks",
    interaction: "Planner decomposes the plan into ordered, testable tasks.",
    activeAgents: ["planner"],
    speech: {
      planner: "Writing the task list.",
    },
  },
  readiness_gate: {
    phase: "plan-review",
    label: "Readiness gate",
    interaction: "Planner and Reviewer confirm the repo-write gate before Coder can touch files.",
    activeAgents: ["planner", "reviewer"],
    speech: {
      planner: "Checking readiness.",
      reviewer: "No write before spec and tasks.",
    },
  },
  coder: {
    phase: "coding",
    label: "Implementation",
    interaction: "Coder works at the implementation desk after the protected gate opens.",
    activeAgents: ["coder"],
    speech: {
      coder: "Implementing the task list.",
    },
  },
  tester: {
    phase: "testing",
    label: "Testing with fixes",
    interaction: "Tester pulls Coder into the test lane so failures can be fixed in context.",
    activeAgents: ["coder", "tester"],
    carrier: "coder",
    speech: {
      coder: "Ready to patch failures.",
      tester: "Running the suite.",
    },
  },
  reviewer: {
    phase: "code-review",
    label: "Code review",
    interaction: "Coder brings the diff to Reviewer for regression and policy checks.",
    activeAgents: ["coder", "reviewer"],
    carrier: "coder",
    speech: {
      coder: "Walking through the diff.",
      reviewer: "Reviewing for regressions.",
    },
  },
  pre_pr_sync: {
    phase: "pre-pr",
    label: "Pre-PR sync",
    interaction: "Tester hands verified results to PR Creator for merge-conflict and diff-size checks.",
    activeAgents: ["tester", "pr_creator"],
    carrier: "tester",
    speech: {
      tester: "Tests are ready.",
      pr_creator: "Checking branch state.",
    },
  },
  pr_creator: {
    phase: "pr-creation",
    label: "Pull request creation",
    interaction: "PR Creator opens the signed pull request after the mandatory chain is complete.",
    activeAgents: ["planner", "pr_creator"],
    carrier: "pr_creator",
    speech: {
      planner: "Final handoff approved.",
      pr_creator: "Opening the PR.",
    },
  },
};

export function simulateAgentNarration(nodeId: string): string {
  return narrationByNodeId[nodeId] ?? `Executing node: ${nodeId}.`;
}

export function getSimulationAgentVisual(nodeId: string): SimulationAgentVisual {
  const role = nodeAgentRole[nodeId] ?? "planner";
  return { role, ...visualAgentByRole[role] };
}

export function getSimulationOfficeState(
  nodeId: string,
  narration: string = simulateAgentNarration(nodeId),
): SimulationOfficeState {
  const configured = officeByNodeId[nodeId];
  if (!configured) {
    return {
      phase: "concept",
      label: "Custom graph step",
      interaction: `Executing custom node ${nodeId}.`,
      activeAgents: ["planner"],
      speech: { planner: narration },
    };
  }

  const primaryRole = nodeAgentRole[nodeId] ?? "planner";
  return {
    ...configured,
    speech: {
      ...configured.speech,
      [primaryRole]: narration,
    },
  };
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
    const narration = simulateAgentNarration(node.id);
    steps.push({
      index: steps.length,
      nodeId: node.id,
      label: node.label,
      isProtected: node.protected,
      writesRepo: node.writesRepo ?? false,
      transitionReason: "success",
      narration,
      visualAgent: getSimulationAgentVisual(node.id),
      office: getSimulationOfficeState(node.id, narration),
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
