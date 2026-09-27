/**
 * Icon system — consistent 16px stroke icons.
 * Replaces emojis which render inconsistently across platforms.
 */

interface IconProps {
  size?: number
  className?: string
}

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
})

export const Icons = {
  Dashboard: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  ),

  Search: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  ),

  Flame: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M12 2c1 4 4 5 4 9a4 4 0 0 1-8 0c0-1.5.5-2.5 1-3.5C8 9 6 11 6 14a6 6 0 0 0 12 0c0-5-4-8-6-12Z" />
    </svg>
  ),

  Radar: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
      <path d="M12 3v4M21 12h-4" />
    </svg>
  ),

  Book: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M4 5a2 2 0 0 1 2-2h12a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V5Z" />
      <path d="M4 17h15M9 3v14" />
    </svg>
  ),

  Star: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="m12 3 2.6 5.6 6.1.8-4.4 4.3 1 6.1L12 17l-5.3 2.8 1-6.1L3.3 9.4l6.1-.8L12 3Z" />
    </svg>
  ),

  Bell: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  ),

  Chart: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M3 3v18h18" />
      <path d="m7 15 4-5 3 3 5-7" />
    </svg>
  ),

  Settings: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a2 2 0 0 1-4 0v-.1A1.7 1.7 0 0 0 8 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H2a2 2 0 0 1 0-4h.2A1.7 1.7 0 0 0 3.7 8a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H8a1.7 1.7 0 0 0 1-1.5V2a2 2 0 0 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V8a1.7 1.7 0 0 0 1.5 1H22a2 2 0 0 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  ),

  Filter: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M3 5h18M6 12h12M10 19h4" />
    </svg>
  ),

  Refresh: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </svg>
  ),

  ChevronDown: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  ),

  ChevronRight: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  ),

  ChevronsLeft: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="m11 17-5-5 5-5M18 17l-5-5 5-5" />
    </svg>
  ),

  ArrowUp: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  ),

  ArrowDown: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M12 5v14M19 12l-7 7-7-7" />
    </svg>
  ),

  ExternalLink: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </svg>
  ),

  Check: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  ),

  X: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  ),

  Plus: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),

  Sun: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),

  Moon: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  ),

  Warning: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  ),

  Info: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  ),

  Zap: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
    </svg>
  ),

  Wallet: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5" />
      <path d="M17 12h.01" />
    </svg>
  ),

  Clipboard: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <rect x="8" y="2" width="8" height="4" rx="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    </svg>
  ),

  Bulb: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M9 18h6M10 22h4M12 2a6 6 0 0 0-3 11c.5.5 1 1.5 1 2.5h4c0-1 .5-2 1-2.5A6 6 0 0 0 12 2Z" />
    </svg>
  ),

  Inbox: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z" />
    </svg>
  ),

  /** Drag handle — filled dots read as "grabbable" better than strokes. */
  Grip: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className} fill="currentColor" stroke="none">
      <circle cx="9" cy="6" r="1.4" />
      <circle cx="15" cy="6" r="1.4" />
      <circle cx="9" cy="12" r="1.4" />
      <circle cx="15" cy="12" r="1.4" />
      <circle cx="9" cy="18" r="1.4" />
      <circle cx="15" cy="18" r="1.4" />
    </svg>
  ),

  Pencil: ({ size = 16, className }: IconProps) => (
    <svg {...base(size)} className={className}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  ),
}

export type IconName = keyof typeof Icons
