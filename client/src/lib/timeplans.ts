export type PlanKind = 'regular' | 'festival';

export interface TimePlan {
  id: string;
  name: string;
  type: 1 | 2;
  weekSchedule: Record<string, string[]>;
  isDefault: boolean;
  local?: boolean;
}

export interface TimeContext {
  system_time: {
    time_zone?: string;
    time_mode?: string;
    time_dst?: { dst_enable?: number; offset?: number };
  };
  current_time: { time?: string };
  clock_source?: 'box' | 'backend_fallback';
}

const emptyWeek = () => Object.fromEntries(
  Array.from({ length: 7 }, (_, index) => [String(index + 1), []]),
) as Record<string, string[]>;

function normalizePlan(value: Record<string, unknown>, type: 1 | 2): TimePlan {
  const rawWeek = value.week_schedule;
  const weekSchedule = emptyWeek();
  if (rawWeek && typeof rawWeek === 'object') {
    for (const [day, intervals] of Object.entries(rawWeek as Record<string, unknown>)) {
      if (Array.isArray(intervals)) weekSchedule[day] = intervals.map(String);
    }
  }
  const ext = value.ext as Record<string, unknown> | undefined;
  return {
    id: String(value.schedule_plan_id ?? `${type}-${value.schedule_plan_name ?? 'plan'}`),
    name: String(value.schedule_plan_name ?? 'Untitled plan'),
    type,
    weekSchedule,
    isDefault: Number(ext?.default) === 1,
  };
}

async function getJson(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(path, { cache: 'no-store' });
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
  }
  return body ?? {};
}

export async function fetchTimeContext(): Promise<TimeContext> {
  return (await getJson('/api/timeplans/time')) as unknown as TimeContext;
}

export async function fetchTimePlans(kind: PlanKind): Promise<TimePlan[]> {
  const type = kind === 'regular' ? 1 : 2;
  const body = await getJson(`/api/timeplans/${kind}`);
  const plans = Array.isArray(body.schedule_plans) ? body.schedule_plans : [];
  return plans.map((plan) => normalizePlan(plan as Record<string, unknown>, type));
}

export async function updateTimePlan(plan: TimePlan): Promise<void> {
  const response = await fetch(`/api/timeplans/${encodeURIComponent(plan.id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schedule_plan_id: plan.id,
      schedule_plan_name: plan.name.trim(),
      schedule_plan_type: plan.type,
      week_schedule: plan.weekSchedule,
      bind_schedule_plan: [],
    }),
  });
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Could not save the time plan (${response.status})`);
  }
}

export async function createTimePlan(plan: TimePlan): Promise<void> {
  const response = await fetch('/api/timeplans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schedule_plan_name: plan.name.trim(),
      schedule_plan_type: plan.type,
      week_schedule: plan.weekSchedule,
      bind_schedule_plan: [],
    }),
  });
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Could not create the time plan (${response.status})`);
  }
}

export async function deleteTimePlan(plan: TimePlan): Promise<void> {
  const response = await fetch(`/api/timeplans/${encodeURIComponent(plan.id)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schedule_plan_id: plan.id,
      schedule_plan_type: plan.type,
    }),
  });
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Could not delete the time plan (${response.status})`);
  }
}

export function blankTimePlan(kind: PlanKind, index: number): TimePlan {
  return {
    id: `local-${kind}-${Date.now()}-${index}`,
    name: `New ${kind === 'regular' ? 'regular' : 'festival'} plan`,
    type: kind === 'regular' ? 1 : 2,
    weekSchedule: emptyWeek(),
    isDefault: false,
    local: true,
  };
}