import React, { createContext, useContext, useEffect, useState } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access');
    if (!token) { setLoading(false); return; }
    api.get('/auth/me/')
      .then((res) => setUser(res.data))
      .catch(() => { localStorage.removeItem('access'); localStorage.removeItem('refresh'); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login/', { email, password });
    localStorage.setItem('access', data.access);
    localStorage.setItem('refresh', data.refresh);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    // Clear any unsaved intake drafts (keyed per-user) so they never leak to
    // whichever account logs in next on this workstation.
    try {
      Object.keys(localStorage)
        .filter((k) => k.startsWith('nacc-child-draft:'))
        .forEach((k) => localStorage.removeItem(k));
    } catch { /* private browsing / storage unavailable */ }
    setUser(null);
  };

  // Shallow-merges into the stored user (e.g. clearing must_change_password
  // after a successful change) without a round-trip to /auth/me/.
  const updateUser = (patch) => setUser((u) => (u ? { ...u, ...patch } : u));

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
