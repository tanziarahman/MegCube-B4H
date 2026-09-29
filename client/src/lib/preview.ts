// Live preview: camera list + MJPEG stream URLs from the FastAPI backend.

export interface PreviewCamera {
  id: number;
  name: string;
  online: boolean;
  task: string | null;   // analysis task on this camera, if any
  stream_token: string | null; // signed "exp=..&sig=.." that lets the <img> open the video (API key can't be sent by an <img>)
}

// Video goes straight to the backend (not through the Next.js /api proxy) so frames aren't buffered.
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

export async function fetchPreviewCameras(): Promise<PreviewCamera[]> {
  const res = await fetch('/api/preview/cameras', { cache: 'no-store' });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Request failed (${res.status})`);
  return res.json();
}

/** hd = main stream (full resolution), otherwise the light sub-stream. `retry` forces a fresh stream. */
export function streamUrl(camera: PreviewCamera, hd = false, retry = 0): string {
  const width = hd ? 1920 : 640;
  const token = camera.stream_token ? `&${camera.stream_token}` : '';
  return `${BACKEND}/api/preview/${camera.id}/stream?hd=${hd}&width=${width}&r=${retry}${token}`;
}