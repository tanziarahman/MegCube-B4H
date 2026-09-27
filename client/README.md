# B4H Portal (Next.js)

Next.js 15 (App Router) + TypeScript + Tailwind.

## Run
```bash
npm install
cp .env.example .env.local   # set BACKEND_URL to your FastAPI address
npm run dev                  # http://localhost:3000
```
Requests to `/api/*` are forwarded to FastAPI (`BACKEND_URL`, default http://localhost:8000), so no CORS setup is needed.
Demo login: any username, password `admin`.

## Structure
```
src/
├─ app/
│  ├─ layout.tsx                 # root HTML, fonts, global CSS
│  ├─ globals.css
│  ├─ not-found.tsx
│  ├─ login/page.tsx             # no sidebar/navbar
│  └─ (portal)/                  # route group: everything here gets the app shell
│     ├─ layout.tsx              # wraps pages in <AppShell>
│     ├─ page.tsx                # /            Dashboard
│     ├─ live/page.tsx           # /live
│     ├─ alarms/page.tsx         # /alarms
│     ├─ alarms/[id]/page.tsx    # /alarms/:id
│     ├─ recognition/…           # /recognition, /recognition/:id
│     └─ captures/ counting/ people/ devices/ settings/
├─ components/
│  ├─ layout/
│  │  ├─ AppShell.tsx            # sidebar + navbar + content (collapse state)
│  │  ├─ Sidebar/                # Sidebar, SidebarBrand, SidebarSection, SidebarItem
│  │  └─ Navbar/                 # Navbar, SearchBox, StatusIndicators, LanguageSwitch, UserMenu
│  └─ common/                    # PageHeader, Placeholder (shared UI)
├─ config/navigation.ts          # sidebar sections & links
├─ lib/paths.ts                  # all URLs in one place
└─ hooks/useLocalStorage.ts
```

## Adding a page
1. Create `src/app/(portal)/foo/page.tsx` (the folder name is the URL).
2. Add `foo: '/foo'` to `lib/paths.ts`.
3. Add a link in `config/navigation.ts` if it should appear in the sidebar.

Components that use state, effects or browser APIs start with `'use client'`. Pages stay server components unless they need interactivity.
