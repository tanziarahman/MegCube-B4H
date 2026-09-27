import Link from 'next/link';
import { PATHS } from '@/lib/paths';

// Static values for now; wire to real data later (devices online, live connection, data source).
export default function StatusIndicators() {
  const usingDemoData = true;
  const devices = { online: 20, total: 24 };
  const live = true;

  return (
    <div className="flex items-center gap-3 text-[12.5px]">
      {usingDemoData && (
        <span className="rounded-full bg-warn-bg px-2.5 py-0.5 font-medium text-warn">Demo data</span>
      )}
      <Link
        href={PATHS.devices}
        className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-ink hover:bg-ground"
      >
        <span className={`h-2 w-2 rounded-full ${devices.online === devices.total ? 'bg-ok' : 'bg-warn'}`} />
        Devices {devices.online} / {devices.total}
      </Link>
      <span className={`flex items-center gap-1.5 ${live ? 'text-ok' : 'text-mute'}`}>
        <span className={`h-2 w-2 rounded-full ${live ? 'bg-ok' : 'bg-mute'}`} />
        {live ? 'Live' : 'Offline'}
      </span>
    </div>
  );
}
