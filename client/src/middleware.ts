// Adds the backend API key to every /api request before next.config's rewrite forwards it to FastAPI.
// The key lives only on the Next.js server (BACKEND_API_KEY in .env.local, no NEXT_PUBLIC_ prefix),
// so browsers never see it. Live video <img> tags go straight to the backend with a signed link instead.
import { NextResponse, type NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const key = process.env.BACKEND_API_KEY;
  if (!key) return NextResponse.next();
  const headers = new Headers(request.headers);
  headers.set('x-api-key', key);
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: '/api/:path*' };
