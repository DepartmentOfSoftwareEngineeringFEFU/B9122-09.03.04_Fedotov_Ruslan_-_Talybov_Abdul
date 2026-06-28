import React, { createContext, useContext, useEffect } from 'react';

const ThemeContext = createContext({
  isDark: true,
  theme: 'dark',
  toggleTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }) {
  useEffect(() => {
    localStorage.setItem('quantum-trade-theme', 'dark');
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
  }, []);

  return (
    <ThemeContext.Provider value={{ isDark: true, theme: 'dark', toggleTheme: () => {} }}>
      <div className="dark min-h-screen bg-[#070707] text-zinc-100">
        {children}
      </div>
    </ThemeContext.Provider>
  );
}
