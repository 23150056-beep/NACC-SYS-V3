import React, { useEffect, useState } from 'react';
import api from '../api/client';
import { useToast } from '../context/ToastContext';
import { Card, Button, Badge, Alert, EmptyState, Avatar, RoleBadge, Icon, iconBtn, hoverLift } from '../ui';

// Admin-only list of everyone still on a temporary password (must_change_password),
// i.e. every account whose credentials still need to be handed over physically.
// Passwords are generated fresh at the moment of handoff (via the existing
// reset-password endpoint) and live ONLY in this component's state until the
// page is refreshed — the server never stores a plaintext password.
// Rendered as a tab inside User Management (Users.jsx), not its own route.
export default function CredentialHandoffs() {
  const toast = useToast();
  const [users, setUsers] = useState([]);
  const [generated, setGenerated] = useState({}); // { userId: tempPassword }
  const [busy, setBusy] = useState(false);

  const load = () => api.get('/users/').then((r) => setUsers(r.data.filter((u) => u.must_change_password)));
  useEffect(() => { load(); }, []);

  const generate = async (u) => {
    try {
      const { data } = await api.post(`/users/${u.id}/reset-password/`);
      setGenerated((g) => ({ ...g, [u.id]: data.temp_password }));
      return true;
    } catch (err) {
      toast.error(err.response?.data?.detail || `Could not generate a password for ${u.fullname || u.email}.`);
      return false;
    }
  };

  const generateAll = async () => {
    setBusy(true);
    // Sequential on purpose: predictable order, no burst of parallel writes.
    for (const u of users) await generate(u);
    setBusy(false);
  };

  const copyPassword = (u) => {
    navigator.clipboard.writeText(generated[u.id]);
    toast.success(`Password for ${u.fullname || u.email} copied.`);
  };

  const slips = users.filter((u) => generated[u.id]);
  const th = { textAlign: 'left', padding: '12px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' };

  return (
    <>
      <div className="racco-no-print">
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginBottom: 16 }}>
          <Button variant="secondary" disabled={busy || users.length === 0} onClick={generateAll} iconLeft={<Icon name="key-round" size={16} />}>
            {busy ? 'Generating…' : 'Generate All'}
          </Button>
          <Button variant="primary" disabled={slips.length === 0} onClick={() => window.print()} iconLeft={<Icon name="printer" size={16} />}>
            Print Slips{slips.length > 0 ? ` (${slips.length})` : ''}
          </Button>
        </div>

        <Alert tone="info" icon={<Icon name="shield-check" size={18} />} style={{ marginBottom: 16 }}>
          These accounts are still waiting for their password handoff. Generate a fresh temporary
          password at the moment you hand it over — passwords exist only on this screen until you
          refresh, and are never stored by the system. Each user must set their own password at
          first login, after which they disappear from this list.
        </Alert>

        <Card padding="0">
          {users.length === 0 ? (
            <EmptyState icon={<Icon name="check-circle-2" size={24} />} title="No pending handoffs" description="Everyone has set their own password. New accounts will appear here automatically." />
          ) : (
            <div className="racco-scroll" style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', minWidth: 720, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                    {['Name', 'Email', 'Role', 'Temporary Password', 'Actions'].map((h) => <th key={h} scope="col" style={th}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                          <Avatar name={u.fullname || u.email} tone="amber" size="sm" />
                          <span style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{u.fullname || u.username}</span>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-body)' }} className="racco-mono">{u.email}</td>
                      <td style={{ padding: '12px 16px' }}>{u.role_name ? <RoleBadge role={u.role_name} /> : '—'}</td>
                      <td style={{ padding: '12px 16px' }}>
                        {generated[u.id]
                          ? <span className="racco-mono" style={{ fontSize: 14.5, fontWeight: 700, color: 'var(--text-strong)', letterSpacing: '0.04em' }}>{generated[u.id]}</span>
                          : <Badge tone="amber" size="sm" dot>Awaiting handoff</Badge>}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button title={generated[u.id] ? 'Regenerate password' : 'Generate password'} aria-label={`Generate password for ${u.fullname || u.email}`}
                            onClick={() => generate(u)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--amber-500)')}>
                            <Icon name={generated[u.id] ? 'rotate-ccw' : 'key-round'} size={15} />
                          </button>
                          {generated[u.id] && (
                            <button title="Copy password" aria-label={`Copy password for ${u.fullname || u.email}`}
                              onClick={() => copyPassword(u)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--blue-600)')}>
                              <Icon name="copy" size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Printable slips — one cut-out per generated password. Visible only in
          print (racco-print-only); index.css already hides the app chrome. */}
      <div className="racco-print-only" style={{ padding: 8 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {slips.map((u) => (
            <div key={u.id} style={{ border: '1.5px dashed #94a3b8', borderRadius: 8, padding: '14px 16px', breakInside: 'avoid' }}>
              <div style={{ fontWeight: 800, fontSize: 13, color: '#1d4ed8' }}>NACC – RACCO 1</div>
              <div style={{ fontSize: 10.5, color: '#64748b', marginBottom: 8 }}>Temporary account credentials — keep this slip private</div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{u.fullname || u.username}</div>
              <div style={{ fontFamily: 'monospace', fontSize: 12, color: '#334155' }}>{u.email}</div>
              <div style={{ fontFamily: 'monospace', fontSize: 17, fontWeight: 700, letterSpacing: '0.06em', margin: '8px 0', padding: '6px 10px', border: '1px solid #cbd5e1', borderRadius: 6, display: 'inline-block' }}>
                {generated[u.id]}
              </div>
              <div style={{ fontSize: 10.5, color: '#64748b', lineHeight: 1.5 }}>
                Sign in with this password — you will be required to set your own
                password immediately. Destroy this slip after use.
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
