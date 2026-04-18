export type OperatorRole = "viewer" | "operator" | "admin" | "super-admin";
export type RunStatus = "planning" | "active" | "paused" | "review" | "dlq" | "completed";

export type RunCard = {
  id: string;
  ticket: string;
  lane: string;
  agent: "planner" | "coder" | "tester" | "reviewer" | "pr_creator";
  status: RunStatus;
  retryCount: number;
  costUsd: number;
};

export type GraphCandidate = {
  profileId: string;
  nodes: Array<{
    id: string;
    label: string;
    protected: boolean;
    writesRepo?: boolean;
  }>;
  edges: Array<{ from: string; to: string; transition: string }>;
};

export type AgentCard = {
  role: string;
  model: string;
  tools: string[];
  retryBudget: string;
  testPrompt: string;
};

export const roles: OperatorRole[] = ["viewer", "operator", "admin", "super-admin"];

export const initialRuns: RunCard[] = [
  {
    id: "run-101",
    ticket: "ENG-101",
    lane: "Tenant Alpha",
    agent: "planner",
    status: "planning",
    retryCount: 0,
    costUsd: 1.2,
  },
  {
    id: "run-102",
    ticket: "ENG-102",
    lane: "Tenant Alpha",
    agent: "coder",
    status: "active",
    retryCount: 1,
    costUsd: 4.8,
  },
  {
    id: "run-103",
    ticket: "ENG-103",
    lane: "Tenant Beta",
    agent: "reviewer",
    status: "paused",
    retryCount: 0,
    costUsd: 2.6,
  },
  {
    id: "run-104",
    ticket: "ENG-104",
    lane: "Tenant Alpha",
    agent: "tester",
    status: "dlq",
    retryCount: 2,
    costUsd: 3.4,
  },
];

export const activeGraphCandidate: GraphCandidate = {
  profileId: "ticket_to_pr_v1",
  nodes: [
    { id: "load_constitution", label: "Load Constitution", protected: true },
    { id: "create_feature_spec", label: "Feature Spec", protected: true },
    { id: "clarify", label: "Clarify", protected: true },
    { id: "create_plan", label: "Plan", protected: true },
    { id: "create_task_list", label: "Task List", protected: true },
    { id: "readiness_gate", label: "Readiness Gate", protected: true },
    { id: "coder", label: "Coder", protected: true, writesRepo: true },
    { id: "tester", label: "Tester", protected: true },
    { id: "reviewer", label: "Reviewer", protected: true },
    { id: "pre_pr_sync", label: "Pre-PR Sync", protected: true },
    { id: "pr_creator", label: "PR Creator", protected: true },
  ],
  edges: [
    { from: "START", to: "load_constitution", transition: "success" },
    { from: "load_constitution", to: "create_feature_spec", transition: "success" },
    { from: "create_feature_spec", to: "clarify", transition: "success" },
    { from: "clarify", to: "create_plan", transition: "success" },
    { from: "create_plan", to: "create_task_list", transition: "success" },
    { from: "create_task_list", to: "readiness_gate", transition: "success" },
    { from: "readiness_gate", to: "coder", transition: "success" },
    { from: "coder", to: "tester", transition: "success" },
    { from: "tester", to: "reviewer", transition: "success" },
    { from: "reviewer", to: "pre_pr_sync", transition: "success" },
    { from: "pre_pr_sync", to: "pr_creator", transition: "success" },
  ],
};

export const invalidGraphCandidate: GraphCandidate = {
  ...activeGraphCandidate,
  nodes: activeGraphCandidate.nodes.filter(
    (node) => node.id !== "reviewer" && node.id !== "pre_pr_sync",
  ),
  edges: activeGraphCandidate.edges.filter(
    (edge) =>
      !["reviewer", "pre_pr_sync"].includes(edge.from) &&
      !["reviewer", "pre_pr_sync"].includes(edge.to),
  ),
};

export const agentCards: AgentCard[] = [
  {
    role: "planner",
    model: "gpt-4.1",
    tools: ["jira_read", "repo_read", "checkpoint_read"],
    retryBudget: "clarification: 2",
    testPrompt: "Summarize the feature scope and list missing context.",
  },
  {
    role: "coder",
    model: "gpt-4.1",
    tools: ["repo_write", "local_test", "build_tool"],
    retryBudget: "implementation: 2",
    testPrompt: "Explain the intended patch strategy without touching protected paths.",
  },
  {
    role: "reviewer",
    model: "gpt-4.1",
    tools: ["repo_read", "diff_analysis", "policy_check"],
    retryBudget: "review: 1",
    testPrompt: "Inspect the candidate diff for regressions and policy violations.",
  },
];

export const spriteManifest = [
  {
    spriteId: "planner-idle",
    sourceKind: "bundled",
    runtimeRole: "planner",
    runtimeState: "planning",
    path: "/assets/sprites/planner-idle.svg",
  },
  {
    spriteId: "coder-active",
    sourceKind: "bundled",
    runtimeRole: "coder",
    runtimeState: "active",
    path: "/assets/sprites/coder-active.svg",
  },
  {
    spriteId: "reviewer-paused",
    sourceKind: "bundled",
    runtimeRole: "reviewer",
    runtimeState: "paused",
    path: "/assets/sprites/reviewer-paused.svg",
  },
];
