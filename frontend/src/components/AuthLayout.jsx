import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';

/* The shell both Login and Signup sit in.
 *
 * Extracted rather than duplicated: the two pages are reached one after the
 * other, so any drift between them — a different card width, a heavier
 * shadow, the seal a few pixels off — reads as the second page belonging to a
 * different system. Sharing the frame means only the form differs, which is
 * the only thing that should.
 *
 * Sizing is deliberately NOT inline. Everything vertical scales with the
 * viewport height and the card is capped at the window (see .racco-auth-* in
 * index.css), because the request-access form is tall enough to run off the
 * bottom of a 768p laptop at 100% zoom. Hard-coded paddings here would fight
 * that and win.
 */

/* One link style for both pages. Two hand-written inline styles drifted by a
 * font weight the first time this was written; this is the fix. */
export function AuthLink({ to, children }) {
  return (
    <Link to={to} style={{ color: 'var(--blue-600)', fontWeight: 700, textDecoration: 'none' }}>
      {children}
    </Link>
  );
}

export default function AuthLayout({ heading, subheading, children, footer = null, title = null }) {
  // These are the only two screens reached before the app shell mounts, so
  // nothing else is setting the tab title — without this both read whatever
  // index.html says, and a browser with several tabs open shows two identical
  // ones.
  useEffect(() => {
    if (!title) return undefined;
    const previous = document.title;
    document.title = `${title} · NACC RACCO I`;
    return () => { document.title = previous; };
  }, [title]);

  return (
    <div className="racco-sky-wash racco-auth-wash">
      <div className="racco-login-card"
           style={{ background: 'var(--surface)', borderRadius: 'var(--radius-2xl)',
                    boxShadow: 'var(--shadow-xl)', overflow: 'hidden' }}>

        {/* Brand panel */}
        <div className="racco-login-brand"
             style={{ background: 'linear-gradient(155deg, var(--blue-700), var(--blue-600) 60%, var(--blue-800))',
                      color: '#fff', position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(120% 90% at 100% 0%, rgba(255,172,42,0.22), transparent 55%)' }} />
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 14 }}>
            <img src="/racco-seal.jpg" alt="NACC seal" className="racco-auth-seal"
                 style={{ borderRadius: '50%', objectFit: 'cover',
                          boxShadow: 'var(--shadow-md)', flex: 'none' }} />
            <div style={{ minWidth: 0 }}>
              <div className="racco-auth-org"
                   style={{ fontFamily: 'var(--font-display)', fontWeight: 800, lineHeight: 1.1 }}>
                National Authority for Child Care
              </div>
              <div style={{ fontSize: 12, opacity: 0.85, fontWeight: 600, letterSpacing: '0.02em' }}>
                NACC – Regional Alternative Childcare Office 1
              </div>
            </div>
          </div>
          {/* The first thing to go on a short window — it is the one part of
              the page carrying no information the user needs to act on. */}
          <div className="racco-login-tagline" style={{ position: 'relative' }}>
            <div className="racco-auth-motto"
                 style={{ fontFamily: 'var(--font-display)', fontWeight: 800, lineHeight: 1.1 }}>
              In The Best Interests<br />of the Child
            </div>
            <p style={{ marginTop: 10, fontSize: 13.5, opacity: 0.85, lineHeight: 1.55, maxWidth: 320 }}>
              Behavioral Assessment &amp; Counseling Support System
            </p>
          </div>
        </div>

        {/* Form panel. Scrolls inside itself on a window too short for the
            form, so the submit button is always reachable. */}
        <div className="racco-auth-panel racco-scroll">
          <h1 style={{ fontFamily: 'var(--font-display)', fontWeight: 800, color: 'var(--text-strong)' }}>
            {heading}
          </h1>
          {subheading && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.5 }}>
              {subheading}
            </p>
          )}
          {children}
          {footer && (
            <div style={{ marginTop: 'clamp(10px, 1.8vh, 20px)',
                          paddingTop: 'clamp(9px, 1.5vh, 16px)',
                          borderTop: '1px solid var(--border)',
                          fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' }}>
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
