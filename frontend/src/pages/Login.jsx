import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Button, FormField, Input, Alert, Icon } from '../ui';
import PasswordChangeGate from '../components/PasswordChangeGate';

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // 'login' = sign-in form, 'help' = "resets are admin-issued" info panel,
  // 'forced' = the just-logged-in account has a temporary password to replace
  const [view, setView] = useState('login');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const u = await login(email, password);
      if (u?.must_change_password) {
        // Do not enter the app yet — the account was issued a temporary
        // password and must set its own before anything else works.
        setView('forced');
        return;
      }
      toast.success(`Welcome back, ${u?.first_name || u?.fullname || 'there'}`);
      navigate('/');
    } catch (err) {
      if (err.response?.status === 429) {
        const message = err.response.data?.detail || 'Too many failed login attempts. Try again later.';
        setError(message);
        toast.error(message);
      } else {
        setError('Invalid username or password.');
        toast.error('Sign-in failed. Check your credentials.');
      }
    } finally {
      setBusy(false);
    }
  };

  if (view === 'forced') {
    return (
      <PasswordChangeGate
        prefillCurrent={password}
        title="Set a new password"
        subtitle="This account has a temporary password issued by an administrator. Choose a new password to continue."
        onDone={() => { toast.success('Password updated. Welcome!'); navigate('/'); }}
      />
    );
  }

  return (
    <div className="racco-sky-wash" style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, overflowY: 'auto' }}>
      <div style={{ width: 880, maxWidth: '100%', display: 'grid', gridTemplateColumns: '1.05fr 1fr', background: 'var(--surface)', borderRadius: 'var(--radius-2xl)', boxShadow: 'var(--shadow-xl)', overflow: 'hidden' }}>
        {/* Brand panel */}
        <div style={{ background: 'linear-gradient(155deg, var(--blue-700), var(--blue-600) 60%, var(--blue-800))', color: '#fff', padding: '40px 38px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', position: 'relative', overflow: 'hidden', minHeight: 480 }}>
          <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(120% 90% at 100% 0%, rgba(255,172,42,0.22), transparent 55%)' }} />
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 16 }}>
            <img src="/racco-seal.jpg" alt="NACC seal" style={{ width: 72, height: 72, borderRadius: '50%', objectFit: 'cover', boxShadow: 'var(--shadow-md)' }} />
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 26, lineHeight: 1.1 }}>National Authority for Child Care</div>
              <div style={{ fontSize: 12, opacity: 0.85, fontWeight: 600, letterSpacing: '0.02em' }}>NACC – Regional Alternative Childcare Office 1</div>
            </div>
          </div>
          <div style={{ position: 'relative' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1.1 }}>
              In The Best Interests<br />of the Child
            </div>
            <p style={{ marginTop: 12, fontSize: 14, opacity: 0.85, lineHeight: 1.6, maxWidth: 320 }}>
              Behavioral Assessment &amp; Counseling Support System
            </p>
          </div>
        </div>

        {/* Form panel */}
        <div style={{ padding: '40px 38px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 800, color: 'var(--text-strong)' }}>
            {view === 'login' ? 'Log in to your account' : 'Need a password reset?'}
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
            {view === 'login' ? 'Enter your agency credentials to continue.' : 'Password resets are handled by your administrator.'}
          </p>

          {view === 'login' && (
            <form onSubmit={submit} style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {error && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />}>{error}</Alert>}
              <FormField label="Username">
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@racco1.gov.ph" leading={<Icon name="user" size={16} />} required autoFocus />
              </FormField>
              <FormField label="Password">
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" leading={<Icon name="lock" size={16} />} required />
              </FormField>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: -6 }}>
                <button type="button" onClick={() => { setError(''); setView('help'); }} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, color: 'var(--blue-600)' }}>Forgot password?</button>
              </div>
              <Button type="submit" variant="primary" size="lg" fullWidth disabled={busy} iconRight={busy ? null : <Icon name="arrow-right" size={18} />}>
                {busy ? 'Logging in…' : 'Log In'}
              </Button>
            </form>
          )}

          {view === 'help' && (
            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Alert tone="info" icon={<Icon name="info" size={18} />}>
                There is no self-service reset. Ask your administrator for a temporary
                password, log in with it, and you will be asked to set a new password
                of your own before continuing.
              </Alert>
              <Button type="button" variant="secondary" size="lg" fullWidth onClick={() => setView('login')}>← Back to log in</Button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
