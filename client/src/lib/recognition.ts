// Calls the FastAPI backend and turns the box's raw records into simple rows for the table.
// The backend returns box data unchanged, so field names are looked up by several possible keys.

export interface RecognitionRow {
  id: string;
  time: string;            // "2026-09-27 11:53:20"
  deviceId: string;
  device: string;
  living: string;
  name: string;
  groups: string;
  similarity: string;
  faceImg?: string;
  panoramaImg?: string;
  baseImg?: string;
  raw: unknown;
}

export interface Device {
  id: string;
  name: string;
}

type Json = Record<string, unknown>;

// ---------- small helpers for unknown JSON ----------

/** First non-empty value found under any of `keys`, searching nested objects/arrays. */
function find(obj: unknown, keys: string[]): unknown {
  const queue: unknown[] = [obj];
  while (queue.length) {
    const cur = queue.shift();
    if (Array.isArray(cur)) queue.push(...cur);
    else if (cur && typeof cur === 'object') {
      const o = cur as Json;
      for (const k of keys) {
        const v = o[k];
        if (v !== undefined && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)) return v;
      }
      queue.push(...Object.values(o).filter((v) => v && typeof v === 'object'));
    }
  }
  return undefined;
}

/** Every value found under any of `keys` (e.g. all group names). */
function findAll(obj: unknown, keys: string[]): unknown[] {
  const out: unknown[] = [];
  const walk = (node: unknown) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === 'object') {
      for (const [k, v] of Object.entries(node as Json)) {
        if (keys.includes(k) && v !== null && v !== '') out.push(...(Array.isArray(v) ? v : [v]));
        else if (v && typeof v === 'object') walk(v);
      }
    }
  };
  walk(obj);
  return out;
}

/** The array of records inside a box response. */
function findList(resp: unknown): unknown[] {
  if (Array.isArray(resp)) return resp;
  const v = find(resp, ['alarm_list', 'list', 'records', 'items', 'data']);
  return Array.isArray(v) ? v : [];
}

/** All image URIs in a record, in order, with any type label next to them. */
function collectImages(obj: unknown): { uri: string; type: string }[] {
  const out: { uri: string; type: string }[] = [];
  const walk = (node: unknown) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === 'object') {
      const o = node as Json;
      let uri = o.image_uri ?? o.uri ?? o.url ?? o.image_url;
      if (uri === undefined && (o.image_data_format === 2 || o.image_data_format === '2')) uri = o.image_data;
      if (typeof uri === 'string' && uri) {
        out.push({ uri, type: String(o.image_type ?? o.type ?? o.pic_type ?? '').toLowerCase() });
      }
      Object.values(o).forEach((v) => v && typeof v === 'object' && walk(v));
    }
  };
  walk(obj);
  return out;
}

const imageUrl = (uri?: string) =>
  !uri ? undefined : uri.startsWith('http') || uri.startsWith('data:') ? uri : `/api/image?uri=${encodeURIComponent(uri)}`;

const score = (v: unknown) => {
  const n = Number(v);
  if (v === undefined || Number.isNaN(n)) return '—';
  return (n > 0 && n <= 1 ? n * 100 : n).toFixed(1);   // 0.79 -> 79.0
};

function formatTime(v: unknown): string {
  let ms = Number(v);
  if (!ms) return '—';
  if (ms < 1e12) ms *= 1000;                              // seconds -> ms
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// ---------- mapping ----------

/** Image path inside an `image_data` object: {image_data_format: 2, value: "./record_CHN0/...jpg"}. */
function imagePath(v: unknown): string | undefined {
  const d = v as Json | undefined;
  return typeof d?.value === 'string' && d.value ? d.value : undefined;
}

function toRow(rec: unknown, index: number): RecognitionRow {
  // Box layout: faces[0].image_data = face crop, faces[0].recognition_info[0].image_data = library photo,
  // full_images[0].image_data = panorama.
  const r = rec as Json;
  const face0 = (r.faces as Json[] | undefined)?.[0];
  const match0 = (face0?.recognition_info as Json[] | undefined)?.[0];
  const full0 = (r.full_images as Json[] | undefined)?.[0];
  const known = {
    face: imagePath(face0?.image_data),
    base: imagePath(match0?.image_data),
    panorama: imagePath(full0?.image_data),
  };

  const images = collectImages(rec);
  const byType = (words: string[]) => images.find((i) => words.some((w) => i.type.includes(w)))?.uri;
  const face = known.face ?? byType(['face', 'crop', 'snap', 'target']);
  const panorama = known.panorama ?? byType(['panor', 'background', 'scene', 'full', 'bg']);
  const base = known.base ?? byType(['base', 'library', 'register', 'person', 'db']);
  const rest = images.map((i) => i.uri).filter((u) => u !== face && u !== panorama && u !== base);

  const groups = findAll(rec, ['group_name', 'group_names']).map(String);
  const timeValue = find(rec, ['time_ms', 'capture_time', 'alarm_time', 'timestamp', 'time']);

  return {
    id: String(find(rec, ['data_uuid', 'alarm_id', 'record_id', 'uuid', 'id']) ?? `${index}-${timeValue}`),
    time: formatTime(timeValue),
    deviceId: String(find(rec, ['device_id', 'channel_id']) ?? ''),
    device: String(find(rec, ['device_name', 'channel_name', 'camera_name', 'source_name']) ?? '—'),
    living: score(find(rec, ['liveness_score', 'living_score', 'liveness', 'live_score', 'living_fraction'])),
    name: String(find(rec, ['person_name', 'name']) ?? '—'),
    groups: groups.length ? Array.from(new Set(groups)).join(', ') : '—',
    similarity: score(find(rec, ['face_score', 'similarity', 'score', 'compare_score', 'match_score'])),
    // unlabelled images: assume order face, panorama, base
    faceImg: imageUrl(face ?? rest.shift()),
    panoramaImg: imageUrl(panorama ?? rest.shift()),
    baseImg: imageUrl(base ?? rest.shift()),
    raw: rec,
  };
}

// ---------- API calls ----------

export interface RecognitionQuery {
  start: string;   // "YYYY-MM-DD HH:mm:ss"
  end: string;
  page: number;
  size: number;
  minor: string;
}

export async function fetchRecognition(q: RecognitionQuery): Promise<{ rows: RecognitionRow[]; total: number }> {
  const params = new URLSearchParams({
    start: q.start, end: q.end, page: String(q.page), size: String(q.size), minor: q.minor,
  });
  const res = await fetch(`/api/recognition?${params}`, { cache: 'no-store' });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Request failed (${res.status})`);
  const data: unknown = await res.json();
  const list = findList(data);
  const total = Number(find(data, ['total', 'total_num', 'total_count', 'count'])) || list.length;
  return { rows: list.map(toRow), total };
}

export async function fetchDevices(): Promise<Device[]> {
  const res = await fetch('/api/devices', { cache: 'no-store' });
  if (!res.ok) return [];
  return findList(await res.json()).map((d, i) => ({
    id: String(find(d, ['device_id', 'id', 'channel_id']) ?? i),
    name: String(find(d, ['device_name', 'name', 'channel_name']) ?? `Device ${i + 1}`),
  }));
}
