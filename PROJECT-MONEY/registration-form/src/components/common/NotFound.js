import React from 'react';
import { Link } from 'react-router-dom';
import Icon from './Icons';

export default function NotFound() {
  return (
    <section className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-10">
      <div className="max-w-xl rounded-[2rem] border border-zinc-800 bg-[#0b0b0b] p-8 text-center shadow-2xl">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-yellow-400 text-black">
          <Icon name="alert" className="h-7 w-7" />
        </div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-yellow-300">404</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">Страница не найдена</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-400">
          Такого маршрута нет в интерфейсе Trade Master. Проверьте адрес или вернитесь в рабочий раздел.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
          <Link to="/portfolio" className="rounded-2xl bg-yellow-400 px-5 py-3 text-sm font-semibold text-black hover:bg-yellow-300">
            Вернуться в портфель
          </Link>
          <Link to="/market" className="rounded-2xl border border-zinc-700 px-5 py-3 text-sm font-semibold text-zinc-200 hover:bg-zinc-900">
            Открыть рынок
          </Link>
        </div>
      </div>
    </section>
  );
}
