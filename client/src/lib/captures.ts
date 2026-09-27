// Calls the FastAPI /api/capture endpoint (which already returns normalized,
// flat records) and joins in device names via the same fetchDevices used by
// the recognition page.
import { fetchDevices, type Device } from './recognition';

export type TargetType = 'all' | 'face' | 'body';

export interface CaptureRow {
  id: string;
  trackId: string;
  targetType: 'face' | 'body';
  deviceId: string;
  device: string;
  time: string; // "2026-09-27 15:35:22"
  timeMs: number;
  targetImage?: string;
  panoramicImage?: string;
  attributes: Record<string, number>;
}

interface RawCapture {
  alarm_id: number;
  track_id: string;
  target_type: 'face' | 'body';
  device_id: number;
  capture_time_ms: string;
  target_image: string | null;
  panoramic_image: string | null;
  attributes: Record<string, number>;
}

interface CaptureResponse {
  total_count: number;
  return_count: number;
  list: RawCapture[];
}

const imageUrl = (uri?: string | null) =>
  !uri ? undefined : uri.startsWith('http') || uri.startsWith('data:') ? uri : `/api/image?uri=${encodeURIComponent(uri)}`;

function formatTime(msStr: string): string {
  const ms = Number(msStr);
  if (!ms) return '—';
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** "wear_glasses" -> "Wear glasses". Values stay as raw codes — we don't have
 * the box's enum legend, so we don't guess what e.g. gender: 3 means. */
export function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

export interface CaptureQuery {
  start: string; // "YYYY-MM-DD HH:mm:ss"
  end: string;
  targetType: TargetType;
  page: number;
  size: number;
}

export async function fetchCaptures(
  q: CaptureQuery,
): Promise<{ rows: CaptureRow[]; total: number; devices: Device[] }> {
  const params = new URLSearchParams({
    start: q.start,
    end: q.end,
    target_type: q.targetType,
    page: String(q.page),
    size: String(q.size),
  });

  const [res, devices] = await Promise.all([
    fetch(`/api/capture?${params}`, { cache: 'no-store' }),
    fetchDevices(),
  ]);
  if (!res.ok) {
    throw new Error((await res.json().catch(() => null))?.detail ?? `Request failed (${res.status})`);
  }
  const data: CaptureResponse = await res.json();
  const deviceName = (id: string) => devices.find((d) => d.id === id)?.name ?? `Device ${id}`;

  const rows: CaptureRow[] = (data.list ?? []).map((r) => ({
    id: String(r.alarm_id),
    trackId: r.track_id,
    targetType: r.target_type,
    deviceId: String(r.device_id),
    device: deviceName(String(r.device_id)),
    time: formatTime(r.capture_time_ms),
    timeMs: Number(r.capture_time_ms) || 0,
    targetImage: imageUrl(r.target_image),
    panoramicImage: imageUrl(r.panoramic_image),
    attributes: r.attributes ?? {},
  }));

  return { rows, total: data.total_count ?? rows.length, devices };
}

export type { Device };