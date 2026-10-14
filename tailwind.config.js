/** @type {import('tailwindcss').Config} */
// Ukuran dasar html = 13px (static/css/tailwind-source.css), jadi rem di bawah dihitung dari 13px.
// Ukuran huruf dinaikkan supaya teks setara 12 / 14 / 15px (keterbacaan), jarak & tata letak tetap.
// Abu slate-400/500 digelapkan satu tingkat: teks keterangan di latar putih lebih kontras.
const colors = require('tailwindcss/colors')

module.exports = {
  content: ["./templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        xs: ['0.9231rem', { lineHeight: '1.35' }],    // 12px
        sm: ['1.0769rem', { lineHeight: '1.45' }],    // 14px
        base: ['1.1538rem', { lineHeight: '1.5' }],   // 15px
        lg: ['1.3077rem', { lineHeight: '1.45' }],    // 17px
        xl: ['1.4615rem', { lineHeight: '1.35' }],    // 19px
      },
      colors: {
        slate: { ...colors.slate, 400: '#64748b', 500: '#475569' },
      },
    },
  },
  plugins: [],
}
