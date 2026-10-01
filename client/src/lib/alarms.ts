// Alarms: rules, email recipients and incidents, from the backend's /api/alarms/* routes.
// These live in the portal's own database, not on the box.

export type Severity = 'info' | 'warning' | 'critical';
export type EventKind = 'matched' | 'stranger' | 'face_capture' | 'body_capture';
export type MatchMode = 'anyone' | 'strangers' | 'known' | 'targets';
export type DedupeScope = 'camera' | 'track';
export type IncidentStatus = 'open' | 'acknowledged' | 'resolved' | 'false_alarm';

export const EVENT_KIND_LABELS: Record<EventKind, string> = {
  stranger: 'Stranger',
  matched: 'Recognised person',
  face_capture: 'Face capture',
  body_capture: 'Body capture',
};
export const MATCH_MODE_LABELS: Record<MatchMode, string> = {
  anyone: 'Anyone',
  strangers: 'Strangers only',
  known: 'Anyone in the face library',
  targets: 'Specific people or groups',
};
export const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
  false_alarm: 'False alarm',
};
/** 1 = Monday, as the backend stores it. */
export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export interface AlarmStatus {
  database: boolean;
  smtpConfigured: boolean;
  smtpSender: string | null;
  timezone: string;
  maxRecipients: number;
  openIncidents: number;
  pendingEmails: number;
  failedEmails: number;
  ingestRunning: boolean;
  ingestError: string | null;
  lastPollOk: string | null;
}

export interface AlarmCamera { id: number; deviceId: number; name: string; deleted: boolean }

export interface Contact { id: number; name: string; email: string; isActive: boolean; ruleCount: number }

export interface RuleWindow { isoDow: number; start: string; end: string }   // "HH:MM"
export interface RuleTarget { type: 'person' | 'group'; value: string; label: string | null }

export interface AlarmRule {
  id: number;
  name: string;
  description: string;
  isEnabled: boolean;
  severity: Severity;
  eventKinds: EventKind[];
  matchMode: MatchMode;
  minMatchScore: number | null;
  minLiveness: number | null;
  timezone: string;
  cooldownSeconds: number;
  dedupeScope: DedupeScope;
  maxDelaySeconds: number;
  emailDelayed: boolean;
  attachSnapshot: boolean;
  cameraIds: number[];
  windows: RuleWindow[];
  targets: RuleTarget[];
  recipientIds: number[];
  version: number;
  lastFiredAt: string | null;
}

export type RuleInput = Omit<AlarmRule, 'id' | 'version' | 'lastFiredAt'>;

export interface Incident {
  id: number;
  publicId: string;
  ruleId: number | null;
  ruleName: string;
  severity: Severity;
  cameraId: number;
  cameraName: string;
  trackId: number | null;
  personName: string | null;
  isStranger: boolean;
  occurredAt: string;
  detectedAt: string;
  delaySeconds: number;
  isDelayed: boolean;
  eventCount: number;
  lastEventAt: string;
  status: IncidentStatus;
  acknowledgedBy: string | null;
  acknowledgedAt: string | null;
  note: string | null;
  snapshotPath: string | null;
}

export interface IncidentEvent {
  id: number;
  kind: EventKind;
  occurredAt: string;
  trackId: number | null;
  personName: string | null;
  matchScore: number | null;
  imagePath: string | null;
  panoramaPath: string | null;
}

export interface IncidentNotification {
  id: number;
  toAddress: string;
  status: 'pending' | 'sending' | 'sent' | 'failed' | 'cancelled';
  attempts: number;
  lastError: string | null;
  sentAt: string | null;
}

export interface IncidentDetail extends Incident {
  events: IncidentEvent[];
  notifications: IncidentNotification[];
}

export interface IncidentPage { total: number; items: Incident[] }

// ---------- helpers ----------

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
    throw new Error(
      typeof detail === 'string' ? detail
        : Array.isArray(detail) ? String(detail[0]?.msg ?? 'Invalid input').replace(/^Value error, /, '')
          : `Request failed (${res.status})`,
    );
  }
  return body as T;
}

const str = (v: unknown) => (v == null ? '' : String(v));
const numOrNull = (v: unknown) => (v == null || v === '' ? null : Number(v));

/** Box image path -> URL through the backend's image proxy. */
export const imageUrl = (uri: string | null | undefined) =>
  uri ? `/api/image?uri=${encodeURIComponent(uri)}` : undefined;

/** Who triggered it, in words. */
export const whoLabel = (i: Pick<Incident, 'personName' | 'isStranger'>) =>
  i.personName || (i.isStranger ? 'Stranger' : 'Unidentified person');

// ---------- mapping ----------

function toStatus(d: Json): AlarmStatus {
  const smtp = (d.smtp ?? {}) as Json;
  const ingest = ((d.workers as Json)?.ingest ?? {}) as Json;
  const emails = (d.notifications ?? {}) as Json;
  return {
    database: Boolean(d.database),
    smtpConfigured: Boolean(smtp.configured),
    smtpSender: smtp.sender ? String(smtp.sender) : null,
    timezone: str(d.timezone),
    maxRecipients: Number(d.max_recipients ?? 5),
    openIncidents: Number(d.open_incidents ?? 0),
    pendingEmails: Number(emails.pending ?? 0),
    failedEmails: Number(emails.failed ?? 0),
    ingestRunning: Boolean(ingest.running),
    ingestError: ingest.last_error ? String(ingest.last_error) : null,
    lastPollOk: ingest.last_ok ? String(ingest.last_ok) : null,
  };
}

function toRule(d: Json): AlarmRule {
  return {
    id: Number(d.id),
    name: str(d.name),
    description: str(d.description),
    isEnabled: Boolean(d.is_enabled),
    severity: str(d.severity) as Severity,
    eventKinds: ((d.event_kinds as string[]) ?? []) as EventKind[],
    matchMode: str(d.match_mode) as MatchMode,
    minMatchScore: numOrNull(d.min_match_score),
    minLiveness: numOrNull(d.min_liveness),
    timezone: str(d.timezone),
    cooldownSeconds: Number(d.cooldown_seconds ?? 0),
    dedupeScope: str(d.dedupe_scope) as DedupeScope,
    maxDelaySeconds: Number(d.max_delay_seconds ?? 0),
    emailDelayed: Boolean(d.email_delayed),
    attachSnapshot: Boolean(d.attach_snapshot),
    cameraIds: ((d.camera_ids as number[]) ?? []).map(Number),
    windows: ((d.windows as Json[]) ?? []).map((w) => ({ isoDow: Number(w.iso_dow), start: str(w.start), end: str(w.end) })),
    targets: ((d.targets as Json[]) ?? []).map((t) => ({
      type: str(t.type) as RuleTarget['type'], value: str(t.value), label: t.label ? String(t.label) : null,
    })),
    recipientIds: ((d.recipient_ids as number[]) ?? []).map(Number),
    version: Number(d.version ?? 1),
    lastFiredAt: d.last_fired_at ? String(d.last_fired_at) : null,
  };
}

function fromRule(r: RuleInput): Json {
  return {
    name: r.name.trim(),
    description: r.description.trim() || null,
    is_enabled: r.isEnabled,
    severity: r.severity,
    event_kinds: r.eventKinds,
    match_mode: r.matchMode,
    min_match_score: r.minMatchScore,
    min_liveness: r.minLiveness,
    timezone: r.timezone,
    cooldown_seconds: r.cooldownSeconds,
    dedupe_scope: r.dedupeScope,
    max_delay_seconds: r.maxDelaySeconds,
    email_delayed: r.emailDelayed,
    attach_snapshot: r.attachSnapshot,
    camera_ids: r.cameraIds,
    windows: r.windows.map((w) => ({ iso_dow: w.isoDow, start: w.start, end: w.end })),
    targets: r.targets.map((t) => ({ type: t.type, value: t.value, label: t.label })),
    recipient_ids: r.recipientIds,
  };
}

function toIncident(d: Json): Incident {
  return {
    id: Number(d.id),
    publicId: str(d.public_id),
    ruleId: d.rule_id == null ? null : Number(d.rule_id),
    ruleName: str(d.rule_name),
    severity: str(d.severity) as Severity,
    cameraId: Number(d.camera_id),
    cameraName: str(d.camera_name) || `Camera ${d.camera_id}`,
    trackId: d.track_id == null ? null : Number(d.track_id),
    personName: d.person_name ? String(d.person_name) : null,
    isStranger: Boolean(d.is_stranger),
    occurredAt: str(d.occurred_at),
    detectedAt: str(d.detected_at),
    delaySeconds: Number(d.delay_seconds ?? 0),
    isDelayed: Boolean(d.is_delayed),
    eventCount: Number(d.event_count ?? 1),
    lastEventAt: str(d.last_event_at),
    status: str(d.status) as IncidentStatus,
    acknowledgedBy: d.acknowledged_by ? String(d.acknowledged_by) : null,
    acknowledgedAt: d.acknowledged_at ? String(d.acknowledged_at) : null,
    note: d.note ? String(d.note) : null,
    snapshotPath: d.snapshot_path ? String(d.snapshot_path) : null,
  };
}

// ---------- API ----------

export async function fetchAlarmStatus(): Promise<AlarmStatus> {
  return toStatus(await request('/api/alarms/status'));
}

export async function fetchAlarmCameras(): Promise<AlarmCamera[]> {
  const list = await request<Json[]>('/api/alarms/cameras');
  return list.map((c) => ({ id: Number(c.id), deviceId: Number(c.device_id), name: str(c.name), deleted: Boolean(c.deleted) }));
}

export async function fetchContacts(): Promise<Contact[]> {
  const list = await request<Json[]>('/api/alarms/contacts');
  return list.map((c) => ({
    id: Number(c.id), name: str(c.name), email: str(c.email), isActive: Boolean(c.is_active), ruleCount: Number(c.rule_count ?? 0),
  }));
}

export async function saveContact(c: { id?: number; name: string; email: string; isActive: boolean }): Promise<void> {
  const body = JSON.stringify({ name: c.name.trim(), email: c.email.trim(), is_active: c.isActive });
  await request(c.id ? `/api/alarms/contacts/${c.id}` : '/api/alarms/contacts', { method: c.id ? 'PUT' : 'POST', body });
}

export async function deleteContact(id: number): Promise<void> {
  await request(`/api/alarms/contacts/${id}`, { method: 'DELETE' });
}

export async function sendTestEmail(to: string): Promise<void> {
  await request('/api/alarms/test-email', { method: 'POST', body: JSON.stringify({ to: to.trim() }) });
}

export async function fetchRules(): Promise<AlarmRule[]> {
  return (await request<Json[]>('/api/alarms/rules')).map(toRule);
}

export async function createRule(r: RuleInput): Promise<AlarmRule> {
  return toRule(await request('/api/alarms/rules', { method: 'POST', body: JSON.stringify(fromRule(r)) }));
}

export async function updateRule(id: number, version: number, r: RuleInput): Promise<AlarmRule> {
  return toRule(await request(`/api/alarms/rules/${id}`, { method: 'PUT', body: JSON.stringify({ ...fromRule(r), version }) }));
}

export async function setRuleEnabled(id: number, isEnabled: boolean): Promise<AlarmRule> {
  return toRule(await request(`/api/alarms/rules/${id}/enabled`, { method: 'PATCH', body: JSON.stringify({ is_enabled: isEnabled }) }));
}

export async function deleteRule(id: number): Promise<void> {
  await request(`/api/alarms/rules/${id}`, { method: 'DELETE' });
}

export interface IncidentFilters {
  status?: IncidentStatus | '';
  ruleId?: number | '';
  cameraId?: number | '';
  from?: string;   // YYYY-MM-DD, box time zone
  to?: string;
  page?: number;
  size?: number;
}

export async function fetchIncidents(f: IncidentFilters = {}): Promise<IncidentPage> {
  const q = new URLSearchParams();
  if (f.status) q.append('status', f.status);
  if (f.ruleId) q.set('rule_id', String(f.ruleId));
  if (f.cameraId) q.set('camera_id', String(f.cameraId));
  if (f.from) q.set('start', `${f.from} 00:00:00`);
  if (f.to) q.set('end', `${f.to} 23:59:59`);
  q.set('page', String(f.page ?? 1));
  q.set('size', String(f.size ?? 20));
  const body = await request<Json>(`/api/alarms/incidents?${q}`);
  return { total: Number(body.total ?? 0), items: ((body.items as Json[]) ?? []).map(toIncident) };
}

export async function fetchIncident(ref: string): Promise<IncidentDetail> {
  const d = await request<Json>(`/api/alarms/incidents/${encodeURIComponent(ref)}`);
  return {
    ...toIncident(d),
    events: ((d.events as Json[]) ?? []).map((e) => ({
      id: Number(e.id),
      kind: str(e.kind) as EventKind,
      occurredAt: str(e.occurred_at),
      trackId: e.face_track_id != null ? Number(e.face_track_id) : e.body_track_id != null ? Number(e.body_track_id) : null,
      personName: e.person_name ? String(e.person_name) : null,
      matchScore: numOrNull(e.match_score),
      imagePath: (e.face_image_path || e.body_image_path || null) as string | null,
      panoramaPath: (e.panorama_path || null) as string | null,
    })),
    notifications: ((d.notifications as Json[]) ?? []).map((n) => ({
      id: Number(n.id),
      toAddress: str(n.to_address),
      status: str(n.status) as IncidentNotification['status'],
      attempts: Number(n.attempts ?? 0),
      lastError: n.last_error ? String(n.last_error) : null,
      sentAt: n.sent_at ? String(n.sent_at) : null,
    })),
  };
}

export async function updateIncident(id: number, change: { status?: IncidentStatus; note?: string; by?: string }): Promise<Incident> {
  return toIncident(await request(`/api/alarms/incidents/${id}`, { method: 'PATCH', body: JSON.stringify(change) }));
}
