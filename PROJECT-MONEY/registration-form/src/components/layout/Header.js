import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import Icon from '../common/Icons';

export default function Header({ sidebarOpen }) {
  const { currentUser, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <header className={`fixed right-0 top-0 z-40 border-b border-zinc-800 bg-[#090909]/95 backdrop-blur-xl transition-[left] duration-300 ${sidebarOpen ? 'left-64' : 'left-16'}`}>
      <div className="flex h-16 items-center justify-end px-4 lg:px-6">
        <div className="flex items-center gap-3">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-zinc-100">{currentUser?.username || 'Трейдер'}</p>
            <p className="max-w-[240px] truncate text-xs text-zinc-500">{currentUser?.email || 'investor@example.com'}</p>
          </div>
          <div className="hidden h-8 w-px bg-zinc-800 sm:block" />
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Выйти из аккаунта"
            className="inline-flex items-center gap-2 border border-zinc-800 bg-zinc-950 px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-red-500/60 hover:text-red-300"
          >
            <Icon name="logout" className="h-4 w-4" />
            <span className="hidden sm:inline">Выйти</span>
          </button>
        </div>
      </div>
    </header>
  );
}
