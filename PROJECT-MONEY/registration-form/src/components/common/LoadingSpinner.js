import React from 'react';

export function LoaderMark({ size = 'md', tone = 'default' }) {
  const sizeClass = {
    sm: 'h-5 w-5',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }[size] || 'h-8 w-8';

  const toneClass = tone === 'dark' ? 'border-black/15 bg-black/5' : 'border-yellow-400/20 bg-yellow-400/10';

  return (
    <span className={`loader-mark ${sizeClass} ${toneClass}`} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

export function ButtonLoader({ label = 'Загрузка...', dark = false }) {
  return (
    <span className="inline-flex min-w-0 items-center justify-center gap-2">
      <LoaderMark size="sm" tone={dark ? 'dark' : 'default'} />
      <span className="truncate">{label}</span>
    </span>
  );
}

export function TableLoader({ colSpan = 1, label = 'Загружаем данные...' }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-3 py-10">
        <LoadingSpinner label={label} compact />
      </td>
    </tr>
  );
}

export default function LoadingSpinner({ label = 'Загружаем данные...', fullScreen = false, compact = false }) {
  if (fullScreen) {
    return (
      <div className="min-h-screen bg-[#070707] px-6 text-zinc-100">
        <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center">
          <div className="loader-panel w-full max-w-md border border-yellow-400/15 bg-[#11100d]/95 p-8 text-center shadow-2xl">
            <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center border border-yellow-400/15 bg-black/30">
              <LoaderMark size="lg" />
            </div>
            <div className="text-sm font-semibold uppercase tracking-[0.28em] text-yellow-300">Quantum Trade</div>
            <div className="mt-3 text-lg font-semibold text-white">{label}</div>
            <div className="loader-tape mt-6" aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center justify-center ${compact ? 'py-4' : 'py-10'}`}>
      <div className="loader-inline border border-yellow-400/15 bg-[#11100d] px-5 py-4 shadow-lg">
        <LoaderMark size={compact ? 'md' : 'lg'} />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white">{label}</div>
          <div className="mt-2 h-1.5 w-44 max-w-full overflow-hidden bg-black/40">
            <span className="loader-line block h-full w-1/2 bg-yellow-400" />
          </div>
        </div>
      </div>
    </div>
  );
}
