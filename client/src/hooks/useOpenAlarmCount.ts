'use client';

import { useEffect, useState } from 'react';
import { fetchAlarmStatus } from '@/lib/alarms';

const REFRESH_MS = 60_000;

/** Open alarms, for the sidebar badge. 0 while loading, without a database, or when the backend is down. */
export function useOpenAlarmCount(): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = () => fetchAlarmStatus()
      .then((s) => { if (alive) setCount(s.openIncidents); })
      .catch(() => { if (alive) setCount(0); });
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return count;
}
