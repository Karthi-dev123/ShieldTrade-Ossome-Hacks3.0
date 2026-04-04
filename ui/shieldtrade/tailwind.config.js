/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', 'ui-monospace', 'monospace'],
      },
      colors: {
        bg:          '#141414',
        surface:     'rgba(255,255,255,0.03)',
        card:        'rgba(255,255,255,0.05)',
        card2:       'rgba(255,255,255,0.08)',
        border:      'rgba(255,255,255,0.08)',
        border2:     'rgba(255,255,255,0.14)',
        'brand-lime':  '#E2FF3B',
        'chart-yellow':'#F5C842',
        'glass-border':'rgba(255,255,255,0.08)',
      },
      backdropBlur: {
        xs: '4px',
        DEFAULT: '12px',
        xl: '20px',
        '2xl': '32px',
        '3xl': '48px',
      },
      boxShadow: {
        glass:      '0 4px 32px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)',
        'glass-lg': '0 8px 48px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.08)',
        'glow-green': '0 0 24px rgba(16,185,129,0.25)',
        'glow-blue':  '0 0 24px rgba(96,165,250,0.20)',
        'glow-lime':  '0 0 24px rgba(226,255,59,0.30), 0 0 48px rgba(226,255,59,0.12)',
        'soft-glow':  '0 0 20px rgba(226,255,59,0.22)',
      },
    },
  },
  plugins: [],
}

