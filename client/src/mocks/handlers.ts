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

export const handlers = [
  http.get('/api/devices/detail', () => HttpResponse.json(sampleDevices)),
  http.post('/api/devices', () => HttpResponse.json({ device_id: 3 }, { status: 201 })),
  http.get('/api/personnel/groups', () => HttpResponse.json({ groups: [{ group_id: 'staff', group_name: 'Staff' }] })),
  http.get('/api/personnel', () => HttpResponse.json(samplePeople)),
  http.post('/api/personnel', () => HttpResponse.json({}, { status: 201 })),
  http.get('/api/people', () => HttpResponse.json({ total_count: 1, person_list: [{ person_id: 'p-1', name: 'Ada Lovelace' }] })),
  http.get('/api/devices', () => HttpResponse.json([{ id: 1, name: 'Entrance camera' }])),
  http.get('/api/recognition', () => HttpResponse.json(sampleRecognition)),
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
