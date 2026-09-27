/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ─── Brand: refined azure/sky palette ───
        brand: {
          50: '#f0f7ff',
          100: '#e0efff',
          200: '#b9dcff',
          300: '#7cc0ff',
          400: '#36a2ff',
          500: '#0c87f2',   // primary light mode
          600: '#0069cf',   // primary hover
          700: '#0054a7',
          800: '#00458a',
          900: '#053b72',
          950: '#03254c',
        },

        // ─── Semantic ───
        success: {
          50: '#ecfdf5', 100: '#d1fae5', 400: '#34d399',
          500: '#10b981', 600: '#059669', 900: '#064e3b',
        },
        warning: {
          50: '#fffbeb', 100: '#fef3c7', 400: '#fbbf24',
          500: '#f59e0b', 600: '#d97706', 900: '#78350f',
        },
        danger: {
          50: '#fef2f2', 100: '#fee2e2', 400: '#f87171',
          500: '#ef4444', 600: '#dc2626', 900: '#7f1d1d',
        },

        // ─── Dark theme surfaces: deep slate / soft navy ───
        surface: {
          // Light mode
          base: '#ffffff',
          subtle: '#f8fafc',
          muted: '#f1f5f9',
          // Dark mode (deep slate, never pure black)
          'dark-base': '#0f1419',
          'dark-raised': '#161c24',
          'dark-overlay': '#1c242e',
          'dark-hover': '#222b36',
        },

        // ─── Borders ───
        edge: {
          light: '#e2e8f0',
          'light-strong': '#cbd5e1',
          dark: '#232b36',
          'dark-strong': '#2e3846',
        },
      },

      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Menlo', 'monospace'],
      },

      fontSize: {
        // Semantic type scale — no more arbitrary values
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.01em' }],    // 11px labels
        'xs': ['0.75rem', { lineHeight: '1.125rem' }],                             // 12px data
        'sm': ['0.8125rem', { lineHeight: '1.25rem' }],                            // 13px body
        'base': ['0.875rem', { lineHeight: '1.375rem' }],                          // 14px
        'lg': ['1rem', { lineHeight: '1.5rem', letterSpacing: '-0.01em' }],        // 16px
        'xl': ['1.125rem', { lineHeight: '1.75rem', letterSpacing: '-0.015em' }],  // 18px
        '2xl': ['1.375rem', { lineHeight: '1.875rem', letterSpacing: '-0.02em' }], // 22px
        '3xl': ['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.025em' }],  // 28px
      },

      spacing: {
        // 4px base grid
        '4.5': '1.125rem',
        '13': '3.25rem',
        '15': '3.75rem',
        '18': '4.5rem',
      },

      borderRadius: {
        'sm': '0.25rem',
        DEFAULT: '0.375rem',
        'md': '0.5rem',
        'lg': '0.625rem',
        'xl': '0.75rem',
      },

      boxShadow: {
        'xs': '0 1px 2px 0 rgb(15 23 42 / 0.04)',
        'sm': '0 1px 3px 0 rgb(15 23 42 / 0.08), 0 1px 2px -1px rgb(15 23 42 / 0.06)',
        'md': '0 4px 12px -2px rgb(15 23 42 / 0.08), 0 2px 4px -2px rgb(15 23 42 / 0.04)',
        'lg': '0 12px 24px -4px rgb(15 23 42 / 0.10), 0 4px 8px -4px rgb(15 23 42 / 0.06)',
        // Dark mode
        'dark-sm': '0 1px 3px 0 rgb(0 0 0 / 0.4)',
        'dark-md': '0 4px 12px -2px rgb(0 0 0 / 0.5)',
        'dark-lg': '0 12px 24px -4px rgb(0 0 0 / 0.6)',
        // Focus ring
        'focus': '0 0 0 3px rgb(12 135 242 / 0.15)',
      },

      transitionDuration: {
        '150': '150ms',
        '200': '200ms',
      },

      animation: {
        'fade-in': 'fadeIn 150ms ease-out',
        'slide-down': 'slideDown 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        'shimmer': 'shimmer 1.8s ease-in-out infinite',
        'pulse-dot': 'pulseDot 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },

      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.7' },
        },
        pulseDot: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [],
}
