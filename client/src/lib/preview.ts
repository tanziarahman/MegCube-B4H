// Live preview: camera list + MJPEG stream URLs from the FastAPI backend.

export interface PreviewCamera {
  id: number;
  name: string;
  online: boolean;
  task: string | null;   // analysis task on this camera, if any
}

// Video goes straight to the backend (not through the Next.js /api proxy) so frames aren't buffered.
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

export async function fetchPreviewCameras(): Promise<PreviewCamera[]> {
  const res = await fetch('/api/preview/cameras', { cache: 'no-store' });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Request failed (${res.status})`);
  return res.json();
}

/** `retry` changes the URL so the browser opens a fresh stream. */
export function streamUrl(cameraId: number, retry = 0, width = 960): string {
  return `${BACKEND}/api/preview/${cameraId}/stream?width=${width}&r=${retry}`;
}
