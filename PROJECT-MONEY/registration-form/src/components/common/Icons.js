import React from 'react';

const paths = {
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'M6 18L18 6M6 6l12 12',
  trading: 'M3 17l6-6 4 4 8-8M14 7h7v7',
  portfolio: 'M3 7h18v12H3V7zm3-4h12v4H6V3zm0 8h6m-6 4h10',
  market: 'M4 19V5m0 14h16M7 16l3-5 3 3 4-8 3 4',
  models: 'M12 3v3m0 12v3M3 12h3m12 0h3M7.8 7.8l2.1 2.1m4.2 4.2l2.1 2.1m0-8.4l-2.1 2.1m-4.2 4.2l-2.1 2.1M9 12a3 3 0 106 0 3 3 0 00-6 0z',
  analytics: 'M5 19V9m7 10V5m7 14v-7',
  settings: 'M12 8a4 4 0 100 8 4 4 0 000-8zm8.5 4a8.5 8.5 0 01-.2 1.8l2 1.5-2 3.4-2.4-1a8.8 8.8 0 01-3.1 1.8l-.3 2.5h-4l-.3-2.5a8.8 8.8 0 01-3.1-1.8l-2.4 1-2-3.4 2-1.5A8.5 8.5 0 014.5 12c0-.6.1-1.2.2-1.8l-2-1.5 2-3.4 2.4 1a8.8 8.8 0 013.1-1.8L10.5 2h4l.3 2.5a8.8 8.8 0 013.1 1.8l2.4-1 2 3.4-2 1.5c.1.6.2 1.2.2 1.8z',
  logout: 'M15 17l5-5-5-5M20 12H9m4 7H5a2 2 0 01-2-2V7a2 2 0 012-2h8',
  user: 'M20 21a8 8 0 10-16 0m8-10a4 4 0 100-8 4 4 0 000 8z',
  lock: 'M7 10V7a5 5 0 0110 0v3M6 10h12v11H6V10z',
  eye: 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12zm10-3a3 3 0 100 6 3 3 0 000-6z',
  eyeOff: 'M3 3l18 18M10.6 5.1A9.9 9.9 0 0112 5c7 0 10 7 10 7a12.6 12.6 0 01-2 2.9M6.1 6.1C3.3 8 2 12 2 12s3 7 10 7a9.8 9.8 0 005.9-2M9.9 9.9a3 3 0 104.2 4.2',
  mail: 'M4 6h16v12H4V6zm0 0l8 7 8-7',
  key: 'M15 7a4 4 0 11-3.2 6.4L8 17H5v3H2v-3.6l5.6-5.6A4 4 0 0115 7z',
  alert: 'M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  check: 'M5 13l4 4L19 7',
  chevronLeft: 'M15 19l-7-7 7-7',
  chevronRight: 'M9 5l7 7-7 7',
  sidebarOpen: 'M4 5h16v14H4V5zm6 0v14m4-9l3 2-3 2',
  sidebarClose: 'M4 5h16v14H4V5zm6 0v14m7-9l-3 2 3 2',
  refresh: 'M20 6v6h-6M4 18v-6h6M5 9a7 7 0 0111.7-3M19 15A7 7 0 017.3 18',
};

export default function Icon({ name, className = 'w-5 h-5', strokeWidth = 1.8 }) {
  const path = paths[name] || paths.analytics;

  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}
