// Camera list for the Devices page, from the backend's GET /api/devices/detail.
// RTSP passwords are masked by the backend and never reach the browser.

export interface DeviceDetail {
  id: number;
  name: string;
  type: string;          // "Video"
  protocol: string;      // "rtsp"
  manufacturer: string;
  address: string;       // rtsp://user:****@host:port/path
  online: boolean;
  stateCode: number | null;
  pullingStream: boolean;
}

export async function fetchDeviceDetails(): Promise<DeviceDetail[]> {
  const res = await fetch('/api/devices/detail', { cache: 'no-store' });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Request failed (${res.status})`);
  const list = (await res.json()) as Record<string, unknown>[];
  return list.map((d) => ({
    id: Number(d.device_id),
    name: String(d.device_name ?? ''),
    type: String(d.device_type ?? ''),
    protocol: String(d.protocol ?? ''),
    manufacturer: String(d.manufacturer ?? ''),
    address: String(d.address ?? ''),
    online: Boolean(d.online),
    stateCode: d.state_code == null ? null : Number(d.state_code),
    pullingStream: Boolean(d.pulling_stream),
  }));
}
