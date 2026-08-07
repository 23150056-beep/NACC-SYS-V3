import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const refresh = localStorage.getItem('refresh');
    // A 401 raised because the account has a forced password change pending
    // (see accounts/authentication.py) is not an expired/invalid session —
    // refreshing the access token won't help, since the new token is blocked
    // the same way. Reject as-is so the change-password gate can show its own
    // error instead of triggering the logout/redirect below.
    const isPasswordChangeRequired = error.response?.status === 401
      && String(error.response?.data?.detail || '').includes('must change your password');
    if (isPasswordChangeRequired) return Promise.reject(error);
    if (error.response?.status === 401 && refresh && !original._retry) {
      original._retry = true;
      try {
        refreshing = refreshing || axios.post(`${baseURL}/auth/refresh/`, { refresh });
        const { data } = await refreshing;
        refreshing = null;
        localStorage.setItem('access', data.access);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (e) {
        refreshing = null;
        localStorage.removeItem('access');
        localStorage.removeItem('refresh');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
