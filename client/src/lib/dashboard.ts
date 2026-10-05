export interface DashboardDevice {
  id: number;
  name: string;
  online: boolean;
  state_code: number | null;
  pulling_stream: boolean;
  task?: string | null;
}

export interface DashboardEvent {
  id: string;
  type: string;
  person?: string | null;
  device_id: string;
  device: string;
  time_ms?: number | null;
  score?: number | null;
}

export interface DashboardSummary {
  date: string;
  generated_at: string;
  period: { start: string; end: string; previous_start: string; previous_end: string };
  health: {
    devices_total: number;
    devices_online: number;
    devices_offline: number;
    streams_pulling: number;
    tasks_total: number;
    clock: { time?: string; time_zone?: string; source: string };
  };
  activity: {
    matched: number;
    strangers: number;
    captures: number;
    face_captures: number;
    body_captures: number;
    capture_breakdown_limited: boolean;
    previous_matched: number;
    previous_strangers: number;
    previous_captures: number;
  };
  insights: {
    peak_hour: number | null;
    busiest_device_id: string | null;
    busiest_device: string | null;
    average_match_score: number | null;
    low_confidence_count: number;
    low_liveness_count: number;
    tracked_encounters: number;
    face_encounters: number;
    body_encounters: number;
    unique_recognized_people: number;
    recognized_encounters: number;
    stranger_encounters: number;
    recognized_capture_tracks: number;
    recognition_coverage_percent: number | null;
    busiest_capture_device: string | null;
    analysis_sampled: number;
    analysis_limited: boolean;
    top_people: { name: string; count: number }[];
    hourly_activity: { hour: number; count: number }[];
    events: DashboardEvent[];
  };
  devices: DashboardDevice[];
  attention: { severity: string; type: string; message: string; device_id?: number | null }[];
  meta?: {
    source: 'database' | 'box';
    fallback_reason?: string | null;
    coverage_start?: string | null;
    cache?: { health: string; activity: string };
    ingest_last_success_at?: string | null;
  };
}

export async function fetchDashboardSummary(
  date?: string,
  options: { fresh?: boolean } = {},
): Promise<DashboardSummary> {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (options.fresh) params.set('fresh', '1');
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`/api/dashboard/summary${query}`, { cache: 'no-store' });
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (!response.ok) {
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Could not load dashboard (${response.status})`);
  }
  return body as unknown as DashboardSummary;
}