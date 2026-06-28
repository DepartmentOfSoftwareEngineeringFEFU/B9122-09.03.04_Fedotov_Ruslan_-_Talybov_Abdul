import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const PRICE_COLORS = {
  up: '#16c784',
  down: '#ea3943',
  accent: '#facc15',
  grid: 'rgba(250, 204, 21, 0.10)',
  gridStrong: 'rgba(250, 204, 21, 0.18)',
  text: '#a1a1aa',
  textStrong: '#f4f4f5',
  panel: '#0b0a08',
};

const MIN_VISIBLE_SPAN = 8;
const DEFAULT_VISIBLE_CANDLES = 96;

const layout = (width, height) => ({
  left: 14,
  right: 76,
  top: 16,
  priceHeight: Math.max(240, Math.floor(height * 0.72)),
  volumeGap: 14,
  bottom: 28,
  get plotWidth() {
    return Math.max(260, width - this.left - this.right);
  },
  get volumeTop() {
    return this.top + this.priceHeight + this.volumeGap;
  },
  get volumeHeight() {
    return Math.max(70, height - this.volumeTop - this.bottom);
  },
});

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const getNumber = (value, fallback = 0) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const formatPrice = (value) => {
  if (!Number.isFinite(value)) return '—';
  return `${value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
};

const formatVolume = (value) => {
  if (!Number.isFinite(value)) return '—';
  if (value >= 1_000_000) return `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}M`;
  if (value >= 1_000) return `${(value / 1_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}K`;
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
};

const formatTimeLabel = (timestamp) => {
  if (!timestamp) return '';
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
};

const formatFullDate = (timestamp) => {
  if (!timestamp) return '';
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const getInitialView = (length) => {
  if (length <= 1) return { start: 0, end: Math.max(0, length - 1) };
  const span = Math.min(length - 1, DEFAULT_VISIBLE_CANDLES);
  return { start: Math.max(0, length - 1 - span), end: length - 1 };
};

const normalizeView = (view, length) => {
  if (length <= 1) return { start: 0, end: 0 };

  const maxSpan = Math.max(MIN_VISIBLE_SPAN, length - 1);
  const minSpan = Math.min(MIN_VISIBLE_SPAN, maxSpan);
  const span = clamp(view.end - view.start, minSpan, maxSpan);
  const maxStart = Math.max(0, length - 1 - span);
  const start = clamp(view.start, 0, maxStart);

  return { start, end: start + span };
};

const getVisibleData = (data, view) => {
  const startIndex = Math.max(0, Math.floor(view.start) - 2);
  const endIndex = Math.min(data.length - 1, Math.ceil(view.end) + 2);
  return data.slice(startIndex, endIndex + 1).map((item, offset) => ({
    ...item,
    __index: startIndex + offset,
  }));
};

const getMousePosition = (event, element) => {
  const rect = element.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
};

const drawRoundedLabel = (ctx, x, y, text, fill, textColor = '#111111') => {
  const paddingX = 7;
  const width = ctx.measureText(text).width + paddingX * 2;
  const height = 21;
  const radius = 4;
  const labelX = x;
  const labelY = y - height / 2;

  ctx.beginPath();
  ctx.moveTo(labelX + radius, labelY);
  ctx.lineTo(labelX + width - radius, labelY);
  ctx.quadraticCurveTo(labelX + width, labelY, labelX + width, labelY + radius);
  ctx.lineTo(labelX + width, labelY + height - radius);
  ctx.quadraticCurveTo(labelX + width, labelY + height, labelX + width - radius, labelY + height);
  ctx.lineTo(labelX + radius, labelY + height);
  ctx.quadraticCurveTo(labelX, labelY + height, labelX, labelY + height - radius);
  ctx.lineTo(labelX, labelY + radius);
  ctx.quadraticCurveTo(labelX, labelY, labelX + radius, labelY);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();

  ctx.fillStyle = textColor;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '600 11px Inter, system-ui, sans-serif';
  ctx.fillText(text, labelX + width / 2, y + 0.5);
};

const drawChart = ({ canvas, data, view, chartType, hoverIndex }) => {
  const ctx = canvas.getContext('2d');
  if (!ctx) return false;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const ratio = window.devicePixelRatio || 1;

  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }

  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = PRICE_COLORS.panel;
  ctx.fillRect(0, 0, width, height);

  if (!data.length) return true;

  const l = layout(width, height);
  const visible = getVisibleData(data, view);
  const priceValues = visible.flatMap((item) => [getNumber(item.high), getNumber(item.low)]);
  const minPriceRaw = Math.min(...priceValues);
  const maxPriceRaw = Math.max(...priceValues);
  const priceRange = Math.max(maxPriceRaw - minPriceRaw, 0.01);
  const minPrice = minPriceRaw - priceRange * 0.08;
  const maxPrice = maxPriceRaw + priceRange * 0.08;
  const volumeMax = Math.max(...visible.map((item) => getNumber(item.volume)), 1);
  const span = Math.max(view.end - view.start, 1);
  const candleWidth = clamp((l.plotWidth / span) * 0.68, 2, 14);

  const xForIndex = (index) => l.left + ((index - view.start) / span) * l.plotWidth;
  const yForPrice = (price) => l.top + ((maxPrice - price) / (maxPrice - minPrice)) * l.priceHeight;
  const yForVolume = (volume) => l.volumeTop + l.volumeHeight - (volume / volumeMax) * l.volumeHeight;

  ctx.save();

  // Grid + price scale.
  ctx.strokeStyle = PRICE_COLORS.grid;
  ctx.lineWidth = 1;
  ctx.font = '11px Inter, system-ui, sans-serif';
  ctx.fillStyle = PRICE_COLORS.text;
  ctx.textBaseline = 'middle';

  const horizontalLines = 5;
  for (let i = 0; i <= horizontalLines; i += 1) {
    const y = l.top + (l.priceHeight / horizontalLines) * i;
    const price = maxPrice - ((maxPrice - minPrice) / horizontalLines) * i;
    ctx.beginPath();
    ctx.moveTo(l.left, y);
    ctx.lineTo(l.left + l.plotWidth, y);
    ctx.stroke();
    ctx.textAlign = 'left';
    ctx.fillText(price.toLocaleString('ru-RU', { maximumFractionDigits: 2 }), l.left + l.plotWidth + 9, y);
  }

  // Vertical grid + bottom time scale.
  const verticalLines = Math.min(8, Math.max(3, Math.floor(l.plotWidth / 140)));
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let i = 0; i <= verticalLines; i += 1) {
    const index = Math.round(view.start + (span / verticalLines) * i);
    const x = xForIndex(index);
    const point = data[clamp(index, 0, data.length - 1)];
    ctx.beginPath();
    ctx.moveTo(x, l.top);
    ctx.lineTo(x, l.volumeTop + l.volumeHeight);
    ctx.stroke();
    ctx.fillText(formatTimeLabel(point?.timestamp), x, l.volumeTop + l.volumeHeight + 8);
  }

  // Price/volume separator.
  ctx.strokeStyle = PRICE_COLORS.gridStrong;
  ctx.beginPath();
  ctx.moveTo(l.left, l.volumeTop - l.volumeGap / 2);
  ctx.lineTo(l.left + l.plotWidth, l.volumeTop - l.volumeGap / 2);
  ctx.stroke();

  // Volume.
  visible.forEach((item) => {
    const x = xForIndex(item.__index);
    const open = getNumber(item.open);
    const close = getNumber(item.close);
    const color = close >= open ? PRICE_COLORS.up : PRICE_COLORS.down;
    const volY = yForVolume(getNumber(item.volume));

    ctx.globalAlpha = 0.26;
    ctx.fillStyle = color;
    ctx.fillRect(x - candleWidth / 2, volY, candleWidth, l.volumeTop + l.volumeHeight - volY);
    ctx.globalAlpha = 1;
  });

  // Price series.
  if (chartType === 'line' || chartType === 'area') {
    ctx.beginPath();
    visible.forEach((item, i) => {
      const x = xForIndex(item.__index);
      const y = yForPrice(getNumber(item.close));
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    if (chartType === 'area') {
      const last = visible[visible.length - 1];
      const first = visible[0];
      const gradient = ctx.createLinearGradient(0, l.top, 0, l.top + l.priceHeight);
      gradient.addColorStop(0, 'rgba(250, 204, 21, 0.28)');
      gradient.addColorStop(1, 'rgba(250, 204, 21, 0.02)');

      ctx.lineTo(xForIndex(last.__index), l.top + l.priceHeight);
      ctx.lineTo(xForIndex(first.__index), l.top + l.priceHeight);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.beginPath();
      visible.forEach((item, i) => {
        const x = xForIndex(item.__index);
        const y = yForPrice(getNumber(item.close));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
    }

    ctx.strokeStyle = PRICE_COLORS.accent;
    ctx.lineWidth = 2;
    ctx.stroke();
  } else {
    visible.forEach((item) => {
      const x = xForIndex(item.__index);
      const open = getNumber(item.open);
      const high = getNumber(item.high);
      const low = getNumber(item.low);
      const close = getNumber(item.close);
      const color = close >= open ? PRICE_COLORS.up : PRICE_COLORS.down;
      const yOpen = yForPrice(open);
      const yClose = yForPrice(close);
      const yHigh = yForPrice(high);
      const yLow = yForPrice(low);
      const bodyTop = Math.min(yOpen, yClose);
      const bodyHeight = Math.max(Math.abs(yClose - yOpen), 1.2);

      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(x, yHigh);
      ctx.lineTo(x, yLow);
      ctx.stroke();
      ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    });
  }

  // Current price line.
  const last = data[data.length - 1];
  const currentPrice = getNumber(last?.close);
  const currentY = yForPrice(currentPrice);
  const currentColor = getNumber(last?.close) >= getNumber(last?.open) ? PRICE_COLORS.up : PRICE_COLORS.down;

  ctx.setLineDash([5, 5]);
  ctx.strokeStyle = currentColor;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(l.left, currentY);
  ctx.lineTo(l.left + l.plotWidth, currentY);
  ctx.stroke();
  ctx.setLineDash([]);
  drawRoundedLabel(ctx, l.left + l.plotWidth + 6, clamp(currentY, l.top + 12, l.top + l.priceHeight - 12), currentPrice.toLocaleString('ru-RU', { maximumFractionDigits: 2 }), currentColor);

  // Hover crosshair.
  if (Number.isInteger(hoverIndex) && hoverIndex >= 0 && hoverIndex < data.length) {
    const hover = data[hoverIndex];
    const x = xForIndex(hoverIndex);
    const y = yForPrice(getNumber(hover.close));

    if (x >= l.left && x <= l.left + l.plotWidth) {
      ctx.strokeStyle = 'rgba(244, 244, 245, 0.36)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(x, l.top);
      ctx.lineTo(x, l.volumeTop + l.volumeHeight);
      ctx.moveTo(l.left, y);
      ctx.lineTo(l.left + l.plotWidth, y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = PRICE_COLORS.textStrong;
      ctx.beginPath();
      ctx.arc(x, y, 3.2, 0, Math.PI * 2);
      ctx.fill();

      drawRoundedLabel(ctx, l.left + l.plotWidth + 6, clamp(y, l.top + 12, l.top + l.priceHeight - 12), getNumber(hover.close).toLocaleString('ru-RU', { maximumFractionDigits: 2 }), '#f4f4f5', '#111111');
    }
  }

  ctx.restore();
  return true;
};

const buildSvgFallback = (data, view, chartType) => {
  if (!data.length) return null;

  const width = 1000;
  const height = 520;
  const l = layout(width, height);
  const safeView = normalizeView(view, data.length);
  const visible = getVisibleData(data, safeView);
  const priceValues = visible.flatMap((item) => [getNumber(item.high), getNumber(item.low)]);
  const minPriceRaw = Math.min(...priceValues);
  const maxPriceRaw = Math.max(...priceValues);
  const priceRange = Math.max(maxPriceRaw - minPriceRaw, 0.01);
  const minPrice = minPriceRaw - priceRange * 0.08;
  const maxPrice = maxPriceRaw + priceRange * 0.08;
  const span = Math.max(safeView.end - safeView.start, 1);
  const candleWidth = clamp((l.plotWidth / span) * 0.68, 3, 16);

  const xForIndex = (index) => l.left + ((index - safeView.start) / span) * l.plotWidth;
  const yForPrice = (price) => l.top + ((maxPrice - price) / (maxPrice - minPrice)) * l.priceHeight;
  const closePoints = visible
    .map((item) => `${xForIndex(item.__index).toFixed(1)},${yForPrice(getNumber(item.close)).toFixed(1)}`)
    .join(' ');
  const areaPoints = visible.length
    ? `${closePoints} ${xForIndex(visible[visible.length - 1].__index).toFixed(1)},${(l.top + l.priceHeight).toFixed(1)} ${xForIndex(visible[0].__index).toFixed(1)},${(l.top + l.priceHeight).toFixed(1)}`
    : '';

  return {
    width,
    height,
    layout: l,
    visible,
    candleWidth,
    xForIndex,
    yForPrice,
    closePoints,
    areaPoints,
    horizontalLines: Array.from({ length: 6 }, (_item, index) => ({
      y: l.top + (l.priceHeight / 5) * index,
    })),
  };
};

export default function InteractiveMarketChart({ data = [], chartType = 'candlestick', symbol = '' }) {
  const canvasRef = useRef(null);
  const wrapperRef = useRef(null);
  const pointersRef = useRef(new Map());
  const dragRef = useRef({ active: false, lastX: 0, moved: false });
  const pinchRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 520 });
  const [view, setView] = useState(() => getInitialView(data.length));
  const [hover, setHover] = useState(null);
  const [useSvgFallback, setUseSvgFallback] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const hasData = data.length > 0;
  const latest = data[data.length - 1];
  const firstVisible = data[Math.max(0, Math.floor(view.start))];
  const visibleChange = useMemo(() => {
    if (!firstVisible || !latest) return 0;
    const from = getNumber(firstVisible.close);
    const to = getNumber(latest.close);
    return from ? ((to - from) / from) * 100 : 0;
  }, [firstVisible, latest]);
  const svgFallback = useMemo(() => buildSvgFallback(data, view, chartType), [chartType, data, view]);

  useEffect(() => {
    setView(getInitialView(data.length));
    setHover(null);
  }, [data.length]);

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) return undefined;

    const updateSize = () => {
      const rect = element.getBoundingClientRect();
      setSize({ width: Math.floor(rect.width), height: 520 });
    };

    updateSize();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize);
      return () => window.removeEventListener('resize', updateSize);
    }

    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, [data.length]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !size.width) return;

    const rendered = drawChart({
      canvas,
      data,
      view: normalizeView(view, data.length),
      chartType,
      hoverIndex: hover?.index,
    });

    setUseSvgFallback((current) => (current === !rendered ? current : !rendered));
  }, [chartType, data, hover, size, view]);

  const applyView = useCallback((nextView) => {
    setView((current) => normalizeView(typeof nextView === 'function' ? nextView(current) : nextView, data.length));
  }, [data.length]);

  const zoomAt = useCallback((factor, normalizedX) => {
    if (data.length <= 2) return;
    applyView((current) => {
      const safeView = normalizeView(current, data.length);
      const span = safeView.end - safeView.start;
      const center = safeView.start + clamp(normalizedX, 0, 1) * span;
      const nextSpan = clamp(span * factor, MIN_VISIBLE_SPAN, Math.max(MIN_VISIBLE_SPAN, data.length - 1));
      const start = center - clamp(normalizedX, 0, 1) * nextSpan;
      return { start, end: start + nextSpan };
    });
  }, [applyView, data.length]);

  const panByPixels = useCallback((deltaX) => {
    if (data.length <= 2 || !size.width) return;
    const l = layout(size.width, size.height);
    applyView((current) => {
      const safeView = normalizeView(current, data.length);
      const span = safeView.end - safeView.start;
      const deltaIndex = -(deltaX / l.plotWidth) * span;
      return { start: safeView.start + deltaIndex, end: safeView.end + deltaIndex };
    });
  }, [applyView, data.length, size.height, size.width]);

  const updateHover = useCallback((clientEvent) => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length || !size.width) return;

    const point = getMousePosition(clientEvent, canvas);
    const l = layout(size.width, size.height);

    if (point.x < l.left || point.x > l.left + l.plotWidth || point.y < l.top || point.y > l.volumeTop + l.volumeHeight) {
      setHover(null);
      return;
    }

    const safeView = normalizeView(view, data.length);
    const normalizedX = (point.x - l.left) / l.plotWidth;
    const index = clamp(Math.round(safeView.start + normalizedX * (safeView.end - safeView.start)), 0, data.length - 1);
    const candle = data[index];

    setHover({
      index,
      x: point.x,
      y: point.y,
      candle,
    });
  }, [data, size.height, size.width, view]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const onWheel = (event) => {
      event.preventDefault();
      if (!size.width) return;

      const absDeltaX = Math.abs(event.deltaX || 0);
      const absDeltaY = Math.abs(event.deltaY || 0);
      const shouldPan = event.shiftKey || (absDeltaX > absDeltaY && absDeltaX > 0);

      if (shouldPan) {
        const panDelta = absDeltaX > absDeltaY ? event.deltaX : event.deltaY;
        panByPixels(-panDelta);
        return;
      }

      const point = getMousePosition(event, canvas);
      const l = layout(size.width, size.height);
      const normalizedX = clamp((point.x - l.left) / l.plotWidth, 0, 1);
      const factor = event.deltaY > 0 ? 1.14 : 0.86;
      zoomAt(factor, normalizedX);
    };

    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [panByPixels, size.height, size.width, zoomAt]);

  const handlePointerDown = (event) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.setPointerCapture?.(event.pointerId);
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });

    if (pointersRef.current.size === 1) {
      dragRef.current = { active: true, lastX: event.clientX, moved: false };
      setIsDragging(true);
      pinchRef.current = null;
    }

    if (pointersRef.current.size === 2) {
      const points = [...pointersRef.current.values()];
      const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      pinchRef.current = { distance };
      dragRef.current.active = false;
      setIsDragging(false);
    }
  };

  const handlePointerMove = (event) => {
    if (pointersRef.current.has(event.pointerId)) {
      pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    }

    if (pointersRef.current.size === 2 && pinchRef.current && size.width) {
      const points = [...pointersRef.current.values()];
      const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      const midpointX = (points[0].x + points[1].x) / 2;
      const rect = canvasRef.current.getBoundingClientRect();
      const l = layout(size.width, size.height);
      const normalizedX = clamp((midpointX - rect.left - l.left) / l.plotWidth, 0, 1);

      if (distance > 0 && pinchRef.current.distance > 0) {
        zoomAt(pinchRef.current.distance / distance, normalizedX);
        pinchRef.current = { distance };
      }
      return;
    }

    if (dragRef.current.active) {
      const deltaX = event.clientX - dragRef.current.lastX;
      if (Math.abs(deltaX) > 1) {
        panByPixels(deltaX);
        dragRef.current.lastX = event.clientX;
        dragRef.current.moved = true;
      }
    }

    if (!dragRef.current.moved) {
      updateHover(event);
    }
  };

  const handlePointerUp = (event) => {
    pointersRef.current.delete(event.pointerId);
    dragRef.current.active = false;
    setIsDragging(false);
    pinchRef.current = null;

    if (pointersRef.current.size === 0) {
      updateHover(event);
    }
  };

  const resetView = () => {
    setView(getInitialView(data.length));
    setHover(null);
  };

  return (
    <div className="trading-chart-shell border border-[rgba(250,204,21,0.13)] bg-[#0b0a08] overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-[rgba(250,204,21,0.13)] bg-[#0f0e0b] px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <div className="text-sm text-zinc-500">{symbol || 'Инструмент'}</div>
            <div className="text-xl font-semibold text-white">{hasData ? formatPrice(getNumber(latest?.close)) : '—'}</div>
          </div>
          {hasData && (
            <div className={`text-sm font-semibold ${visibleChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {visibleChange >= 0 ? '+' : ''}{visibleChange.toFixed(2)}%
            </div>
          )}
          {hover?.candle && (
            <div className="hidden flex-wrap items-center gap-3 text-xs text-zinc-400 lg:flex">
              <span>{formatFullDate(hover.candle.timestamp)}</span>
              <span>O {formatPrice(getNumber(hover.candle.open))}</span>
              <span>H {formatPrice(getNumber(hover.candle.high))}</span>
              <span>L {formatPrice(getNumber(hover.candle.low))}</span>
              <span>C {formatPrice(getNumber(hover.candle.close))}</span>
              <span>V {formatVolume(getNumber(hover.candle.volume))}</span>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={resetView}
          disabled={!hasData}
          className="h-9 border border-zinc-700 bg-zinc-900 px-3 text-sm font-semibold text-zinc-200 hover:border-yellow-400 hover:text-yellow-300"
        >
          Сбросить вид
        </button>
      </div>

      <div ref={wrapperRef} className="relative h-[520px] select-none">
        <canvas
          ref={canvasRef}
          className={`block h-full w-full touch-none ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onPointerLeave={() => {
            if (!dragRef.current.active && pointersRef.current.size === 0) setHover(null);
          }}
        />

        {useSvgFallback && svgFallback && (
          <svg
            data-testid="market-svg-fallback"
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${svgFallback.width} ${svgFallback.height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="market-svg-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={PRICE_COLORS.accent} stopOpacity="0.24" />
                <stop offset="100%" stopColor={PRICE_COLORS.accent} stopOpacity="0.02" />
              </linearGradient>
            </defs>
            {svgFallback.horizontalLines.map((line, index) => (
              <line
                key={`grid-${index}`}
                x1={svgFallback.layout.left}
                x2={svgFallback.layout.left + svgFallback.layout.plotWidth}
                y1={line.y}
                y2={line.y}
                stroke={PRICE_COLORS.grid}
                strokeWidth="1"
              />
            ))}
            {chartType === 'area' && (
              <polygon points={svgFallback.areaPoints} fill="url(#market-svg-area)" />
            )}
            {(chartType === 'line' || chartType === 'area') ? (
              <polyline
                points={svgFallback.closePoints}
                fill="none"
                stroke={PRICE_COLORS.accent}
                strokeWidth="2.5"
                vectorEffect="non-scaling-stroke"
              />
            ) : (
              svgFallback.visible.map((item) => {
                const open = getNumber(item.open);
                const high = getNumber(item.high);
                const low = getNumber(item.low);
                const close = getNumber(item.close);
                const color = close >= open ? PRICE_COLORS.up : PRICE_COLORS.down;
                const x = svgFallback.xForIndex(item.__index);
                const yOpen = svgFallback.yForPrice(open);
                const yClose = svgFallback.yForPrice(close);
                const yHigh = svgFallback.yForPrice(high);
                const yLow = svgFallback.yForPrice(low);
                const bodyTop = Math.min(yOpen, yClose);
                const bodyHeight = Math.max(Math.abs(yClose - yOpen), 2);

                return (
                  <g key={`svg-candle-${item.__index}`}>
                    <line
                      x1={x}
                      x2={x}
                      y1={yHigh}
                      y2={yLow}
                      stroke={color}
                      strokeWidth="1.4"
                      vectorEffect="non-scaling-stroke"
                    />
                    <rect
                      x={x - svgFallback.candleWidth / 2}
                      y={bodyTop}
                      width={svgFallback.candleWidth}
                      height={bodyHeight}
                      fill={color}
                    />
                  </g>
                );
              })
            )}
          </svg>
        )}

        {!hasData && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-zinc-500">
            Данные для графика пока не загружены
          </div>
        )}

        {hover?.candle && (
          <div
            className="pointer-events-none absolute z-10 min-w-[210px] border border-zinc-700 bg-[#111111]/95 p-3 text-xs text-zinc-300 shadow-2xl backdrop-blur"
            style={{
              left: hover.x > size.width - 260 ? hover.x - 230 : hover.x + 16,
              top: hover.y > 330 ? hover.y - 184 : hover.y + 16,
            }}
          >
            <div className="mb-2 font-semibold text-white">{formatFullDate(hover.candle.timestamp)}</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <span className="text-zinc-500">Открытие</span><span className="text-right text-white">{formatPrice(getNumber(hover.candle.open))}</span>
              <span className="text-zinc-500">Максимум</span><span className="text-right text-white">{formatPrice(getNumber(hover.candle.high))}</span>
              <span className="text-zinc-500">Минимум</span><span className="text-right text-white">{formatPrice(getNumber(hover.candle.low))}</span>
              <span className="text-zinc-500">Закрытие</span><span className="text-right text-white">{formatPrice(getNumber(hover.candle.close))}</span>
              <span className="text-zinc-500">Объём</span><span className="text-right text-white">{formatVolume(getNumber(hover.candle.volume))}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
