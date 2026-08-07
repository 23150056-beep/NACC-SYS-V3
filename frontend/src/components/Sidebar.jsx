import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Icon, ROLE_META } from '../ui';

// Role-gated navigation. Sections render only when they contain a visible item.
const NAV = [
  { section: 'Overview' },
  { to: '/', label: 'Dashboard', icon: 'layout-dashboard', roles: ['Administrator', 'Psychologist', 'Staff'], end: true },
  { section: 'Casework' },
  // Terminated-case archive lives inside Records (Archived filter), not its own route.
  { to: '/children', label: 'Records', icon: 'users', roles: ['Administrator', 'Psychologist', 'Staff'] },
  // Same route, role-scoped label/description: admins get full catalog
  // governance, psychologists only manage their agency form templates here
  // (their instrument catalog lives inside the Pre-Assessment wizard, step 4).
  { to: '/instruments', label: 'Instruments & Agency Forms', icon: 'clipboard-pen', roles: ['Administrator'] },
  { to: '/instruments', label: 'Pre-Assessment Instruments', icon: 'file-text', roles: ['Psychologist'] },
  { section: 'Clinical' },
  { to: '/pre-assessment', label: 'Pre-Assessment', icon: 'clipboard-list', roles: ['Psychologist'] },
  { to: '/monitoring', label: 'Progress Monitoring', icon: 'activity', roles: ['Administrator', 'Psychologist', 'Staff'] },
  { to: '/reports', label: 'Results & Reports', icon: 'clipboard-check', roles: ['Administrator', 'Psychologist', 'Staff'] },
  { section: 'Governance' },
  { to: '/reports/summary', label: 'Agency Summary', icon: 'bar-chart-3', roles: ['Administrator', 'Staff'] },
  // Credential Handoffs lives inside User Management as a tab, not its own route.
  { to: '/users', label: 'User Management', icon: 'user-cog', roles: ['Administrator'] },
  // { to: '/samd', label: 'SAMD Readiness', icon: 'shield-check', roles: ['Administrator'] }, // hidden for now, re-enable when ready
  { to: '/settings', label: 'Settings', icon: 'settings', roles: ['Administrator'] },
];

function navForRole(role) {
  const out = [];
  let pending = null;
  for (const item of NAV) {
    if (item.section) { pending = item.section; continue; }
    if (!item.roles.includes(role)) continue;
    if (pending) { out.push({ section: pending }); pending = null; }
    out.push(item);
  }
  return out;
}

export default function Sidebar() {
  const { user } = useAuth();
  const role = user?.role_name || 'Staff';
  const m = ROLE_META[role] || ROLE_META.Staff;
  const items = navForRole(role);

  return (
    <aside style={{ width: 'var(--sidebar-w)', background: 'var(--surface)', borderRight: '1px solid var(--border)', height: '100%', display: 'flex', flexDirection: 'column', flex: 'none' }}>
      <div style={{ padding: '18px 18px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <img src="/racco-seal.jpg" alt="NACC seal" style={{ width: 54, height: 54, borderRadius: '50%', objectFit: 'cover', boxShadow: 'var(--shadow-sm)', flex: 'none' }} />
        <div style={{ lineHeight: 1.12 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 18, color: 'var(--blue-700)' }}>NACC – RACCO 1</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.03em', textTransform: 'uppercase' }}>National Authority for Child Care</div>
        </div>
      </div>

      <nav className="racco-scroll" aria-label="Primary" style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
        {items.map((it, i) =>
          it.section ? (
            <div key={'s' + i} className="racco-eyebrow" style={{ fontSize: 10, padding: '12px 10px 5px' }}>{it.section}</div>
          ) : (
            <NavLink
              key={it.label + it.to}
              to={it.to}
              end={it.end}
              title={it.readonly ? it.label + ' (read-only)' : it.label}
              style={({ isActive }) => ({
                width: '100%', display: 'flex', alignItems: 'center', gap: 11, padding: '8px 11px', marginBottom: 2,
                borderRadius: 'var(--radius-md)', cursor: 'pointer', textAlign: 'left', textDecoration: 'none',
                background: isActive ? m.soft : 'transparent', color: isActive ? m.color : 'var(--text-body)',
                fontFamily: 'var(--font-sans)', fontWeight: isActive ? 700 : 600, fontSize: 14,
                position: 'relative', transition: 'var(--transition-base)',
              })}
              onMouseEnter={(e) => { if (!e.currentTarget.style.background.includes('var')) e.currentTarget.style.background = 'var(--ink-50)'; }}
            >
              {({ isActive }) => (
                <>
                  {isActive && <span style={{ position: 'absolute', left: -12, top: 6, bottom: 6, width: 3, borderRadius: '0 3px 3px 0', background: m.color }} />}
                  <Icon name={it.icon} size={18} />
                  <span style={{ flex: 1 }}>{it.label}</span>
                  {it.readonly && <Icon name="eye" size={14} style={{ opacity: 0.6 }} />}
                </>
              )}
            </NavLink>
          )
        )}
      </nav>
    </aside>
  );
}
