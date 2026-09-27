'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { APP_NAME } from '@/config/navigation';
import { PATHS } from '@/lib/paths';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    // Demo login: replace with a real API call later.
    if (username && password === 'admin') router.push(PATHS.dashboard);
    else setError(true);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-ground p-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-line bg-white p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-pri text-sm font-bold text-white">B4</span>
          <span className="font-semibold">{APP_NAME}</span>
        </div>
        <h1 className="text-xl font-semibold">Sign in</h1>
        {error && (
          <p role="alert" className="rounded-md bg-crit-bg px-3 py-2 text-[13px] text-crit">
            Incorrect username or password.
          </p>
        )}
        <label className="block text-[12px] font-medium text-mute">
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
            className="mt-1 h-9 w-full rounded-md border border-line px-3 text-[13px] text-ink outline-none focus:border-pri" />
        </label>
        <label className="block text-[12px] font-medium text-mute">
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
            className="mt-1 h-9 w-full rounded-md border border-line px-3 text-[13px] text-ink outline-none focus:border-pri" />
        </label>
        <button type="submit" className="h-9 w-full rounded-md bg-pri text-[13px] font-medium text-white hover:bg-[#1A43A0]">
          Sign in
        </button>
        <p className="text-[11.5px] text-mute">Demo: any username, password “admin”.</p>
      </form>
    </div>
  );
}
