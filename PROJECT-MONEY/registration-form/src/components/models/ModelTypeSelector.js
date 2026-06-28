import React from 'react';

export default function ModelTypeSelector({ activeTab, setActiveTab, modelConfigs }) {
  return (
    <section className="border border-yellow-400/12 bg-[#12110e] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.2)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-black text-white">Модель</h2>
        <div className="text-xs text-zinc-500">Adaptive / SVR / GPR</div>
      </div>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {Object.keys(modelConfigs).map((modelKey) => {
          const isActive = activeTab === modelKey;
          const model = modelConfigs[modelKey];
          return (
            <button
              key={modelKey}
              type="button"
              onClick={() => setActiveTab(modelKey)}
              className={`border p-3 text-left transition-all ${
                isActive
                  ? 'border-yellow-400 bg-yellow-400 text-black shadow-[0_16px_35px_rgba(250,204,21,0.14)]'
                  : 'border-yellow-400/12 bg-[#17140f] text-zinc-300 hover:border-yellow-400/35 hover:bg-[#1f1a10]'
              }`}
            >
              <div className="font-black">{model.name}</div>
              <div className={`mt-1 text-xs ${isActive ? 'text-black/65' : 'text-zinc-500'}`}>{model.kernel}</div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
