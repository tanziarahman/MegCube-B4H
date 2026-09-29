// Single source of truth for URLs. Import these instead of typing strings.
export const PATHS = {
  login: '/login',
  dashboard: '/',
  live: '/live',
  alarms: '/alarms',
  alarmDetail: (id: string) => `/alarms/${id}`,
  recognition: '/recognition',
  recognitionDetail: (id: string) => `/recognition/${id}`,
  captures: '/captures',
  counting: '/counting',
  people: '/people',
  devices: '/devices',
  timeplans: '/timeplans',
  settings: '/settings',
} as const;
