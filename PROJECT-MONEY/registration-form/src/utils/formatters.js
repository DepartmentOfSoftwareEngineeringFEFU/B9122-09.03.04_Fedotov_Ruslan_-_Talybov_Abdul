export const formatMoney = (value, options = {}) => {
  const { minimumFractionDigits = 2, maximumFractionDigits = 2 } = options;
  return Number(value || 0).toLocaleString('ru-RU', {
    minimumFractionDigits,
    maximumFractionDigits,
  });
};

export const formatPercent = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`;

export const formatShortId = (value, length = 8) => {
  if (!value) return '—';
  const raw = String(value);
  return raw.length > length ? `${raw.slice(0, length)}...` : raw;
};
