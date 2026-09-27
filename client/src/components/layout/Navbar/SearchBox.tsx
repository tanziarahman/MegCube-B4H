'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { PATHS } from '@/lib/paths';

export default function SearchBox() {
  const [query, setQuery] = useState('');
  const router = useRouter();

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    // Simple rule for now: searches go to People. Adjust when search is implemented.
    router.push(`${PATHS.people}?search=${encodeURIComponent(query.trim())}`);
  };

  return (
    <form onSubmit={onSubmit} role="search" className="relative w-full max-w-sm">
      <Search size={16} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-mute" />
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search person, camera, track ID…"
        aria-label="Search"
        className="h-9 w-full rounded-md border border-line bg-white pl-8 pr-3 text-[13px] outline-none placeholder:text-mute focus:border-pri"
      />
    </form>
  );
}
