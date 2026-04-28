import { type CSSProperties, useEffect, useMemo, useState } from "react";

import type { SimulationAgentRole, SimulationStep } from "../lib/graphSimulator";

type Props = {
  currentStep: SimulationStep;
  reducedMotion: boolean;
  running: boolean;
};

type Facing = "front" | "back" | "left" | "right";

type AgentPosition = {
  x: number;
  y: number;
  facing: Facing;
};

type AgentConfig = {
  role: SimulationAgentRole;
  title: string;
  name: string;
  spritePath: string;
  home: AgentPosition;
};

const SPRITE_FRAME_MS = 150;
const SPRITE_FRAME_SIZE = 64;

const rowByFacing: Record<Facing, number> = {
  front: 0,
  back: 1,
  right: 2,
  left: 3,
};

const agents: AgentConfig[] = [
  {
    role: "planner",
    title: "Planner",
    name: "Alexis",
    spritePath: "/assets/sprites/agent_a.png",
    home: { x: 150, y: 314, facing: "back" },
  },
  {
    role: "reviewer",
    title: "Reviewer",
    name: "Brad",
    spritePath: "/assets/sprites/agent_b.png",
    home: { x: 335, y: 314, facing: "back" },
  },
  {
    role: "coder",
    title: "Coder",
    name: "Carlos",
    spritePath: "/assets/sprites/agent_c.png",
    home: { x: 520, y: 314, facing: "back" },
  },
  {
    role: "tester",
    title: "Tester",
    name: "Dana",
    spritePath: "/assets/sprites/agent_d.png",
    home: { x: 705, y: 314, facing: "back" },
  },
  {
    role: "pr_creator",
    title: "PR Creator",
    name: "Sal",
    spritePath: "/assets/sprites/agent_s.png",
    home: { x: 890, y: 314, facing: "back" },
  },
];

const officePositionsByPhase: Partial<
  Record<SimulationStep["office"]["phase"], Partial<Record<SimulationAgentRole, AgentPosition>>>
> = {
  "plan-review": {
    planner: { x: 300, y: 316, facing: "right" },
    reviewer: { x: 335, y: 316, facing: "left" },
  },
  testing: {
    coder: { x: 665, y: 316, facing: "right" },
    tester: { x: 705, y: 316, facing: "left" },
  },
  "code-review": {
    coder: { x: 384, y: 316, facing: "left" },
    reviewer: { x: 342, y: 316, facing: "right" },
  },
  "pre-pr": {
    tester: { x: 850, y: 316, facing: "right" },
    pr_creator: { x: 890, y: 316, facing: "left" },
  },
  "pr-creation": {
    planner: { x: 845, y: 316, facing: "right" },
    pr_creator: { x: 890, y: 316, facing: "left" },
  },
  complete: {
    planner: { x: 395, y: 370, facing: "right" },
    reviewer: { x: 455, y: 370, facing: "right" },
    coder: { x: 515, y: 370, facing: "front" },
    tester: { x: 575, y: 370, facing: "left" },
    pr_creator: { x: 635, y: 370, facing: "left" },
  },
};

function getAgentPosition(agent: AgentConfig, step: SimulationStep): AgentPosition {
  return officePositionsByPhase[step.office.phase]?.[agent.role] ?? agent.home;
}

function buildSpriteStyle(agent: AgentConfig, position: AgentPosition, frame: number): CSSProperties {
  const row = rowByFacing[position.facing];
  return {
    backgroundImage: `url(${agent.spritePath})`,
    backgroundPosition: `-${frame * SPRITE_FRAME_SIZE}px -${row * SPRITE_FRAME_SIZE}px`,
  };
}

export default function DynamicPixelOffice({ currentStep, reducedMotion, running }: Props) {
  const [frame, setFrame] = useState(0);

  const activeAgents = useMemo(
    () => new Set(currentStep.office.activeAgents),
    [currentStep.office.activeAgents],
  );

  useEffect(() => {
    if (reducedMotion || !running) {
      setFrame(0);
      return;
    }

    const interval = window.setInterval(() => {
      setFrame((current) => (current + 1) % 8);
    }, SPRITE_FRAME_MS);

    return () => window.clearInterval(interval);
  }, [reducedMotion, running]);

  return (
    <section
      className={reducedMotion ? "pixel-office reduced-office-motion" : "pixel-office"}
      aria-label={`Dynamic office: ${currentStep.office.label}`}
    >
      <div className="pixel-office-copy">
        <p className="eyebrow">{currentStep.office.phase}</p>
        <h3>{currentStep.office.label}</h3>
        <p>{currentStep.office.interaction}</p>
      </div>

      <div className="pixel-office-scene" role="list" aria-label="Agent office positions">
        <div className="office-window" aria-hidden="true">
          <span className="office-star star-one" />
          <span className="office-star star-two" />
          <span className="office-star star-three" />
          <span className="office-earth" />
        </div>
        <div className="office-floor" aria-hidden="true" />
        <img
          className="office-prop office-watercooler"
          src="/assets/sprites/watercooler.png"
          alt=""
          aria-hidden="true"
        />
        <img className="office-prop office-couch" src="/assets/sprites/couch.png" alt="" aria-hidden="true" />
        <img className="office-prop office-tv" src="/assets/sprites/tv.png" alt="" aria-hidden="true" />
        <img
          className="office-prop office-pingpong"
          src="/assets/sprites/pingpong.png"
          alt=""
          aria-hidden="true"
        />

        {agents.map((agent, index) => {
          const position = getAgentPosition(agent, currentStep);
          const isActive = activeAgents.has(agent.role);
          const isAwayFromHome = position.x !== agent.home.x || position.y !== agent.home.y;
          const spriteFrame = isActive && (running || isAwayFromHome) && !reducedMotion ? frame : 0;
          const speech = currentStep.office.speech[agent.role];
          const style = {
            "--agent-x": `${position.x / 10}%`,
            "--agent-y": `${position.y / 4.6}%`,
            "--agent-z": String(20 + index),
          } as CSSProperties;

          return (
            <div
              key={agent.role}
              className={`office-agent${isActive ? " office-agent-active" : ""}${
                isAwayFromHome ? " office-agent-away" : ""
              }`}
              role="listitem"
              aria-label={`${agent.title} ${isActive ? "active" : "idle"}`}
              style={style}
            >
              {speech ? <div className="office-speech">{speech}</div> : null}
              <div className="office-agent-shadow" aria-hidden="true" />
              <div
                className="office-agent-sprite"
                style={buildSpriteStyle(agent, position, spriteFrame)}
                aria-hidden="true"
              />
              {currentStep.office.carrier === agent.role ? (
                <div className="office-document" aria-hidden="true" />
              ) : null}
              <div className="office-agent-label">
                <strong>{agent.title}</strong>
                <span>{agent.name}</span>
              </div>
            </div>
          );
        })}

        <div className="office-phase-card" aria-hidden="true">
          <span>{currentStep.nodeId}</span>
          <strong>{currentStep.label}</strong>
        </div>
      </div>
    </section>
  );
}
