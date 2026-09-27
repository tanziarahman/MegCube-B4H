/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#15191E',
        mute: '#58616C',
        line: '#DCE0E5',
        ground: '#F3F4F6',
        nav: { DEFAULT: '#0F1621', text: '#B9C3CF', hover: '#1A2330', active: '#223453', head: '#7D8896' },
        pri: { DEFAULT: '#1F4FB5', bg: '#E8EEFA' },
        crit: { DEFAULT: '#B42318', bg: '#FDECEA' },
        warn: { DEFAULT: '#8A5300', bg: '#FFF4DB' },
        ok: { DEFAULT: '#16723A', bg: '#E6F4EC' },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
