import React from 'react';

export default function BotTradeControls({ forecastResult, setReminder }) {
  const action = forecastResult?.recommendation?.action;
  if (!['HOLD', 'WAIT'].includes(action)) return null;

  return (
    <div className="mt-5 rounded-2xl p-5 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-[#070707]">
      <div className="font-bold text-gray-900 dark:text-white mb-2">Повторить прогноз позже</div>
      <div className="flex flex-wrap gap-2">
        {[15, 30, 60].map(minutes => (
          <button
            key={minutes}
            type="button"
            onClick={() => setReminder(minutes)}
            className="px-4 py-2 rounded-xl text-sm font-semibold bg-white dark:bg-[#111111] border border-gray-200 dark:border-zinc-800 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Через {minutes} мин
          </button>
        ))}
      </div>
    </div>
  );
}
