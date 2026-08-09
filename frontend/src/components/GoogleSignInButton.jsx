import React, { useEffect, useRef, useState } from 'react';
import api from '../api/client';

const GIS_SRC = 'https://accounts.google.com/gsi/client';

// Load Google Identity Services once per page, and let every caller await the
// same load. Without the shared promise, two mounts would inject two scripts.
let gisPromise = null;
function loadGis() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (gisPromise) return gisPromise;
  gisPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = resolve;
    script.onerror = () => { gisPromise = null; reject(new Error('gis-unavailable')); };
    document.head.appendChild(script);
  });
  return gisPromise;
}

/**
 * Renders Google's official sign-in button.
 *
 * Nothing is shown unless the server reports the feature configured, so an
 * agency running without Google sees the plain password form and no dead
 * button. The client ID comes from the API rather than a build-time variable
 * so switching this on doesn't require rebuilding the frontend.
 */
export default function GoogleSignInButton({ onCredential, onError, disabled = false }) {
  const holder = useRef(null);
  const [state, setState] = useState('loading'); // loading | ready | off | failed

  useEffect(() => {
    let cancelled = false;

    (async () => {
      let config;
      try {
        const { data } = await api.get('/auth/google/config/');
        config = data;
      } catch {
        if (!cancelled) setState('off');   // API unreachable: fall back to password only
        return;
      }
      if (cancelled) return;
      if (!config.enabled || !config.client_id) { setState('off'); return; }

      try {
        await loadGis();
      } catch {
        // Google's script is blocked (offline, firewall, ad blocker). Say so
        // rather than leaving an empty gap where a button should be.
        if (!cancelled) setState('failed');
        return;
      }
      if (cancelled || !holder.current) return;

      window.google.accounts.id.initialize({
        client_id: config.client_id,
        callback: (response) => onCredential(response.credential),
        // Shared workstations: never auto-select a previous account, and
        // never silently re-sign someone in as a colleague.
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      window.google.accounts.id.renderButton(holder.current, {
        theme: 'outline',
        size: 'large',
        width: 320,
        text: 'signin_with',
        shape: 'rectangular',
      });
      setState('ready');
    })();

    return () => { cancelled = true; };
    // Mount-only: re-running would re-render Google's button into the node.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state === 'off') return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      {/* The divider lives here rather than in the page so it vanishes with
          the button when Google Sign-In is not configured. */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--text-muted)' }}>OR</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
      </div>

      {state === 'failed' ? (
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)', textAlign: 'center' }}>
          Google Sign-In could not load. Use your email and password instead.
        </div>
      ) : (
        <div
          ref={holder}
          aria-busy={state === 'loading'}
          style={{
            minHeight: 44,
            // Google owns the button's internals, so a disabled state has to
            // be applied from outside it.
            opacity: disabled ? 0.5 : 1,
            pointerEvents: disabled ? 'none' : 'auto',
          }}
        />
      )}
    </div>
  );
}
