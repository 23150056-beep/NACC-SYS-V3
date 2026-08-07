import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ActivityProvider } from './context/ActivityContext';
import { ToastProvider } from './context/ToastContext';
import { INSTRUMENT_MANAGER_ROLES } from './config/roles';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Children from './pages/Children';
import Report from './pages/Report';
import ChildProgressReport from './pages/ChildProgressReport';
import Monitoring from './pages/Monitoring';
import AgencySummary from './pages/AgencySummary';
import Settings from './pages/Settings';
import Users from './pages/Users';
import MyProfile from './pages/MyProfile';
import Instruments from './pages/Instruments';
import PreAssessment from './pages/PreAssessment';
import Schedule from './pages/Schedule';
import Survey from './pages/Survey';
import SamdReadiness from './pages/SamdReadiness';

function Shell({ children }) {
  return (
    <div style={{ display: 'flex', height: '100%', background: 'var(--bg-app)', overflow: 'hidden' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Topbar />
        <main className="racco-scroll" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
      <ActivityProvider>
        <BrowserRouter>
          <Routes>
          <Route path="/login" element={<Login />} />
          {/* Public, token-gated child opinionnaire (opened via QR code). */}
          <Route path="/survey/:token" element={<Survey />} />
          <Route path="/" element={<ProtectedRoute><Shell><Dashboard /></Shell></ProtectedRoute>} />
          {/* Terminated-case archive lives inside Records (Archived filter) — no separate route. */}
          <Route path="/children" element={<ProtectedRoute roles={['Administrator', 'Staff', 'Psychologist']}><Shell><Children /></Shell></ProtectedRoute>} />
          <Route path="/instruments" element={<ProtectedRoute roles={INSTRUMENT_MANAGER_ROLES}><Shell><Instruments /></Shell></ProtectedRoute>} />
          <Route path="/pre-assessment" element={<ProtectedRoute roles={['Psychologist']}><Shell><PreAssessment /></Shell></ProtectedRoute>} />
          <Route path="/schedule" element={<ProtectedRoute roles={['Administrator', 'Psychologist', 'Staff']}><Shell><Schedule /></Shell></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Shell><Report /></Shell></ProtectedRoute>} />
          <Route path="/report/child/:id" element={<ProtectedRoute><Shell><ChildProgressReport /></Shell></ProtectedRoute>} />
          <Route path="/monitoring" element={<ProtectedRoute roles={['Administrator', 'Staff', 'Psychologist']}><Shell><Monitoring /></Shell></ProtectedRoute>} />
          <Route path="/reports/summary" element={<ProtectedRoute roles={['Administrator', 'Staff']}><Shell><AgencySummary /></Shell></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute roles={['Administrator']}><Shell><Users /></Shell></ProtectedRoute>} />
          <Route path="/samd" element={<ProtectedRoute roles={['Administrator']}><Shell><SamdReadiness /></Shell></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute roles={['Administrator']}><Shell><Settings /></Shell></ProtectedRoute>} />
          {/* Demo-only profile prototype for Social Worker / Psychologist. */}
          <Route path="/profile" element={<ProtectedRoute roles={['Staff', 'Psychologist']}><Shell><MyProfile /></Shell></ProtectedRoute>} />
          </Routes>
        </BrowserRouter>
      </ActivityProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
