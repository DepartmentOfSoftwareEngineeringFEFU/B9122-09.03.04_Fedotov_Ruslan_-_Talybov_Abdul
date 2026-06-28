export function clampNumber(value, { min = 0, max = Number.MAX_SAFE_INTEGER, integer = false } = {}) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  const clamped = Math.min(max, Math.max(min, number));
  return integer ? Math.floor(clamped) : clamped;
}

export function sanitizeNumberInput(value, {
  min = 0,
  max = Number.MAX_SAFE_INTEGER,
  integer = false,
  maxLength = 12,
} = {}) {
  const source = String(value ?? '').slice(0, maxLength);
  const normalized = integer
    ? source.replace(/[^\d]/g, '')
    : source.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1');

  if (normalized === '') return '';

  const number = Number(normalized);
  if (!Number.isFinite(number)) return '';

  const clamped = Math.min(max, Math.max(min, number));
  return String(integer ? Math.floor(clamped) : clamped);
}
