import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import LoginForm from './components/auth/LoginForm';
import RegistrationForm from './components/auth/RegistrationForm';
import Trading from './components/trading/Trading';
import Portfolio from './components/portfolio/Portfolio';
import Analytics from './components/analytics/Analytics';
import Models from './components/models/Models';
import MarketData from './components/market/MarketData';
import MainLayout from './components/layout/MainLayout';
import UserSettings from './components/settings/UserSettings';
import Backtest from './components/backtest/Backtest';
import NotFound from './components/common/NotFound';
import LoadingSpinner from './components/common/LoadingSpinner';

function FullScreenLoader() {
  return <LoadingSpinner fullScreen label="Проверяем сессию..." />;
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <FullScreenLoader />;
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <FullScreenLoader />;
  }

  return !isAuthenticated ? children : <Navigate to="/portfolio" replace />;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <div className="App min-h-screen bg-[#070707] text-zinc-100">
            <Routes>
              <Route path="/login" element={<PublicRoute><LoginForm /></PublicRoute>} />
              <Route path="/register" element={<PublicRoute><RegistrationForm /></PublicRoute>} />
              <Route path="/trading" element={<ProtectedRoute><MainLayout><Trading /></MainLayout></ProtectedRoute>} />
              <Route path="/portfolio" element={<ProtectedRoute><MainLayout><Portfolio /></MainLayout></ProtectedRoute>} />
              <Route path="/market" element={<ProtectedRoute><MainLayout><MarketData /></MainLayout></ProtectedRoute>} />
              <Route path="/models" element={<ProtectedRoute><MainLayout><Models /></MainLayout></ProtectedRoute>} />
              <Route path="/analytics" element={<ProtectedRoute><MainLayout><Analytics /></MainLayout></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute><MainLayout><UserSettings /></MainLayout></ProtectedRoute>} />

              <Route path="/dashboard" element={<Navigate to="/market" replace />} />
              <Route path="/backtest" element={<ProtectedRoute><MainLayout><Backtest /></MainLayout></ProtectedRoute>} />
              <Route path="/" element={<Navigate to="/portfolio" replace />} />
              <Route path="*" element={<ProtectedRoute><MainLayout><NotFound /></MainLayout></ProtectedRoute>} />
            </Routes>
          </div>
        </Router>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
