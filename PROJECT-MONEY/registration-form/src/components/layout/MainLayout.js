import React, { useState } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';

export default function MainLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen bg-[#070707] text-zinc-100">
      <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen((value) => !value)} />
      <Header sidebarOpen={sidebarOpen} />
      <main className={`flex-1 pt-16 transition-[margin] duration-300 ${sidebarOpen ? 'ml-64' : 'ml-16'}`}>
        <div className="min-h-[calc(100vh-4rem)] p-5 lg:p-7">
          {children}
        </div>
      </main>
    </div>
  );
}
