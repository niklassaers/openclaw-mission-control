import { render, screen } from "@testing-library/react";

import { AgentWorkloadPanel, SchedulePanel } from "@/app/dashboard/page";

describe("AgentWorkloadPanel", () => {
  it("renders summary values and agent cards", () => {
    render(
      <AgentWorkloadPanel
        isLoading={false}
        error={null}
        summary={{
          total_agents: 1,
          online_agents: 1,
          assigned_tasks: 3,
          inbox_tasks: 1,
          in_progress_tasks: 1,
          review_tasks: 0,
          done_tasks: 1,
        }}
        agents={[
          {
            agent_id: "agent-1",
            board_id: "board-1",
            board_name: "Ops",
            name: "Alpha",
            status: "online",
            last_seen_at: new Date().toISOString(),
            task_counts: { inbox: 1, in_progress: 1, review: 0, done: 1 },
          },
        ]}
      />,
    );

    expect(screen.getByText("Agent Workload")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Ops")).toBeInTheDocument();
  });
});

describe("SchedulePanel", () => {
  it("renders upcoming events and warnings", () => {
    render(
      <SchedulePanel
        isLoading={false}
        error={null}
        events={[
          {
            id: "cron-1",
            name: "Daily",
            description: "",
            board_id: "board-1",
            board_name: "Ops",
            schedule: "0 0 * * *",
            next_run_at: "2026-03-05T00:00:00Z",
            last_run_at: "2026-03-04T00:00:00Z",
            enabled: true,
            gateway_id: null,
            gateway_name: null,
          },
        ]}
        warnings={[{ message: "Cron warning", gateway_id: null, board_id: null }]}
      />,
    );

    expect(screen.getByText("Schedule & Calendar")).toBeInTheDocument();
    expect(screen.getByText("Cron warning")).toBeInTheDocument();
    expect(screen.getByText("Daily")).toBeInTheDocument();
    expect(screen.getByText("Ops")).toBeInTheDocument();
  });
});
