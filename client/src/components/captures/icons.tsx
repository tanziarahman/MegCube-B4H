// Minimal inline icon set (no extra dependency). Each takes a className.
type IconProps = { className?: string };

export const IconGrid = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className={className}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

export const IconList = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className={className}>
    <line x1="4" y1="6" x2="20" y2="6" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <line x1="4" y1="18" x2="20" y2="18" />
  </svg>
);

export const IconChevronLeft = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

export const IconChevronRight = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

export const IconClose = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export const IconFace = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className={className}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="9" cy="10" r="0.75" fill="currentColor" stroke="none" />
    <circle cx="15" cy="10" r="0.75" fill="currentColor" stroke="none" />
    <path d="M8.5 14.5c1 1 2.2 1.5 3.5 1.5s2.5-.5 3.5-1.5" strokeLinecap="round" />
  </svg>
);

export const IconBody = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className={className}>
    <circle cx="12" cy="6" r="3" />
    <path d="M6 21v-4a6 6 0 0 1 12 0v4" strokeLinecap="round" />
  </svg>
);

export const IconRefresh = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className={className}>
    <path d="M20 11A8 8 0 1 0 19 16" strokeLinecap="round" />
    <polyline points="20 4 20 11 13 11" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const IconImageOff = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <line x1="3" y1="21" x2="21" y2="3" />
  </svg>
);

export const IconCamera = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className={className}>
    <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
    <circle cx="12" cy="13" r="3.5" />
  </svg>
);