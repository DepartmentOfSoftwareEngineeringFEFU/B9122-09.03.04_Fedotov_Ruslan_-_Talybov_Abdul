import React from 'react';

const sourceOptions = [
  { key: 'portfolio', label: 'Портфель', hint: 'мои позиции' },
  { key: 'popular', label: 'MOEX', hint: 'все акции' },
  { key: 'manual', label: 'FIGI', hint: 'вручную' },
];

export default function InstrumentSelector({
  selectedSource,
  setSelectedSource,
  selectedInstrument,
  manualInstrument,
  setManualInstrument,
  instrumentOptions,
  selectInstrument,
}) {
  const fieldClass = 'w-full border border-yellow-400/12 bg-[#11100d] px-4 py-3 text-white outline-none hover:border-yellow-400/28 focus:border-yellow-400';

  return (
    <section className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-black text-white">Акция</h2>
        <div className="break-all font-mono text-xs text-zinc-500">{selectedInstrument?.figi || 'FIGI не выбран'}</div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2">
        {sourceOptions.map(item => {
          const isActive = selectedSource === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setSelectedSource(item.key)}
              className={`border px-3 py-3 text-left transition-all ${
                isActive
                  ? 'border-yellow-400 bg-yellow-400 text-black shadow-[0_14px_35px_rgba(250,204,21,0.14)]'
                  : 'border-yellow-400/12 bg-[#15130f] text-zinc-300 hover:border-yellow-400/35 hover:bg-[#1d190f]'
              }`}
            >
              <div className="text-sm font-bold">{item.label}</div>
              <div className={`mt-0.5 text-[11px] ${isActive ? 'text-black/65' : 'text-zinc-500'}`}>{item.hint}</div>
            </button>
          );
        })}
      </div>

      {selectedSource !== 'manual' ? (
        <select
          value={selectedInstrument.figi}
          onChange={(event) => {
            const item = instrumentOptions.find(option => option.figi === event.target.value);
            if (item) selectInstrument(item, selectedSource);
          }}
          className={fieldClass}
        >
          {instrumentOptions.length === 0 && <option value="">Нет доступных инструментов</option>}
          {instrumentOptions.map(item => (
            <option key={item.figi} value={item.figi}>
              {(item.ticker || item.figi)} — {item.name || item.figi}
            </option>
          ))}
        </select>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_150px]">
          <input
            value={manualInstrument.figi}
            onChange={(event) => setManualInstrument(prev => ({ ...prev, figi: event.target.value }))}
            placeholder="FIGI"
            className={fieldClass}
          />
          <input
            value={manualInstrument.ticker}
            onChange={(event) => setManualInstrument(prev => ({ ...prev, ticker: event.target.value }))}
            placeholder="Ticker"
            className={fieldClass}
          />
          <button
            type="button"
            onClick={() => selectInstrument(manualInstrument, 'manual')}
            className="border border-yellow-300 bg-yellow-400 px-4 py-3 font-bold text-black hover:border-yellow-200 hover:bg-yellow-300"
          >
            Выбрать
          </button>
        </div>
      )}
    </section>
  );
}
