import type { GraphCandidate } from "../data/sampleData";

const requiredProtectedNodes = [
  "readiness_gate",
  "coder",
  "tester",
  "reviewer",
  "pre_pr_sync",
  "pr_creator",
];

export type GraphValidation = {
  valid: boolean;
  errors: string[];
};

export function parseGraphCandidate(source: string): GraphCandidate | null {
  try {
    return JSON.parse(source) as GraphCandidate;
  } catch {
    return null;
  }
}

export function validateGraphCandidate(source: string): GraphValidation {
  const parsed = parseGraphCandidate(source);
  if (parsed === null) {
    return {
      valid: false,
      errors: ["Candidate graph JSON is invalid."],
    };
  }

  const nodeIds = new Set(parsed.nodes.map((node) => node.id));
  const errors: string[] = [];

  requiredProtectedNodes.forEach((nodeId) => {
    if (!nodeIds.has(nodeId)) {
      errors.push(`Protected path is missing required node "${nodeId}".`);
    }
  });

  const coderIndex = parsed.nodes.findIndex((node) => node.id === "coder");
  const readinessIndex = parsed.nodes.findIndex((node) => node.id === "readiness_gate");
  if (coderIndex !== -1 && readinessIndex !== -1 && coderIndex < readinessIndex) {
    errors.push('Repo-writing node "coder" appears before "readiness_gate".');
  }

  const hasSuccessPath = parsed.edges.some(
    (edge) => edge.from === "pre_pr_sync" && edge.to === "pr_creator",
  );
  if (!hasSuccessPath) {
    errors.push('Success path does not reach "pr_creator" through "pre_pr_sync".');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
