'use client';

import { useLocalStorage } from '@/hooks/useLocalStorage';

const LANGS = [
  { code: 'en', label: 'EN' },
  { code: 'zh', label: '中' },
] as const;

export default function LanguageSwitch() {
  const [lang, setLang] = useLocalStorage<string>('lang', 'en');
  return (
    <div className="flex items-center text-[12.5px]" role="group" aria-label="Language">
      {LANGS.map((l, i) => (
        <span key={l.code} className="flex items-center">
          {i > 0 && <span className="px-1 text-line">|</span>}
          <button
            type="button"
            onClick={() => setLang(l.code)}
            aria-pressed={lang === l.code}
            className={lang === l.code ? 'font-semibold text-ink' : 'text-mute hover:text-ink'}
          >
            {l.label}
          </button>
        </span>
      ))}
    </div>
  );
}
