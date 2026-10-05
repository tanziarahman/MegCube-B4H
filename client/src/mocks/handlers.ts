import { http, HttpResponse } from 'msw';

export const sampleDevices = [
  {
    device_id: 1,
    device_name: 'Entrance camera',
    device_type: 'Video',
    protocol: 'rtsp',
    manufacturer: 'Hikvision',
    address: 'rtsp://viewer:****@192.168.1.20:554/stream1',
    online: true,
    state_code: 0,
    pulling_stream: true,
  },
  {
    device_id: 2,
    device_name: 'Loading bay',
    device_type: 'Video',
    protocol: 'rtsp',
    manufacturer: 'Axis',
    address: 'rtsp://viewer:****@192.168.1.21:554/stream1',
    online: false,
    state_code: 3,
    pulling_stream: false,
  },
];

export const samplePeople = {
  total_count: 1,
  person_list: [
    {
      person_id: 'p-1',
      person_info: { name: 'Ada Lovelace', code: 'ADA-1', birthday: '1815-12-10', remarks: 'Visitor' },
      groups: [{ group_id: 'staff', group_name: 'Staff' }],
    },
  ],
};

export const sampleRecognition = {
  total_count: 1,
  return_count: 1,
  list: [
    {
      data_uuid: 'record-1',
      additional: { alarm_id: 101 },
      device_id: 1,
      device_name: 'Entrance camera',
      time_ms: '1760000000000',
      person_name: 'Ada Lovelace',
      face_score: 98,
      liveness_score: 0.99,
      faces: [],
      full_images: [],
    },
  ],
};

export const sampleCaptures = {
  total_count: 1,
  return_count: 1,
  list: [
    {
      alarm_id: 2201,
      track_id: '5610081',
      target_type: 'face',
      device_id: 1,
      capture_time_ms: '1760000000000',
      target_image: null,
      panoramic_image: null,
      attributes: { age: 31 },
    },
  ],
};

export const sampleDashboard = {
  date: '2026-09-29',
  generated_at: '2026-09-29T14:30:00',
  period: { start: '2026-09-29 00:00:00', end: '2026-09-29 23:59:59', previous_start: '2026-09-28 00:00:00', previous_end: '2026-09-28 23:59:59' },
  health: {
    devices_total: 2,
    devices_online: 1,
    devices_offline: 1,
    streams_pulling: 1,
    tasks_total: 1,
    clock: { time: '2026-09-29 14:30:00', time_zone: 'Asia/Dhaka', source: 'box' },
  },
  activity: {
    matched: 12,
    strangers: 3,
    captures: 30,
    face_captures: 20,
    body_captures: 10,
    capture_breakdown_limited: false,
    previous_matched: 8,
    previous_strangers: 4,
    previous_captures: 25,
  },
  insights: {
    peak_hour: 14,
    busiest_device_id: '1',
    busiest_device: 'Entrance camera',
    average_match_score: 91.2,
    low_confidence_count: 1,
    low_liveness_count: 0,
    tracked_encounters: 30,
    face_encounters: 20,
    body_encounters: 10,
    unique_recognized_people: 4,
    recognized_encounters: 12,
    stranger_encounters: 3,
    recognized_capture_tracks: 12,
    recognition_coverage_percent: 60,
    busiest_capture_device: 'Entrance camera',
    analysis_sampled: 15,
    analysis_limited: false,
    top_people: [{ name: 'Ada Lovelace', count: 8 }],
    hourly_activity: Array.from({ length: 24 }, (_, hour) => ({ hour, count: hour === 14 ? 6 : 0 })),
    events: [{ id: '101', type: 'matched', person: 'Ada Lovelace', device_id: '1', device: 'Entrance camera', time_ms: 1760000000000, score: 98 }],
  },
  devices: [
    { id: 1, name: 'Entrance camera', online: true, state_code: 0, pulling_stream: true, task: 'FR' },
    { id: 2, name: 'Loading bay', online: false, state_code: 3, pulling_stream: false, task: null },
  ],
  attention: [{ severity: 'critical', type: 'offline_camera', message: 'Loading bay is offline', device_id: 2 }],
  meta: {
    source: 'box',
    fallback_reason: null,
    coverage_start: null,
    cache: { health: 'off', activity: 'off' },
    ingest_last_success_at: null,
  },
};

export const sampleAlarmStatus = {
  database: true,
  workers: { ingest: { running: true, last_ok: '2026-09-28T17:05:00+00:00', last_error: null }, mailer: { running: true } },
  smtp: { configured: true, host: 'smtp.example.org', sender: 'alarms@example.org' },
  timezone: 'Asia/Dhaka',
  max_recipients: 5,
  ingest: [],
  open_incidents: 1,
  notifications: { pending: 0, failed: 0 },
};

export const sampleAlarmCameras = [
  { id: 1, device_id: 1, name: 'Hikvision', deleted: false },
  { id: 2, device_id: 2, name: 'IPCAM-D3', deleted: false },
];

export const sampleContacts = [
  { id: 1, name: 'Guard desk', email: 'guard@example.org', is_active: true, rule_count: 1 },
];

export const sampleRule = {
  id: 7, name: 'Night watch D3', description: null, is_enabled: true, severity: 'critical',
  event_kinds: ['stranger', 'matched'], match_mode: 'anyone', min_match_score: null, min_liveness: null,
  timezone: 'Asia/Dhaka', cooldown_seconds: 300, dedupe_scope: 'camera', max_delay_seconds: 300,
  email_delayed: false, attach_snapshot: true, version: 1, last_fired_at: null,
  camera_ids: [2], windows: Array.from({ length: 7 }, (_, i) => ({ iso_dow: i + 1, start: '22:00', end: '06:00' })),
  targets: [], recipient_ids: [1],
};

export const sampleIncident = {
  id: 41, public_id: '0b5c6c1e-0000-4000-8000-000000000001', rule_id: 7, rule_name: 'Night watch D3',
  severity: 'critical', camera_id: 2, camera_name: 'IPCAM-D3', track_id: 5727190, person_uuid: null,
  person_name: null, is_stranger: true, occurred_at: '2026-09-28T17:04:30+00:00', detected_at: '2026-09-28T17:04:34+00:00',
  delay_seconds: 4, is_delayed: false, event_count: 3, last_event_at: '2026-09-28T17:06:00+00:00', status: 'open',
  acknowledged_by: null, acknowledged_at: null, note: null, snapshot_path: './record_CHN0/face.jpg',
};

export const sampleIncidentDetail = {
  ...sampleIncident,
  rule_snapshot: {},
  events: [{ id: 900, alarm_id: 12345, kind: 'stranger', occurred_at: '2026-09-28T17:04:30+00:00', face_track_id: 5727190,
    body_track_id: null, person_name: null, match_score: 41, liveness_score: null, face_image_path: './record_CHN0/face.jpg',
    body_image_path: null, panorama_path: './record_CHN0/full.jpg' }],
  notifications: [{ id: 1, to_address: 'guard@example.org', status: 'sent', attempts: 1, last_error: null,
    sent_at: '2026-09-28T17:04:40+00:00', next_attempt_at: '2026-09-28T17:04:34+00:00' }],
};

const countingTotals = {
  walk_pasts: 12, visits: 12, unique_people: 12, known_people: 0, stranger_walk_pasts: 0,
  not_compared_walk_pasts: 12, paired: 9, face_only: 2, body_only: 1,
};

export const sampleCountingSummary = {
  period: { start: '2026-10-04T00:00:00+06:00', end: '2026-10-04T15:00:00+06:00', timezone: 'Asia/Dhaka' },
  totals: {
    ...countingTotals,
    face_estimate: { people: 8, low: 6, high: 10, fingerprinted: 10, unusable: 2, pending: 0, too_many: false },
  },
  by_camera: [
    { camera_id: 1, name: 'Hikvision', count_basis: 'merged', ...countingTotals, walk_pasts: 2, visits: 2, unique_people: 2, paired: 2, face_only: 0, body_only: 0 },
    { camera_id: 2, name: 'IPCAM-D3', count_basis: 'merged', ...countingTotals, walk_pasts: 10, visits: 10, unique_people: 10, paired: 7 },
  ],
  identity_available: false,
  face_matching: { available: true, reason: null },
  last_sighting_at: '2026-10-04T09:12:03+00:00',
};

export const sampleCountingSeries = {
  granularity: 'hour',
  points: Array.from({ length: 24 }, (_, h) => ({
    start: `2026-10-04T${String(h).padStart(2, '0')}:00:00+06:00`, walk_pasts: h === 9 ? 8 : h === 14 ? 4 : 0, face: 0, body: 0,
    new_people: h === 9 ? 6 : h === 14 ? 2 : 0,
  })),
};

export const sampleCountingHeatmap = {
  cells: [{ iso_dow: 7, hour: 9, walk_pasts: 8, avg_walk_pasts: 8 }, { iso_dow: 7, hour: 14, walk_pasts: 4, avg_walk_pasts: 4 }],
  days_in_range: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 1 },
};

export const sampleSighting = {
  id: 881, camera_id: 2, camera_name: 'IPCAM-D3', first_seen_at: '2026-10-04T03:12:00+00:00',
  last_seen_at: '2026-10-04T03:12:01.300000+00:00', duration_seconds: 1.3, face_track_id: 5735752, body_track_id: 5735751,
  person_source: 'unidentified', person_name: null, recognition_result: null, event_count: 3,
  face_image_path: './record_CHN0/face.jpg', body_image_path: './record_CHN0/body.jpg',
  person_no: 3, new_person: false, person_first_seen_at: '2026-10-04T03:01:00+00:00',
};

export const sampleCountingCameras = [
  { id: 1, device_id: 1, name: 'Hikvision', deleted: false, count_enabled: true, count_basis: 'merged' },
  { id: 2, device_id: 2, name: 'IPCAM-D3', deleted: false, count_enabled: true, count_basis: 'merged' },
];

export const handlers = [
  http.get('/api/dashboard/summary', () => HttpResponse.json(sampleDashboard)),
  http.get('/api/devices/detail', () => HttpResponse.json(sampleDevices)),
  http.post('/api/devices', () => HttpResponse.json({ device_id: 3 }, { status: 201 })),
  http.get('/api/personnel/groups', () => HttpResponse.json({ groups: [{ group_id: 'staff', group_name: 'Staff' }] })),
  http.get('/api/personnel', () => HttpResponse.json(samplePeople)),
  http.post('/api/personnel', () => HttpResponse.json({}, { status: 201 })),
  http.get('/api/people', () => HttpResponse.json({ total_count: 1, person_list: [{ person_id: 'p-1', name: 'Ada Lovelace' }] })),
  http.get('/api/devices', () => HttpResponse.json([{ id: 1, name: 'Entrance camera' }])),
  http.get('/api/recognition', () => HttpResponse.json(sampleRecognition)),
  http.get('/api/capture', () => HttpResponse.json(sampleCaptures)),
  http.delete('/api/recognition/:alarmId', ({ params }) => HttpResponse.json({ deleted: Number(params.alarmId) })),
  http.get('/api/alarms/status', () => HttpResponse.json(sampleAlarmStatus)),
  http.get('/api/alarms/cameras', () => HttpResponse.json(sampleAlarmCameras)),
  http.get('/api/alarms/contacts', () => HttpResponse.json(sampleContacts)),
  http.get('/api/alarms/rules', () => HttpResponse.json([sampleRule])),
  http.post('/api/alarms/rules', async ({ request }) => HttpResponse.json({ ...sampleRule, ...(await request.json() as object), id: 8 }, { status: 201 })),
  http.get('/api/alarms/incidents', () => HttpResponse.json({ total: 1, page: 1, size: 20, items: [sampleIncident] })),
  http.get('/api/alarms/incidents/:ref', () => HttpResponse.json(sampleIncidentDetail)),
  http.patch('/api/alarms/incidents/:id', async ({ request }) => HttpResponse.json({ ...sampleIncident, ...(await request.json() as object) })),
  http.get('/api/counting/summary', () => HttpResponse.json(sampleCountingSummary)),
  http.get('/api/counting/series', () => HttpResponse.json(sampleCountingSeries)),
  http.get('/api/counting/heatmap', () => HttpResponse.json(sampleCountingHeatmap)),
  http.get('/api/counting/sightings', () => HttpResponse.json({ total: 1, page: 1, size: 20, items: [sampleSighting] })),
  http.get('/api/counting/cameras', () => HttpResponse.json(sampleCountingCameras)),
  http.patch('/api/counting/cameras/:id', async ({ params, request }) => HttpResponse.json({
    ...sampleCountingCameras.find((c) => c.id === Number(params.id)), ...(await request.json() as object) })),
];

export const serverErrorHandlers = {
  devices: http.get('/api/devices/detail', () => HttpResponse.json({ detail: 'Service unavailable' }, { status: 503 })),
  people: http.get('/api/personnel', () => HttpResponse.json({ detail: 'Backend unavailable' }, { status: 500 })),
  recognition: http.get('/api/recognition', () => HttpResponse.json({ detail: 'Request timed out' }, { status: 504 })),
};

export const emptyHandlers = {
  devices: http.get('/api/devices/detail', () => HttpResponse.json([])),
  people: http.get('/api/personnel', () => HttpResponse.json({ total_count: 0, person_list: [] })),
  recognition: http.get('/api/recognition', () => HttpResponse.json({ total_count: 0, return_count: 0, list: [] })),
};

export const networkFailureHandlers = {
  devices: http.get('/api/devices/detail', () => HttpResponse.error()),
  people: http.get('/api/personnel', () => HttpResponse.error()),
  recognition: http.get('/api/recognition', () => HttpResponse.error()),
};
