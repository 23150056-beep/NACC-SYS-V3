import React, { useEffect, useState } from 'react';
import api from '../api/client';
import { useActivity } from '../context/ActivityContext';
import { Card, Button, Badge, Alert, Input, Select, FormField, Avatar, RoleBadge, EmptyState, Icon, iconBtn, hoverLift, PAGE, Tabs } from '../ui';
import { useToast } from '../context/ToastContext';
import CredentialHandoffs from './CredentialHandoffs';

// No password field: the server generates a temporary password on create and
// returns it exactly once — admins never choose another user's password.
const EMPTY = { email: '', first_name: '', last_name: '', middle_initial: '', contact_details: '', role: '' };

export default function Users() {
  const [tab, setTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState('');
  // Holds { user, temp_password } while the just-generated temp password is
  // on screen. Closing the modal discards it for good — the API never
  // returns it again, so there is nothing to keep in state afterward.
  const [resetResult, setResetResult] = useState(null);
  const { refresh: refreshActivity } = useActivity();
  const toast = useToast();

  const load = () => api.get('/users/').then((r) => setUsers(r.data));
  useEffect(() => {
    load();
    api.get('/roles/').then((r) => setRoles(r.data));
  }, []);

  const openCreate = () => { setError(''); setForm({ ...EMPTY }); };
  const openEdit = (u) => { setError(''); setForm({ ...EMPTY, ...u }); };

  const save = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const payload = { ...form };
      delete payload.role_name; delete payload.fullname;
      delete payload.must_change_password; delete payload.admin_takeover_pending;
      if (form.id) {
        await api.put(`/users/${form.id}/`, payload);
        toast.success('User updated');
      } else {
        const { data } = await api.post('/users/', payload);
        toast.success('User added');
        // Same one-time display contract as reset: show the generated temp
        // password now — the server can never show it again.
        setResetResult({ user: data, temp_password: data.temp_password });
      }
      setForm(null);
      load();
      refreshActivity();
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Save failed'));
      toast.error('Could not save the user. Please try again.');
    }
  };

  const archive = async (u) => {
    if (!window.confirm(`Deactivate ${u.fullname || u.email}?`)) return;
    try {
      await api.post(`/users/${u.id}/archive/`);
      toast.success(`${u.fullname || u.email} deactivated`);
      load();
      refreshActivity();
    } catch (err) {
      toast.error('Could not deactivate the user.');
    }
  };

  const resetPassword = async (u) => {
    if (!window.confirm(`Issue a new temporary password for ${u.fullname || u.email}? Their current password will stop working immediately.`)) return;
    try {
      const { data } = await api.post(`/users/${u.id}/reset-password/`);
      setResetResult({ user: u, temp_password: data.temp_password });
      refreshActivity();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not reset the password.');
    }
  };

  const copyTempPassword = () => {
    if (!resetResult) return;
    navigator.clipboard.writeText(resetResult.temp_password);
    toast.success('Temporary password copied to clipboard.');
  };

  const toneFor = (role) => (role === 'Administrator' ? 'brand' : role === 'Psychologist' ? 'red' : 'amber');

  const pendingHandoffs = users.filter((u) => u.must_change_password).length;

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      <Tabs
        tabs={[
          { id: 'users', label: 'Users' },
          { id: 'handoffs', label: 'Credential Handoffs', count: pendingHandoffs || undefined },
        ]}
        active={tab}
        onChange={setTab}
        style={{ marginBottom: 16 }}
      />

      {tab === 'handoffs' ? (
        <CredentialHandoffs />
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Button variant="primary" onClick={openCreate} iconLeft={<Icon name="user-plus" size={17} />}>Add User</Button>
          </div>

          <Card padding="0">
            {users.length === 0 ? (
              <EmptyState icon={<Icon name="users" size={24} />} title="No users yet" description="Add agency accounts to get started." />
            ) : (
              <div className="racco-scroll" style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: 680, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                      {['Name', 'Email', 'Contact', 'Role', 'Actions'].map((h) => (
                        <th key={h} scope="col" style={{ textAlign: 'left', padding: '12px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                            <Avatar name={u.fullname || u.username || u.email} tone={toneFor(u.role_name)} size="sm" />
                            <span style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{u.fullname || u.username}</span>
                          </div>
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-body)' }} className="racco-mono">{u.email}</td>
                        <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-muted)' }} className="racco-mono">{u.contact_details || '—'}</td>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                            {u.role_name ? <RoleBadge role={u.role_name} /> : '—'}
                            {u.admin_takeover_pending && <Badge tone="warning" size="sm" dot>Takeover pending</Badge>}
                          </div>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button title="Edit user" aria-label={`Edit ${u.fullname || u.email}`} onClick={() => openEdit(u)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--blue-600)')}><Icon name="pencil" size={15} /></button>
                            {/* Archived users never appear in this list (see load()), but guard
                                anyway in case a future view surfaces them here too. */}
                            <button title="Reset password" aria-label={`Reset password for ${u.fullname || u.email}`} disabled={u.status === 'archived'} onClick={() => resetPassword(u)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={{ ...iconBtn('var(--amber-500)'), ...(u.status === 'archived' ? { opacity: 0.4, cursor: 'not-allowed' } : {}) }}><Icon name="key-round" size={15} /></button>
                            <button title="Deactivate user" aria-label={`Deactivate ${u.fullname || u.email}`} onClick={() => archive(u)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--red-500)')}><Icon name="user-x" size={15} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {form && (
        <div onClick={() => setForm(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.32)', display: 'flex', justifyContent: 'flex-end', zIndex: 70, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
          <form onSubmit={save} onClick={(e) => e.stopPropagation()} style={{ width: 420, maxWidth: '92%', height: '100%', background: 'var(--surface)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', animation: 'racco-slide-left var(--dur-slow) var(--ease-out)' }}>
            <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--ink-50)' }}>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>{form.id ? 'Edit User' : 'Add User'}</div>
              <button type="button" onClick={() => setForm(null)} aria-label="Close" {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--text-muted)')}><Icon name="x" size={17} /></button>
            </div>
            <div className="racco-scroll" style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              {error && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />}>{error}</Alert>}
              {[['first_name', 'First Name'], ['middle_initial', 'Middle Initial'], ['last_name', 'Last Name'], ['email', 'Email'], ['contact_details', 'Contact Details']].map(([k, label]) => (
                <FormField key={k} label={label}>
                  <Input value={form[k] || ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} type={k === 'email' ? 'email' : 'text'} />
                </FormField>
              ))}
              {/* A role cannot be changed once assigned (adviser). */}
              {form.id && form.role ? (
                <FormField label="Role" hint="A role cannot be changed once it has been assigned.">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 42, padding: '0 13px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)', color: 'var(--text-strong)', fontWeight: 700, fontSize: 14 }}>
                    {form.role_name || roles.find((r) => String(r.id) === String(form.role))?.role_name || '—'}
                    <Icon name="lock" size={13} style={{ color: 'var(--text-faint)', marginLeft: 'auto' }} />
                  </div>
                </FormField>
              ) : (
                <FormField label="Role">
                  <Select value={form.role || ''} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                    <option value="">— Select role —</option>
                    {roles.map((r) => <option key={r.id} value={r.id}>{r.role_name}</option>)}
                  </Select>
                </FormField>
              )}
              {/* Single-admin handover warning (product decision 2026-07-18). */}
              {!form.id && roles.find((r) => String(r.id) === String(form.role))?.role_name === 'Administrator' && (
                <Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />}>
                  Admin handover: when this new administrator logs in for the
                  first time, every other administrator account — including
                  yours — is deactivated immediately. A deactivated
                  administrator can only return with a brand-new account.
                </Alert>
              )}
              {!form.id && (
                <Alert tone="info" icon={<Icon name="key-round" size={18} />}>
                  A temporary password is generated automatically when you save.
                  It is shown once — hand it to the user, and they must set their
                  own password at first login.
                </Alert>
              )}
            </div>
            <div style={{ padding: 16, borderTop: '1px solid var(--border)' }}>
              <Button type="submit" variant="primary" fullWidth iconLeft={<Icon name="save" size={16} />}>Save User</Button>
            </div>
          </form>
        </div>
      )}

      {resetResult && (
        <div onClick={() => setResetResult(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 80, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 440, maxWidth: '92%', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>Temporary Password</div>
                <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{resetResult.user.fullname || resetResult.user.email}</div>
              </div>
              <button type="button" onClick={() => setResetResult(null)} aria-label="Close" {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--text-muted)')}><Icon name="x" size={17} /></button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
              <span className="racco-mono" style={{ flex: 1, fontSize: 17, fontWeight: 700, color: 'var(--text-strong)', letterSpacing: '0.04em' }}>{resetResult.temp_password}</span>
              <button type="button" title="Copy" aria-label="Copy temporary password" onClick={copyTempPassword} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--blue-600)')}><Icon name="copy" size={15} /></button>
            </div>
            <Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />}>
              Give this to the user — they'll be required to set a new password at next login.
              This password will not be shown again; generate a new one if it's lost.
            </Alert>
            <Button type="button" variant="secondary" fullWidth onClick={() => setResetResult(null)}>Done</Button>
          </div>
        </div>
      )}
    </div>
  );
}
