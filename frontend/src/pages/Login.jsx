import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Button, FormField, Input, Alert, Icon, Modal, ROLE_META } from '../ui';
import PasswordChangeGate from '../components/PasswordChangeGate';
import GoogleSignInButton from '../components/GoogleSignInButton';

// What a first-time Google user may say about themselves. Administrator is
// absent on purpose: that account is created by an existing administrator and
// never through this door.
const REQUESTABLE = ['Staff', 'Psychologist'];

export default function Login() {
  const { login, loginWithGoogle } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // 'login'   — sign-in form
  // 'help'    — "resets are admin-issued" info panel
  // 'forced'  — the just-logged-in account has a temporary password to replace
  // 'role'    — first Google sign-up: asking what they do here
  // 'pending' — request recorded, waiting on an administrator
  const [view, setView] = useState('login');
  // Held only between the role question and the answer. Google's credential is
  // short-lived and single-purpose, and nothing outside this component sees it.
  const [credential, setCredential] = useState(null);

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

  const submitGoogle = async (cred, requestedRole = null) => {
    setError('');
    setBusy(true);
    try {
      const u = await loginWithGoogle(cred, requestedRole);
      toast.success(`Welcome back, ${u?.first_name || u?.fullname || 'there'}`);
      navigate('/');
    } catch (err) {
      const data = err.response?.data;
      // 403 + pending_approval is not a failure: Google verified them, this
      // system simply has not authorised them yet. Showing an error here is
      // how you get someone clicking the same button all afternoon.
      if (err.response?.status === 403 && data?.state === 'pending_approval') {
        setCredential(cred);
        setView(data.role_required ? 'role' : 'pending');
        return;
      }
      const message = data?.detail
        || 'Google sign-in failed. Please try again or use your password.';
      setError(message);
      toast.error(message);
      // A refused account lands back on the form with the message. The server
      // keeps that message identical for "declined", "deactivated" and "no
      // such account", so there is deliberately nothing more specific to show.
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

  const heading = {
    login: 'Log in to your account',
    help: 'Need a password reset?',
    pending: 'Request received',
  }[view] || 'Log in to your account';

  const subheading = {
    login: 'Continue with Google, or use your agency credentials.',
    help: 'Password resets are handled by your administrator.',
    pending: 'An administrator has to approve your access.',
  }[view] || '';

  return (
    <div className="racco-sky-wash" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, overflowY: 'auto' }}>
      <div className="racco-login-card" style={{ width: 880, maxWidth: '100%', background: 'var(--surface)', borderRadius: 'var(--radius-2xl)', boxShadow: 'var(--shadow-xl)', overflow: 'hidden' }}>
        {/* Brand panel */}
        <div className="racco-login-brand" style={{ background: 'linear-gradient(155deg, var(--blue-700), var(--blue-600) 60%, var(--blue-800))', color: '#fff', padding: '40px 38px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', position: 'relative', overflow: 'hidden', minHeight: 480 }}>
          <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(120% 90% at 100% 0%, rgba(255,172,42,0.22), transparent 55%)' }} />
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 16 }}>
            <img src="/racco-seal.jpg" alt="NACC seal" style={{ width: 72, height: 72, borderRadius: '50%', objectFit: 'cover', boxShadow: 'var(--shadow-md)', flex: 'none' }} />
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 26, lineHeight: 1.1 }}>National Authority for Child Care</div>
              <div style={{ fontSize: 12, opacity: 0.85, fontWeight: 600, letterSpacing: '0.02em' }}>NACC – Regional Alternative Childcare Office 1</div>
            </div>
          </div>
          <div className="racco-login-tagline" style={{ position: 'relative' }}>
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
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 800, color: 'var(--text-strong)' }}>{heading}</h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>{subheading}</p>

          {view === 'login' && (
            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {error && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />}>{error}</Alert>}

              {/* Google first: it is the only route for staff and
                  psychologists, and Google's own guidance asks that the button
                  be at least as prominent as other sign-in options. Renders
                  nothing at all when the server has no client configured, so
                  this whole block disappears rather than leaving a stray
                  divider above empty space. */}
              <GoogleSignInButton onCredential={(c) => submitGoogle(c)} disabled={busy} />

              <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <FormField label="Username">
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@racco1.gov.ph" leading={<Icon name="user" size={16} />} required />
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
            </div>
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

          {/* One message, and nothing to click but the way back. A waiting
              screen that offers admin-facing instructions as its only link is
              a documented trap: the person waiting clicks it, lands somewhere
              meant for someone else, and concludes the system is broken. */}
          {view === 'pending' && (
            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 12, padding: '26px 20px', background: 'var(--blue-50)', border: '1px solid var(--blue-100)', borderRadius: 'var(--radius-lg)' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 52, height: 52, borderRadius: '50%', background: 'var(--surface)', color: 'var(--blue-600)' }}>
                  <Icon name="hourglass" size={24} />
                </span>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>
                  Waiting for approval
                </div>
                <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: 'var(--text-body)', maxWidth: 320 }}>
                  Your request has been sent to the RACCO I administrator. Once
                  they approve it and set your role, sign in with the same
                  Google account and you will go straight in.
                </p>
              </div>
              <Button type="button" variant="secondary" size="lg" fullWidth onClick={() => { setCredential(null); setView('login'); }}>
                ← Back to sign in
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Asked once, on a first sign-up. Why before what: people answer a
          question better when they know what it is for, and this one needs to
          be visibly a request rather than a self-service switch. */}
      {view === 'role' && (
        <Modal
          open
          onClose={() => { setCredential(null); setView('login'); }}
          title="What do you do at RACCO I?"
          subtitle="So the system shows you the right tools."
          icon={<Icon name="user-round-search" size={19} />}
          tone="brand"
          width={470}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {REQUESTABLE.map((roleName) => {
              const meta = ROLE_META[roleName];
              return (
                <button
                  key={roleName}
                  type="button"
                  disabled={busy}
                  onClick={() => submitGoogle(credential, roleName)}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = meta.color; e.currentTarget.style.background = meta.soft; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface)'; }}
                  style={{ display: 'flex', alignItems: 'flex-start', gap: 13, width: '100%', padding: '15px 16px', textAlign: 'left', cursor: busy ? 'wait' : 'pointer', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', transition: 'var(--transition-base)' }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38, flex: 'none', borderRadius: 'var(--radius-md)', background: meta.soft, color: meta.color }}>
                    <Icon name={meta.icon} size={19} />
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: 'block', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 15, color: 'var(--text-strong)' }}>{roleName}</span>
                    <span style={{ display: 'block', fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-muted)', marginTop: 2 }}>{meta.desc}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <Alert tone="info" icon={<Icon name="shield-check" size={18} />}>
            An administrator confirms this before your account is opened, so
            pick whichever describes your work — it is a request, not a setting.
          </Alert>
        </Modal>
      )}
    </div>
  );
}
