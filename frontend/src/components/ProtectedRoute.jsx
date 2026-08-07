import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PasswordChangeGate from './PasswordChangeGate';

export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-6 text-gray-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  // Covers the page-refresh case: /auth/me/ still reports an outstanding
  // admin-issued temporary password, so every route renders the change gate
  // instead of its normal content until it's cleared.
  if (user.must_change_password) {
    return (
      <PasswordChangeGate
        subtitle="Your password was reset by an administrator. Set a new one to continue."
      />
    );
  }
  if (roles && !roles.includes(user.role_name)) return <Navigate to="/" replace />;
  return children;
}
