// Calls the FastAPI backend and turns the box's raw records into simple rows for the table.
// The backend returns box data unchanged, so field names are looked up by several possible keys.

/** One library person the box compared the face against (faces[0].recognition_info[n]). */
export interface Candidate {
  personId: string;
  name: string;
  groups: string;
  similarity: string;
  baseImg?: string;
}

export interface Attribute {
  label: string;
  value: string;
}

export interface RecognitionRow {
  id: string;
  time: string;            // "2026-09-27 11:53:20"
  deviceId: string;
  device: string;
  living: string;
  personId: string;        // box person_id of the matched library person ('' for strangers)
  name: string;
  groups: string;
  similarity: string;
  faceImg?: string;
  panoramaImg?: string;
  baseImg?: string;
  // for the Record details panel
  trackId: string;
  attributes: Attribute[];       // age, gender, hat, glasses, mask, hairstyle, beard
  otherResults: Candidate[];     // lower-ranked candidates ("Other Result" in the box UI)
  raw: unknown;
}

export interface Device {
  id: string;
  name: string;
}

/** A person currently in the box's face library (from /face_manager/person/query). */
export interface Person {
  id: string;
  name: string;
}

type Json = Record<string, unknown>;

const MATCHED = 'face_comparison_successful';

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
  const v = find(resp, ['alarm_list', 'person_list', 'list', 'records', 'items', 'data']);
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
  if (v === undefined || v === null || v === '' || Number.isNaN(n)) return '—';
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

const norm = (s: unknown) => String(s ?? '').trim().toLowerCase();

// ---------- face attributes ----------
// The box sends attributes as numeric codes (1-based). Labels are copied from the box's own
// web UI language file (megcube-b4h-web/src/i18n/langs/en.js, the face-attribute section:
// gender1.., hair1.., beard1.., hat1.., respirator1.., glasses1..).
// Codes not listed here are shown as "Code N" so nothing is silently mislabelled.

const GENDER: Record<number, string> = { 1: 'Unknown', 2: 'Male', 3: 'Female' };
const HAT: Record<number, string> = { 1: 'Unknown', 2: 'Not wearing a hat', 3: 'Wearing a hat' };
const MASK: Record<number, string> = { 1: 'Unknown', 2: 'Not wearing a mask', 3: 'Wearing a mask' };
const GLASSES: Record<number, string> = { 1: 'Unknown', 2: 'Not wearing glasses', 3: 'Wearing glasses' };
const HAIR: Record<number, string> = {
  1: 'Unknown', 2: 'Flat top', 3: 'Middle part', 4: 'Side part', 5: 'Frontal baldness',
  6: 'Top baldness', 7: 'Baldness', 8: 'Curly', 9: 'Waves', 10: 'Braid', 11: 'Updo',
  12: 'Shoulder-length hair', 13: 'Short hair', 14: 'Long hair',
};
const BEARD: Record<number, string> = {
  1: 'Unknown', 2: 'No beard', 3: 'Walrus moustache', 4: 'Whiskers', 5: 'Toothbrush moustache',
  6: 'Becoming moustache', 7: 'Goatee', 8: 'White beard', 9: 'Imperial',
};

function label(map: Record<number, string>, v: unknown): string {
  if (v === undefined || v === null || v === '') return '—';
  const n = Number(v);
  return map[n] ?? `Code ${String(v)}`;
}

function faceAttributes(face: Json | undefined): Attribute[] {
  if (!face) return [];
  const age = Number(face.age);
  return [
    { label: 'Age', value: age > 0 ? String(age) : '—' },
    { label: 'Gender', value: label(GENDER, face.gender) },
    { label: 'Hat', value: label(HAT, face.wear_hat) },
    { label: 'Glasses', value: label(GLASSES, face.wear_glasses) },
    { label: 'Mask', value: label(MASK, face.wear_respirator) },
    { label: 'Hairstyle', value: label(HAIR, face.hair_style) },
    { label: 'Beard', value: label(BEARD, face.beard_class) },
  ];
}

// ---------- mapping ----------

/** Image path inside an `image_data` object: {image_data_format: 2, value: "./record_CHN0/...jpg"}. */
function imagePath(v: unknown): string | undefined {
  const d = v as Json | undefined;
  return typeof d?.value === 'string' && d.value ? d.value : undefined;
}

function toCandidate(c: Json): Candidate {
  const groups = ((c.group_info as Json[] | undefined) ?? [])
    .map((g) => String(g.group_name ?? ''))
    .filter(Boolean);
  return {
    personId: String(find(c, ['person_id']) ?? ''),
    // name may sit directly on the entry or nested (e.g. person_info.name) depending on firmware
    name: String(find(c, ['person_name', 'name']) ?? ''),
    groups: groups.length ? Array.from(new Set(groups)).join(', ') : '—',
    similarity: score(c.face_score),
    baseImg: imageUrl(imagePath(c.image_data)),
  };
}

function toRow(rec: unknown, index: number): RecognitionRow {
  // Box layout: faces[0].image_data = face crop, faces[0].recognition_info[0].image_data = library photo,
  // full_images[0].image_data = panorama. recognition_info is ranked best match first.
  const r = rec as Json;
  const face0 = (r.faces as Json[] | undefined)?.[0];
  const infos = (face0?.recognition_info as Json[] | undefined) ?? [];
  const match0 = infos[0];
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

  const top = match0 ? toCandidate(match0) : undefined;
  // Groups of the matched person only (not of every lower-ranked candidate).
  const fallbackGroups = findAll(rec, ['group_name', 'group_names']).map(String);
  const groups = top && top.groups !== '—'
    ? top.groups
    : fallbackGroups.length ? Array.from(new Set(fallbackGroups)).join(', ') : '—';

  const timeValue = find(rec, ['time_ms', 'capture_time', 'alarm_time', 'timestamp', 'time']);

  return {
    id: String(find(rec, ['data_uuid', 'alarm_id', 'record_id', 'uuid', 'id']) ?? `${index}-${timeValue}`),
    time: formatTime(timeValue),
    deviceId: String(find(rec, ['device_id', 'channel_id']) ?? ''),
    device: String(find(rec, ['device_name', 'channel_name', 'camera_name', 'source_name']) ?? '—'),
    living: score(find(rec, ['liveness_score', 'living_score', 'liveness', 'live_score', 'living_fraction'])),
    personId: top?.personId || String(find(rec, ['person_id']) ?? ''),
    name: top?.name || String(find(rec, ['person_name', 'name']) ?? '—'),
    groups,
    similarity: score(find(rec, ['face_score', 'similarity', 'score', 'compare_score', 'match_score'])),
    // unlabelled images: assume order face, panorama, base
    faceImg: imageUrl(face ?? rest.shift()),
    panoramaImg: imageUrl(panorama ?? rest.shift()),
    baseImg: imageUrl(base ?? rest.shift()),
    trackId: String(face0?.track_id ?? find(rec, ['track_id']) ?? '—'),
    attributes: faceAttributes(face0),
    otherResults: infos.slice(1).map(toCandidate).filter((c) => c.name),   // box pads with empty entries
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

/** One raw page of records straight from the box (no filtering). */
async function fetchRecognitionPage(q: RecognitionQuery): Promise<{ rows: RecognitionRow[]; total: number }> {
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

// How many records to pull per request when collecting a whole time range, and a safety cap.
const CHUNK = 30;          // the backend/box refuses more than 30 records per request
const MAX_RECORDS = 5000;

/**
 * Records for the table.
 *
 * The box keeps its alarm history even after a person is deleted from the face library.
 * - Matched: we pull every record in the time range, drop the ones whose person no longer
 *   exists, and paginate what's left here, so deleted people's rows are gone completely and
 *   "Total" / page counts are correct.
 * - Both modes: deleted people are also dropped from each row's "Other results".
 * If the person library can't be loaded, the box's data is shown unfiltered.
 */
export async function fetchRecognition(q: RecognitionQuery): Promise<{ rows: RecognitionRow[]; total: number }> {
  let exists: ((id: string, name: string) => boolean) | null = null;
  try {
    const people = await fetchPeople();
    const ids = new Set(people.map((p) => p.id).filter(Boolean));
    const names = new Set(people.map((p) => norm(p.name)).filter(Boolean));
    // Still in the library if either the id or the name matches. Records and the person list
    // don't always carry ids from the same place, so id alone can wrongly look "deleted".
    exists = (id, name) => (!!id && ids.has(id)) || names.has(norm(name));
  } catch {
    exists = null;
  }

  const prune = (r: RecognitionRow): RecognitionRow =>
    exists ? { ...r, otherResults: r.otherResults.filter((c) => exists!(c.personId, c.name)) } : r;

  if (q.minor !== MATCHED || !exists) {
    const page = await fetchRecognitionPage(q);
    return { rows: page.rows.map(prune), total: page.total };
  }

  // Collect the whole range from the box.
  const all: RecognitionRow[] = [];
  const first = await fetchRecognitionPage({ ...q, page: 1, size: CHUNK });
  all.push(...first.rows);
  const boxTotal = Math.min(first.total, MAX_RECORDS);
  for (let p = 2; all.length < boxTotal && first.rows.length > 0; p++) {
    const next = await fetchRecognitionPage({ ...q, page: p, size: CHUNK });
    if (next.rows.length === 0) break;
    all.push(...next.rows);
  }

  const kept = all.filter((r) => exists!(r.personId, r.name)).map(prune);
  const from = (q.page - 1) * q.size;
  return { rows: kept.slice(from, from + q.size), total: kept.length };
}

export async function fetchDevices(): Promise<Device[]> {
  const res = await fetch('/api/devices', { cache: 'no-store' });
  if (!res.ok) return [];
  return findList(await res.json()).map((d, i) => ({
    id: String(find(d, ['device_id', 'id', 'channel_id']) ?? i),
    name: String(find(d, ['device_name', 'name', 'channel_name']) ?? `Device ${i + 1}`),
  }));
}

/**
 * Everyone currently in the box's face library, from the backend's GET /api/people
 * (which pages through the box's /face_manager/person/query).
 * Throws on failure so callers can fall back to unfiltered data.
 */
export async function fetchPeople(): Promise<Person[]> {
  // The backend pages through the box's library and returns everyone at once.
  const res = await fetch('/api/people', { cache: 'no-store' });
  if (!res.ok) throw new Error(`Could not load people (${res.status})`);
  const json = (await res.json()) as { person_list?: { person_id?: string; name?: string }[] };
  return (json.person_list ?? []).map((p) => ({ id: String(p.person_id ?? ''), name: String(p.name ?? '') }));
}