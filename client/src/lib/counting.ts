// People counting: walk-pasts and different people per camera, from the backend's /api/counting/* routes.
// Built from records stored in the portal's own database, not read live from the box.

export type CountBasis = 'merged' | 'face' | 'body';
export type Granularity = '15m' | 'hour' | 'day';
export type Preset = 'today' | 'yesterday' | 'last7' | 'last30' | 'custom';

export const BASIS_LABELS: Record<CountBasis, string> = {
  merged: 'Everyone (face + body merged)',
  face: 'Only people whose face was seen',
  body: 'Only people whose body was seen',
};
export const PRESET_LABELS: Record<Preset, string> = {
  today: 'Today',
  yesterday: 'Yesterday',
  last7: 'Last 7 days',
  last30: 'Last 30 days',
  custom: 'Custom',
};
/** Longest range (days) each chart granularity may cover; the backend refuses more. */
export const GRANULARITY_MAX_DAYS: Record<Granularity, number> = { '15m': 7, hour: 62, day: 366 };

export interface CountingFilters {
  cameraIds: number[];          // empty = every camera included in counting
  preset: Preset;
  fromDate: string;             // custom: YYYY-MM-DD
  fromTime: string;             // custom: HH:MM, optional
  toDate: string;
  toTime: string;
  hourFrom: number | null;      // inclusive; hourTo < hourFrom runs past midnight
  hourTo: number | null;
  days: number[];               // ISO weekdays, 1 = Monday; empty = every day
}

export const DEFAULT_FILTERS: CountingFilters = {
  cameraIds: [], preset: 'today', fromDate: '', fromTime: '', toDate: '', toTime: '',
  hourFrom: null, hourTo: null, days: [],
};

/** Different people told apart by face and clothing: a range, since the comparison isn't perfect. */
export interface FaceEstimate {
  people: number | null;        // null: too many walk-pasts in the period to group
  low: number | null;
  high: number | null;
  fingerprinted: number;        // walk-pasts with a usable face or body picture (the estimate covers only these)
  unusable: number;             // nothing usable to compare: not in the estimate
  pending: number;              // face pictures not processed yet
  tooMany: boolean;
}

export interface CountingTotals {
  walkPasts: number;
  visits: number;
  uniquePeople: number;
  knownPeople: number;
  strangerWalkPasts: number;
  notComparedWalkPasts: number;
  paired: number;
  faceOnly: number;
  bodyOnly: number;
  faceEstimate: FaceEstimate | null;
}

export interface CameraTotals extends CountingTotals { cameraId: number; name: string; countBasis: CountBasis }

export interface CountingSummary {
  totals: CountingTotals;
  byCamera: CameraTotals[];
  identityAvailable: boolean;
  faceMatching: { available: boolean; reason: string | null };
  lastSightingAt: string | null;
  timezone: string;
}

/** newPeople: people seen for the first time in the period, in the slot of their first walk-past
 *  (null when the period has too many faces to compare). */
export interface SeriesPoint { start: string; walkPasts: number; face: number; body: number; newPeople: number | null }
export interface HeatCell { isoDow: number; hour: number; walkPasts: number; avgWalkPasts: number }
export interface Heatmap { cells: HeatCell[]; daysInRange: Record<number, number> }

export interface Sighting {
  id: number;
  cameraId: number;
  cameraName: string;
  firstSeenAt: string;
  lastSeenAt: string;
  durationSeconds: number;
  faceTrackId: number | null;
  bodyTrackId: number | null;
  personSource: 'recognized' | 'stranger' | 'unidentified';
  personName: string | null;
  recognitionResult: 'matched' | 'stranger' | null;
  eventCount: number;
  faceImagePath: string | null;
  bodyImagePath: string | null;
  // Who it was within the period; null when there was nothing usable to compare.
  personNo: number | null;
  newPerson: boolean | null;          // true: first time in the period (counted); false: came back
  personFirstSeenAt: string | null;
}

export interface CountingCamera {
  id: number;
  deviceId: number;
  name: string;
  deleted: boolean;
  countEnabled: boolean;
  countBasis: CountBasis;
}

/** A failed request; `status` 503 means the backend has no database (or can't reach it). */
export class CountingError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

type Json = Record<string, unknown>;

async function request<T = Json>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    cache: 'no-store',
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new CountingError(
      typeof detail === 'string' ? detail
        : Array.isArray(detail) ? String(detail[0]?.msg ?? 'Invalid input').replace(/^Value error, /, '')
          : `Request failed (${res.status})`,
      res.status,
    );
  }
  return body as T;
}

/** Box image path -> URL through the backend's image proxy. */
export const imageUrl = (uri: string | null | undefined) =>
  uri ? `/api/image?uri=${encodeURIComponent(uri)}` : undefined;

// ---------- time range ----------

const pad = (n: number) => String(n).padStart(2, '0');
const isoDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

/** start/end query values ('YYYY-MM-DD HH:mm:ss', box time). Missing end = now; missing both = today. */
export function timeRange(f: CountingFilters, today = new Date()): { start?: string; end?: string } {
  switch (f.preset) {
    case 'today':
      return {};
    case 'yesterday':
      return { start: `${isoDate(addDays(today, -1))} 00:00:00`, end: `${isoDate(today)} 00:00:00` };
    case 'last7':
      return { start: `${isoDate(addDays(today, -6))} 00:00:00` };
    case 'last30':
      return { start: `${isoDate(addDays(today, -29))} 00:00:00` };
    case 'custom': {
      const out: { start?: string; end?: string } = {};
      if (f.fromDate) out.start = `${f.fromDate} ${f.fromTime || '00:00'}:00`;
      // A day without a time means "through the end of that day".
      if (f.toDate) out.end = f.toTime ? `${f.toDate} ${f.toTime}:00` : `${isoDate(addDays(new Date(`${f.toDate}T00:00:00`), 1))} 00:00:00`;
      return out;
    }
  }
}

/** Roughly how many days the filters cover (for picking a chart granularity). */
export function rangeDays(f: CountingFilters, today = new Date()): number {
  const { start, end } = timeRange(f, today);
  const from = start ? new Date(start.replace(' ', 'T')) : new Date(`${isoDate(today)}T00:00:00`);
  const to = end ? new Date(end.replace(' ', 'T')) : today;
  return Math.max(0, (to.getTime() - from.getTime()) / 86_400_000);
}

/** ≤ 2 days: hourly bars; longer: daily. */
export const autoGranularity = (days: number): Granularity => (days <= 2 ? 'hour' : 'day');

export function filterQuery(f: CountingFilters, today = new Date()): URLSearchParams {
  const q = new URLSearchParams();
  for (const id of f.cameraIds) q.append('camera_id', String(id));
  const { start, end } = timeRange(f, today);
  if (start) q.set('start', start);
  if (end) q.set('end', end);
  if (f.hourFrom !== null && f.hourTo !== null) q.set('hours', `${f.hourFrom}-${f.hourTo}`);
  if (f.days.length) q.set('days', [...f.days].sort().join(','));
  return q;
}

// ---------- mapping ----------

const num = (v: unknown) => Number(v ?? 0);
const numOrNull = (v: unknown) => (v == null ? null : Number(v));

function toFaceEstimate(d: unknown): FaceEstimate | null {
  if (!d || typeof d !== 'object') return null;
  const e = d as Json;
  return {
    people: numOrNull(e.people), low: numOrNull(e.low), high: numOrNull(e.high),
    fingerprinted: num(e.fingerprinted), unusable: num(e.unusable), pending: num(e.pending),
    tooMany: Boolean(e.too_many),
  };
}

function toTotals(d: Json): CountingTotals {
  return {
    walkPasts: num(d.walk_pasts),
    visits: num(d.visits),
    uniquePeople: num(d.unique_people),
    knownPeople: num(d.known_people),
    strangerWalkPasts: num(d.stranger_walk_pasts),
    notComparedWalkPasts: num(d.not_compared_walk_pasts),
    paired: num(d.paired),
    faceOnly: num(d.face_only),
    bodyOnly: num(d.body_only),
    faceEstimate: toFaceEstimate(d.face_estimate),
  };
}

function toCamera(d: Json): CountingCamera {
  return {
    id: num(d.id),
    deviceId: num(d.device_id),
    name: String(d.name ?? `Camera ${d.id}`),
    deleted: Boolean(d.deleted),
    countEnabled: Boolean(d.count_enabled),
    countBasis: (d.count_basis as CountBasis) ?? 'merged',
  };
}

// ---------- requests ----------

export async function fetchCountingSummary(f: CountingFilters): Promise<CountingSummary> {
  const d = await request<Json>(`/api/counting/summary?${filterQuery(f)}`);
  return {
    totals: toTotals((d.totals as Json) ?? {}),
    byCamera: ((d.by_camera as Json[]) ?? []).map((c) => ({
      ...toTotals(c), cameraId: num(c.camera_id), name: String(c.name ?? ''), countBasis: c.count_basis as CountBasis,
    })),
    identityAvailable: Boolean(d.identity_available),
    faceMatching: {
      available: Boolean((d.face_matching as Json | undefined)?.available),
      reason: ((d.face_matching as Json | undefined)?.reason as string | null) ?? null,
    },
    lastSightingAt: d.last_sighting_at ? String(d.last_sighting_at) : null,
    timezone: String((d.period as Json | undefined)?.timezone ?? ''),
  };
}

export async function fetchCountingSeries(f: CountingFilters, granularity: Granularity): Promise<SeriesPoint[]> {
  const q = filterQuery(f);
  q.set('granularity', granularity);
  const d = await request<Json>(`/api/counting/series?${q}`);
  return ((d.points as Json[]) ?? []).map((p) => ({
    start: String(p.start), walkPasts: num(p.walk_pasts), face: num(p.face), body: num(p.body),
    newPeople: numOrNull(p.new_people),
  }));
}

export async function fetchCountingHeatmap(f: CountingFilters): Promise<Heatmap> {
  const d = await request<Json>(`/api/counting/heatmap?${filterQuery(f)}`);
  const days = (d.days_in_range as Json) ?? {};
  return {
    cells: ((d.cells as Json[]) ?? []).map((c) => ({
      isoDow: num(c.iso_dow), hour: num(c.hour), walkPasts: num(c.walk_pasts), avgWalkPasts: num(c.avg_walk_pasts),
    })),
    daysInRange: Object.fromEntries(Object.entries(days).map(([k, v]) => [Number(k), num(v)])),
  };
}

export async function fetchSightings(f: CountingFilters, page: number, size: number): Promise<{ total: number; items: Sighting[] }> {
  const q = filterQuery(f);
  q.set('page', String(page));
  q.set('size', String(size));
  const d = await request<Json>(`/api/counting/sightings?${q}`);
  return {
    total: num(d.total),
    items: ((d.items as Json[]) ?? []).map((s) => ({
      id: num(s.id),
      cameraId: num(s.camera_id),
      cameraName: String(s.camera_name ?? `Camera ${s.camera_id}`),
      firstSeenAt: String(s.first_seen_at),
      lastSeenAt: String(s.last_seen_at),
      durationSeconds: num(s.duration_seconds),
      faceTrackId: s.face_track_id == null ? null : num(s.face_track_id),
      bodyTrackId: s.body_track_id == null ? null : num(s.body_track_id),
      personSource: (s.person_source as Sighting['personSource']) ?? 'unidentified',
      personName: s.person_name ? String(s.person_name) : null,
      recognitionResult: (s.recognition_result as Sighting['recognitionResult']) ?? null,
      eventCount: num(s.event_count),
      faceImagePath: s.face_image_path ? String(s.face_image_path) : null,
      bodyImagePath: s.body_image_path ? String(s.body_image_path) : null,
      personNo: numOrNull(s.person_no),
      newPerson: s.new_person == null ? null : Boolean(s.new_person),
      personFirstSeenAt: s.person_first_seen_at ? String(s.person_first_seen_at) : null,
    })),
  };
}

export async function fetchCountingCameras(): Promise<CountingCamera[]> {
  return (await request<Json[]>('/api/counting/cameras')).map(toCamera);
}

export async function updateCountingCamera(
  id: number, change: { countEnabled?: boolean; countBasis?: CountBasis },
): Promise<CountingCamera> {
  const body: Json = {};
  if (change.countEnabled !== undefined) body.count_enabled = change.countEnabled;
  if (change.countBasis !== undefined) body.count_basis = change.countBasis;
  return toCamera(await request(`/api/counting/cameras/${id}`, { method: 'PATCH', body: JSON.stringify(body) }));
}
