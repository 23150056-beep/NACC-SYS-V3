import { useEffect, useState } from 'react';
import api from '../api/client';
import { exactDate, timeAgo } from '../utils/time';
import { useActivity } from '../context/ActivityContext';
import { useToast } from '../context/ToastContext';
import {
  Card, Button, Alert, Select, FormField, Avatar, EmptyState, Icon, Skeleton,
  ConfirmDialog, RoleAccessPanel,
} from '../ui';

// People who asked for access and are waiting on a decision. Rendered as a
// tab inside User Management (Users.jsx), not its own route.
//
// Two doors lead here — the Google button and the sign-up form at /signup —
// and this screen is the only access control standing behind either. Sign-up
// is open to anyone on the internet, so nothing separates a stranger from
// child case records except an administrator reading a row and clicking
// Approve. Everything here is built around making that click deliberate
// rather than quick, and that now includes saying which door they used: a
// Google address was verified by Google, a typed one was verified by nobody.


const nameOf = (u) => (u.fullname || u.username || u.email || '');

/* Which door, and what it is worth.
 *
 * Google verified the address it handed over (the flow rejects an unverified
 * one). The sign-up form verifies nothing — no confirmation mail is sent, so
 * the address is only what someone typed. An approver deciding whether they
 * recognise this person should not have to guess which of the two they are
 * looking at. */
function DoorChip({ google }) {
  const [label, hint, icon, color] = google
    ? ['Google', 'Address verified by Google.', 'badge-check', 'var(--blue-600)']
    : ['Typed in', 'Signed up with the form. Nobody has verified this address.',
       'keyboard', 'var(--text-muted)'];
  return (
    <span title={hint}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 3,
                   fontSize: 11, fontWeight: 700, color, whiteSpace: 'nowrap' }}>
      <Icon name={icon} size={12} /> {label}
    </span>
  );
}

/* The claimed role, styled so it cannot be mistaken for a settled one.
 * Dashed and quiet, deliberately unlike the solid RoleBadge used everywhere
 * else: if this read as a fact, an administrator skimming the queue would
 * rubber-stamp it, which defeats the entire gate. */
function ClaimChip({ role }) {
  if (!role) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--text-faint)', fontStyle: 'italic' }}>
        didn’t say
      </span>
    );
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 'var(--radius-pill)', border: '1px dashed var(--border-strong)', background: 'transparent', fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
      <Icon name="quote" size={11} style={{ opacity: 0.6 }} />
      asks to be <strong style={{ color: 'var(--text-body)', fontWeight: 700 }}>{role}</strong>
    </span>
  );
}

export default function AccessRequests({ onChange }) {
  const toast = useToast();
  const { refresh: refreshActivity } = useActivity();
  const [rows, setRows] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [confirm, setConfirm] = useState(null);   // { kind, user }
  const [grantRole, setGrantRole] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const r = await api.get('/users/', { params: { include_archived: 'true' } });
      setRows(r.data.filter((u) => u.status === 'pending'));
      setLoadError('');
    } catch (err) {
      setLoadError(err.response?.data?.detail || 'Could not load access requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Administrator is filtered out: approving cannot create one, and the
    // server refuses it anyway. Offering it here would only produce an error.
    api.get('/roles/')
      .then((r) => setRoles(r.data.filter((x) => x.role_name !== 'Administrator')))
      .catch(() => setRoles([]));
  }, []);

  const openApprove = (u) => {
    // Pre-filled from the claim, which is what makes the queue quick — but the
    // administrator's submission is what the server acts on, and it refuses to
    // act at all without one.
    setGrantRole(u.requested_role ? String(u.requested_role) : '');
    setConfirm({ kind: 'approve', user: u });
  };

  const run = async () => {
    const { kind, user: u } = confirm;
    setBusy(true);
    try {
      if (kind === 'approve') {
        await api.post(`/users/${u.id}/approve/`, { role: grantRole });
        const granted = roles.find((r) => String(r.id) === String(grantRole))?.role_name;
        toast.success(`${nameOf(u)} approved as ${granted}`);
      } else {
        await api.post(`/users/${u.id}/decline/`);
        toast.success(`Request from ${nameOf(u)} declined`);
      }
      setConfirm(null);
      await load();
      refreshActivity();
      onChange?.();
    } catch (err) {
      const body = err.response?.data;
      toast.error(body?.role || body?.detail || 'That did not go through. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const TH = { textAlign: 'left', padding: '11px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap', background: 'var(--surface)', borderBottom: '1px solid var(--border)' };
  const TD = { padding: '13px 16px', fontSize: 13, color: 'var(--text-body)', verticalAlign: 'middle' };

  const granting = confirm?.kind === 'approve'
    ? roles.find((r) => String(r.id) === String(grantRole))
    : null;
  const claimed = confirm?.user?.requested_role_name || null;

  return (
    <>
      <Alert tone="warning" icon={<Icon name="shield-alert" size={18} />} style={{ marginBottom: 16 }}>
        Anyone on the internet can send a request — with a Google account or
        the sign-up form. Approving one is what grants access to child case
        records, so approve only people you know work here, and set the role
        yourself rather than trusting what they typed.
      </Alert>

      <Card padding="0">
        {loadError ? (
          <div style={{ padding: 20 }}>
            <Alert tone="danger" title="Requests could not be loaded" icon={<Icon name="wifi-off" size={18} />}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
                <span>{loadError} Nothing has been changed.</span>
                <Button variant="secondary" size="sm" onClick={() => { setLoading(true); load(); }} iconLeft={<Icon name="refresh-cw" size={15} />}>Try again</Button>
              </div>
            </Alert>
          </div>
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 780, borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Person', 'They say they are', 'Requested', ''].map((h, i) => (
                    <th key={h || i} scope="col" style={TH}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading && Array.from({ length: 3 }).map((_, i) => (
                  <tr key={`sk-${i}`} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={TD}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                        <Skeleton width={30} height={30} radius="50%" />
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                          <Skeleton width="46%" height={11} />
                          <Skeleton width="66%" height={9} />
                        </div>
                      </div>
                    </td>
                    <td style={TD}><Skeleton width={124} height={18} radius="var(--radius-pill)" /></td>
                    <td style={TD}><Skeleton width={70} height={11} /></td>
                    <td style={TD}><Skeleton width={150} height={30} radius="var(--radius-sm)" /></td>
                  </tr>
                ))}

                {!loading && rows.map((u) => (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={TD}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
                        <Avatar name={nameOf(u)} tone="neutral" size="sm" />
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{nameOf(u)}</div>
                          <div className="racco-mono" style={{ fontSize: 11.5, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.email}</div>
                          <DoorChip google={!!u.google_linked} />
                        </div>
                      </div>
                    </td>
                    <td style={TD}><ClaimChip role={u.requested_role_name} /></td>
                    <td style={{ ...TD, whiteSpace: 'nowrap' }} title={exactDate(u.created_at)}>{timeAgo(u.created_at)}</td>
                    <td style={{ ...TD, textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: 8 }}>
                        <Button variant="ghost" size="sm" style={{ color: 'var(--red-600)' }} onClick={() => setConfirm({ kind: 'decline', user: u })}>Decline</Button>
                        <Button variant="primary" size="sm" iconLeft={<Icon name="user-check" size={15} />} onClick={() => openApprove(u)}>Approve</Button>
                      </div>
                    </td>
                  </tr>
                ))}

                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ padding: 0 }}>
                      <EmptyState
                        icon={<Icon name="inbox" size={24} />}
                        title="No one is waiting"
                        description="When a staff member or psychologist asks for access — with Google or the sign-up form — their request appears here for you to approve."
                      />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {confirm?.kind === 'approve' && (
        <ConfirmDialog
          onClose={() => setConfirm(null)} onConfirm={run} busy={busy || !grantRole}
          tone="brand" icon={<Icon name="user-check" size={19} />}
          title={`Give ${nameOf(confirm.user)} access?`}
          description={`They will be able to sign in with ${confirm.user.email} and see everything the role below allows.`}
          confirmLabel="Approve" cancelLabel="Cancel"
        >
          <FormField
            label="Role to grant"
            hint={claimed
              ? `They asked for ${claimed}. Set what is actually correct — this is your decision, not theirs.`
              : 'They did not say what they do. Choose the role that matches their work.'}
          >
            <Select value={grantRole} onChange={(e) => setGrantRole(e.target.value)}>
              <option value="">— Select role —</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.role_name}</option>)}
            </Select>
          </FormField>
          {/* The same panel User Management shows when a role is corrected, so
              "what does this role mean?" has one answer in both places. */}
          <RoleAccessPanel to={granting?.role_name || null} />
          {granting?.role_name === 'Psychologist' && (
            <Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />}>
              That includes clinical interviews, assessment results and uploaded
              reports for the children assigned to them.
            </Alert>
          )}
        </ConfirmDialog>
      )}

      {confirm?.kind === 'decline' && (
        <ConfirmDialog
          onClose={() => setConfirm(null)} onConfirm={run} busy={busy}
          tone="danger" icon={<Icon name="user-x" size={19} />}
          title={`Decline ${nameOf(confirm.user)}?`}
          description="They will not be able to sign in, and this address cannot send another request. If you decline someone by mistake, an administrator can still create their account by hand."
          confirmLabel="Decline" cancelLabel="Cancel"
        />
      )}
    </>
  );
}
