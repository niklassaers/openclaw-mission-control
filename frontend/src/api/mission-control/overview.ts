import { type UseQueryOptions, useQuery } from "@tanstack/react-query";

import { ApiError, customFetch } from "@/api/mutator";

export type OverviewParams = {
  board_id?: string | null;
  group_id?: string | null;
};

export type AgentWorkloadTaskCounts = {
  inbox: number;
  in_progress: number;
  review: number;
  done: number;
};

export type AgentWorkloadAgent = {
  agent_id: string;
  board_id: string | null;
  board_name: string | null;
  name: string;
  status: string;
  last_seen_at: string | null;
  task_counts: AgentWorkloadTaskCounts;
};

export type AgentWorkloadSummary = {
  total_agents: number;
  online_agents: number;
  assigned_tasks: number;
  inbox_tasks: number;
  in_progress_tasks: number;
  review_tasks: number;
  done_tasks: number;
};

export type AgentWorkloadPayload = {
  generated_at: string;
  summary: AgentWorkloadSummary;
  agents: AgentWorkloadAgent[];
};

export type AgentWorkloadResponse = {
  data: AgentWorkloadPayload;
  status: number;
  headers: Headers;
};

export type CalendarWarning = {
  message: string;
  gateway_id: string | null;
  board_id: string | null;
};

export type CalendarEvent = {
  id: string;
  name: string | null;
  description: string | null;
  board_id: string | null;
  board_name: string | null;
  schedule: string | null;
  next_run_at: string | null;
  last_run_at: string | null;
  enabled: boolean | null;
  gateway_id: string | null;
  gateway_name: string | null;
};

export type CalendarOverviewPayload = {
  generated_at: string;
  events: CalendarEvent[];
  warnings: CalendarWarning[];
};

export type CalendarOverviewResponse = {
  data: CalendarOverviewPayload;
  status: number;
  headers: Headers;
};

const buildQueryUrl = (path: string, params?: OverviewParams): string => {
  if (!params) return path;
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return;
    query.append(key, value === null ? "null" : value);
  });
  const stringified = query.toString();
  return stringified ? `${path}?${stringified}` : path;
};

const getAgentWorkloadUrl = (params?: OverviewParams) =>
  buildQueryUrl("/api/v1/metrics/dashboard/agent-workload", params);

const getCalendarOverviewUrl = (params?: OverviewParams) =>
  buildQueryUrl("/api/v1/metrics/dashboard/calendar", params);

export const getAgentWorkload = async (
  params?: OverviewParams,
  options?: RequestInit,
): Promise<AgentWorkloadResponse> => {
  return customFetch<AgentWorkloadResponse>(getAgentWorkloadUrl(params), {
    method: "GET",
    ...options,
  });
};

export const getCalendarOverview = async (
  params?: OverviewParams,
  options?: RequestInit,
): Promise<CalendarOverviewResponse> => {
  return customFetch<CalendarOverviewResponse>(getCalendarOverviewUrl(params), {
    method: "GET",
    ...options,
  });
};

type DashboardQueryOptions<TData> = Partial<
  UseQueryOptions<TData, ApiError, TData>
>;

export const useAgentWorkload = (
  params?: OverviewParams,
  options?: DashboardQueryOptions<AgentWorkloadResponse>,
) => {
  return useQuery({
    queryKey: ["dashboard", "agent-workload", params],
    queryFn: ({ signal }) => getAgentWorkload(params, { signal }),
    refetchInterval: 30_000,
    refetchOnMount: "always",
    ...options,
  });
};

export const useCalendarOverview = (
  params?: OverviewParams,
  options?: DashboardQueryOptions<CalendarOverviewResponse>,
) => {
  return useQuery({
    queryKey: ["dashboard", "calendar", params],
    queryFn: ({ signal }) => getCalendarOverview(params, { signal }),
    refetchInterval: 30_000,
    refetchOnMount: "always",
    ...options,
  });
};
