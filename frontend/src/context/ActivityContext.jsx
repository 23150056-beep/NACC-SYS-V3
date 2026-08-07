import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import api from '../api/client';
import { useAuth } from './AuthContext';

const ActivityContext = createContext(null);
const SEEN_KEY = 'lastSeenActivityAt';

export function ActivityProvider({ children }) {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSeen, setLastSeen] = useState(() => localStorage.getItem(SEEN_KEY) || '');

  const refresh = useCallback(() => {
    if (!localStorage.getItem('access')) return;
    setLoading(true);
    api.get('/activity/')
      .then((r) => setEvents(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user) refresh();
    else setEvents([]);
  }, [user, refresh]);

  const unreadCount = events.filter(
    (e) => !lastSeen || new Date(e.created_at) > new Date(lastSeen)
  ).length;

  const markSeen = useCallback(() => {
    const now = new Date().toISOString();
    localStorage.setItem(SEEN_KEY, now);
    setLastSeen(now);
  }, []);

  return (
    <ActivityContext.Provider value={{ events, loading, refresh, unreadCount, markSeen }}>
      {children}
    </ActivityContext.Provider>
  );
}

export function useActivity() {
  return useContext(ActivityContext)
    || { events: [], loading: false, refresh: () => {}, unreadCount: 0, markSeen: () => {} };
}
