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

export interface NewDevice {
  name: string;
  protocol: string;   // 'rtsp'
  url: string;        // rtsp://host:port/path
  user: string;
  password: string;
}

/** Add a camera on the box. Resolves to the device id the box was given; throws with the backend's message. */
export async function createDevice(d: NewDevice): Promise<number> {
  const res = await fetch('/api/devices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(d),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg ?? 'Invalid input' : `Could not add the device (${res.status})`);
  }
  return Number(body?.device_id);
}

/** Remove a camera from the box. Throws with the backend's message on failure. */
export async function deleteDevice(deviceId: number): Promise<void> {
  const res = await fetch(`/api/devices/${deviceId}`, { method: 'DELETE' });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Could not delete the device (${res.status})`);
  }
}