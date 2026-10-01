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
};

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
