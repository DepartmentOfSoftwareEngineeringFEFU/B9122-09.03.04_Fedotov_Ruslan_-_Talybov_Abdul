import React, { useEffect, useRef } from 'react';
import { ButtonLoader } from './LoadingSpinner';

const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
}) {
  const dialogRef = useRef(null);
  const previousFocusRef = useRef(null);
  const titleId = 'confirm-dialog-title';
  const descriptionId = 'confirm-dialog-description';

  useEffect(() => {
    if (!open) return undefined;

    previousFocusRef.current = document.activeElement;
    const dialog = dialogRef.current;
    const firstFocusable = dialog?.querySelector(FOCUSABLE_SELECTOR);
    firstFocusable?.focus();

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel?.();
        return;
      }

      if (event.key !== 'Tab' || !dialog) return;

      const focusable = Array.from(dialog.querySelectorAll(FOCUSABLE_SELECTOR))
        .filter((element) => !element.disabled && element.offsetParent !== null);

      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousFocusRef.current?.focus?.();
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" role="presentation">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        className="w-full max-w-md rounded-3xl border border-zinc-800 bg-[#111111] p-6 text-white shadow-2xl"
      >
        <h3 id={titleId} className="text-lg font-semibold tracking-tight text-white">
          {title}
        </h3>
        {description && (
          <p id={descriptionId} className="mt-2 text-sm leading-6 text-zinc-400">
            {description}
          </p>
        )}
        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded-2xl border border-zinc-700 px-4 py-3 text-sm font-semibold text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 rounded-2xl px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${
              danger ? 'bg-red-500 text-white hover:bg-red-400' : 'bg-yellow-400 text-black hover:bg-yellow-300'
            }`}
          >
            {loading ? <ButtonLoader label="Выполняется..." dark={!danger} /> : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
