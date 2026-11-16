/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 950: '#08090b', 900: '#0d0f12', 800: '#13161b', 700: '#1b1f26', 600: '#262b34', 500: '#3a414d' },
        bone: { 100: '#f2efe8', 300: '#c9c5ba', 500: '#8d8a82', 700: '#5c5a55' },
        lab: '#f5b84a', // signal amber — the one brand accent
        persona: {
          doom: '#ff6b57',    // Doomscroller
          critic: '#a78bfa',  // Skeptical Critic
          fan: '#4ade80',     // Genre Superfan
          newbie: '#5eb8ff',  // Casual Newcomer
        },
      },
      fontFamily: {
        display: ['Georgia', 'Times New Roman', 'serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      keyframes: {
        rise: { from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'none' } },
        scan: { '0%': { transform: 'translateX(-10%)' }, '100%': { transform: 'translateX(110%)' } },
        blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.25 } },
      },
      animation: {
        rise: 'rise .6s cubic-bezier(.2,.7,.2,1) both',
        scan: 'scan 3.2s linear infinite',
        blink: 'blink 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
