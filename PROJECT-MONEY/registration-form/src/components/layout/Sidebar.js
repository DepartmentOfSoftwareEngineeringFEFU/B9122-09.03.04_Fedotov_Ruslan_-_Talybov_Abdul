import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import Icon from '../common/Icons';

function TradeLogo({ className = '' }) {
  return (
    <span
      className={`relative flex h-10 w-10 items-center justify-center border border-yellow-400/35 bg-[#0d0c08] text-yellow-300 shadow-[0_0_24px_rgba(250,204,21,0.12)] ${className}`}
      aria-hidden="true"
    >
      <svg className="h-6 w-6" viewBox="0 0 28 28" fill="none">
        <path d="M6 20.5L13.8 4.5L22 20.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" strokeLinejoin="miter" />
        <path d="M9.5 16.5H19.2" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" />
        <path d="M17.6 9.4L22.8 4.2" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />
        <path d="M22.8 4.2V10.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />
      </svg>
      <span className="absolute -right-1 -top-1 h-2.5 w-2.5 border border-black bg-yellow-400" />
    </span>
  );
}

function LogoSidebarToggle({ isOpen, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="group relative flex h-10 w-10 items-center justify-center text-zinc-300 transition-colors hover:text-yellow-300 focus-visible:text-yellow-300"
      title={isOpen ? 'Свернуть боковую панель' : 'Открыть боковую панель'}
      aria-label={isOpen ? 'Свернуть боковую панель' : 'Открыть боковую панель'}
      aria-expanded={isOpen}
    >
      <TradeLogo className="transition-opacity duration-150 group-hover:opacity-0 group-focus-visible:opacity-0" />
      <span className="absolute inset-0 flex items-center justify-center border border-zinc-800 bg-zinc-950 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100">
        <Icon name={isOpen ? 'sidebarClose' : 'sidebarOpen'} className="h-5 w-5" />
      </span>
    </button>
  );
}

export default function Sidebar({ isOpen, onToggle }) {
  const location = useLocation();

  const menuItems = [
    { path: '/trading', label: 'Торговля', icon: 'trading' },
    { path: '/portfolio', label: 'Портфель', icon: 'portfolio' },
    { path: '/market', label: 'Рынок', icon: 'market' },
    { path: '/models', label: 'ML-модели', icon: 'models' },
    { path: '/analytics', label: 'Аналитика', icon: 'analytics' },
    { path: '/settings', label: 'Профиль', icon: 'settings' },
  ];

  return (
    <aside className={`fixed left-0 top-0 z-50 h-screen border-r border-zinc-800 bg-[#090909] transition-[width] duration-300 ${isOpen ? 'w-64' : 'w-16'}`}>
      <nav className="flex h-full flex-col p-3">
        <div className={`mb-5 flex h-10 items-center ${isOpen ? 'justify-between' : 'justify-center'}`}>
          {isOpen ? (
            <>
              <TradeLogo />
              <button
                type="button"
                onClick={onToggle}
                className="inline-flex h-9 w-9 items-center justify-center border border-transparent text-zinc-400 transition-colors hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-100 focus-visible:text-yellow-300"
                title="Свернуть боковую панель"
                aria-label="Свернуть боковую панель"
                aria-expanded={isOpen}
              >
                <Icon name="sidebarClose" className="h-5 w-5" />
              </button>
            </>
          ) : (
            <LogoSidebarToggle isOpen={isOpen} onToggle={onToggle} />
          )}
        </div>

        <ul className="space-y-1">
          {menuItems.map((item) => {
            const active = location.pathname === item.path;
            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  title={!isOpen ? item.label : undefined}
                  aria-label={item.label}
                  aria-current={active ? 'page' : undefined}
                  className={`flex items-center gap-3 px-3 py-3 text-sm font-medium transition-all ${active ? 'border border-yellow-400/70 bg-yellow-400 text-black shadow-[0_0_24px_rgba(250,204,21,0.14)]' : 'border border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-100'} ${isOpen ? 'justify-start' : 'justify-center'}`}
                >
                  <Icon name={item.icon} className="h-5 w-5 shrink-0" />
                  {isOpen && <span className="truncate">{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
