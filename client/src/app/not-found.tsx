import Link from 'next/link';
import { PATHS } from '@/lib/paths';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link href={PATHS.dashboard} className="text-sm text-pri hover:underline">Back to Dashboard</Link>
    </div>
  );
}
