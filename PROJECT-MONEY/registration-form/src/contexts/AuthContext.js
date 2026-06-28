// src/contexts/AuthContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await authAPI.getMe();
      setCurrentUser(response.data);
    } catch (error) {
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await authAPI.login(email, password);
    setCurrentUser(response.data.user);
    return response.data;
  };

  const register = async (userData) => {
    const response = await authAPI.register(userData);
    return response.data;
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (err) {
      console.error('Logout failed');
    } finally {
      setCurrentUser(null);
    }
  };

  const refreshCurrentUser = async () => {
    const response = await authAPI.getMe();
    setCurrentUser(response.data);
    return response.data;
  };

  const updateTinkoffToken = async (token) => {
    const response = await authAPI.updateTinkoffToken(token);
    await refreshCurrentUser();
    return response.data;
  };

  const value = {
    currentUser,
    login,
    register,
    logout,
    refreshCurrentUser,
    updateTinkoffToken,
    loading,
    isAuthenticated: !!currentUser,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
