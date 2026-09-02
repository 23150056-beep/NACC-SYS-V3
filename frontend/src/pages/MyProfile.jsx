import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  Card, Button, Badge, Alert, Input, FormField, Avatar, RoleBadge, Icon,
  RoleAccessPanel, Skeleton, EmptyState, PAGE, hoverLift,
} from '../ui';
import { eventText, eventDestination } from '../components/Topbar';
import { exactDate, shortDate, timeAgo } from '../utils/time';
import api from '../api/client';

/* Your own account, on one page.
 *
 * Two columns, the shape most people already know from a social profile: who
 * you are on the left, what you have been doing on the right. That is not
 * decoration — the left column is stable reference (role, contact, how you
 * sign in) and the right is a stream, and they want different reading.
 *
 * Everything on the right is REAL, from endpoints a Staff or Psychologist
 * account can already call: /api/activity/ (already scoped per role by the
 * server), /api/children/ (scoped to a psychologist's assigned children) and
 * /api/appointments/ (scoped to their own). Nothing new was needed on the
 * server to make this page worth opening.
 *
 * The "Optional details" card is the one part that is still a prototype
 * (product decision 2026-07-18) and it says so, both on the card and on the
 * button that saves it. Those four values live in this browser's
 * localStorage and reach no server. docs: see the note at the bottom of this
 * file for what making them real would take.
 */

const EMPTY = { facebook: '', twitter: '', instagram: '', address: '' };

const FIELDS = [
  ['facebook', 'Facebook', 'facebook', 'facebook.com/your.name'],
  ['twitter', 'X (Twitter)', 'twitter', 'x.com/yourhandle'],
  ['instagram', 'Instagram', 'instagram', 'instagram.com/yourhandle'],
  ['address', 'Home address', 'map-pin', 'House No., Street, Barangay, City, Province'],
];

/* One row of the Intro card. Renders the dash rather than collapsing when a
 * value is missing: "not recorded" is information, and a row that disappears
 * makes two accounts look structurally different when they are not. */
function Fact({ icon, label, children, mono = false }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                     width: 30, height: 30, flex: 'none', borderRadius: 'var(--radius-sm)',
                     background: 'var(--blue-50)', color: 'var(--blue-600)' }}>
        <Icon name={icon} size={15} />
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.05em',
                      textTransform: 'uppercase', color: 'var(--text-faint)' }}>{label}</div>
        <div className={mono ? 'racco-mono' : undefined}
             style={{ fontSize: mono ? 12.5 : 13.5, color: 'var(--text-body)',
                      lineHeight: 1.5, overflowWrap: 'anywhere' }}>
          {children || <span style={{ color: 'var(--text-faint)' }}>Not recorded</span>}
        </div>
      </div>
    </div>
  );
}

export default function MyProfile() {
  const { user } = useAuth();
  const toast = useToast();
  const role = user?.role_name;
  const isPsych = role === 'Psychologist';

  const storageKey = `nacc-profile-demo:${user?.id ?? 'anon'}`;
  const [form, setForm] = useState(EMPTY);
  const [saved, setSaved] = useState(EMPTY);
  const [children, setChildren] = useState(null);
  const [appointments, setAppointments] = useState(null);
  const [activity, setActivity] = useState(null);

  useEffect(() => {
    let stored = EMPTY;
    try { stored = { ...EMPTY, ...JSON.parse(localStorage.getItem(storageKey) || '{}') }; }
    catch { stored = EMPTY; }
    setForm(stored);
    setSaved(stored);
  }, [storageKey]);

  useEffect(() => {
    // Each fails independently: a psychologist with no caseload yet should
    // still get their activity, and vice versa.
    api.get('/children/').then((r) => setChildren(r.data)).catch(() => setChildren([]));
    api.get('/appointments/').then((r) => setAppointments(r.data)).catch(() => setAppointments([]));
    api.get('/activity/').then((r) => setActivity(r.data)).catch(() => setActivity([]));
  }, []);

  const dirty = useMemo(
    () => FIELDS.some(([k]) => (form[k] || '') !== (saved[k] || '')), [form, saved]);
  const hasDetails = useMemo(() => FIELDS.some(([k]) => (saved[k] || '').trim()), [saved]);

  const stats = useMemo(() => {
    if (children === null || appointments === null) return null;
    const active = children.filter((c) => c.status !== 'archived'
      && (c.case_status || 'active') !== 'inactive');
    const now = new Date();
    const weekEnd = new Date(now); weekEnd.setDate(now.getDate() + 7);
    const upcoming = appointments.filter((a) => {
      const at = new Date(a.scheduled_at || a.start || a.date);
      return a.status !== 'cancelled' && at >= now && at <= weekEnd;
    });
    const done = appointments.filter((a) => a.status === 'completed');
    return { active: active.length, upcoming: upcoming.length, done: done.length };
  }, [children, appointments]);

  const save = (e) => {
    e.preventDefault();
    try { localStorage.setItem(storageKey, JSON.stringify(form)); }
    catch { toast.error('This browser would not store the details (private mode?).'); return; }
    setSaved(form);
    toast.success('Saved in this browser. Not sent to the system.');
  };

  const clear = () => {
    try { localStorage.removeItem(storageKey); } catch { /* nothing to remove */ }
    setForm(EMPTY);
    setSaved(EMPTY);
    toast.success('Details cleared from this browser.');
  };

  return (
    <div style={{ ...PAGE, maxWidth: 1080 }}>

      {/* ---------------------------- header ---------------------------- */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)',
                    overflow: 'hidden', marginBottom: 18 }}>
        {/* The same gradient as the sign-in page, so the account screen and the
            door you came through belong to one system. */}
        <div style={{ height: 132, position: 'relative',
                      background: 'linear-gradient(155deg, var(--blue-700), var(--blue-600) 60%, var(--blue-800))' }}>
          <div style={{ position: 'absolute', inset: 0,
                        background: 'radial-gradient(120% 120% at 100% 0%, rgba(255,172,42,0.24), transparent 55%)' }} />
        </div>
        {/* Only the avatar crosses the cover line. An earlier version let the
            whole row overlap, which put dark heading text on the blue and made
            the name unreadable — the thing the header exists to show. */}
        <div style={{ padding: '0 26px 22px' }}>
          <div style={{ marginTop: -46, marginBottom: 12, position: 'relative', zIndex: 1 }}>
            <span style={{ display: 'inline-block', borderRadius: '50%', padding: 4,
                           background: 'var(--surface)', boxShadow: 'var(--shadow-md)' }}>
              <Avatar name={user?.fullname || user?.username || 'User'} tone="brand" size="lg" />
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                        gap: 16, flexWrap: 'wrap' }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 24,
                            lineHeight: 1.15, color: 'var(--text-strong)' }}>
                {user?.fullname || user?.username}
              </div>
              <div className="racco-mono" style={{ fontSize: 12.5, color: 'var(--text-muted)',
                                                   marginTop: 3, overflowWrap: 'anywhere' }}>
                {user?.email}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', paddingTop: 3 }}>
              {role && <RoleBadge role={role} solid />}
              <Badge tone={user?.google_linked ? 'brand' : 'neutral'} size="sm">
                <Icon name={user?.google_linked ? 'badge-check' : 'key-round'} size={12} />
                {user?.google_linked ? 'Google' : 'Password'}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* --------------------------- two columns -------------------------- */}
      <div className="racco-profile-grid">

        {/* ----------------------------- left ----------------------------- */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          <Card eyebrow="Account" title="Intro" padding="20px">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 4 }}>
              <Fact icon="mail" label="Email" mono>{user?.email}</Fact>
              <Fact icon="phone" label="Contact number">{user?.contact_details}</Fact>
              <Fact icon={user?.google_linked ? 'badge-check' : 'key-round'} label="Signs in with">
                {user?.google_linked
                  ? 'Google — this address, verified by Google'
                  : 'Email and password'}
              </Fact>
              <Fact icon="clock" label="Last sign-in">
                {user?.last_login
                  ? <span title={exactDate(user.last_login)}>{timeAgo(user.last_login)}</span>
                  : null}
              </Fact>
              <Fact icon="history" label="Member since">
                {user?.created_at ? shortDate(user.created_at) : null}
              </Fact>
            </div>
            {role && (
              <div style={{ marginTop: 16 }}>
                <RoleAccessPanel to={role} />
              </div>
            )}
            <div style={{ fontSize: 12, lineHeight: 1.55, color: 'var(--text-faint)', marginTop: 12 }}>
              Your name, email and role are set by an administrator. Ask them if
              any of this is wrong.
            </div>
          </Card>

          {/* The prototype. Flagged on the card, on the save button, and under
              the form — three places, because someone who fills this in and
              expects it on their account will be disappointed on a different
              machine. */}
          <Card
            padding="20px"
            eyebrow="Optional details"
            title={(
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
                Social &amp; address
                <Badge tone="warning" size="sm"><Icon name="flask-conical" size={12} />Prototype</Badge>
              </span>
            )}
          >
            <form onSubmit={save} style={{ display: 'flex', flexDirection: 'column', gap: 13, marginTop: 6 }}>
              {FIELDS.map(([key, label, icon, placeholder]) => (
                <FormField key={key} label={label}>
                  <Input
                    value={form[key]} placeholder={placeholder}
                    leading={<Icon name={icon} size={16} />}
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  />
                </FormField>
              ))}
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
                <Button type="submit" variant="primary" size="sm" disabled={!dirty}
                        iconLeft={<Icon name="save" size={15} />}>
                  {dirty ? 'Save in this browser' : 'Saved'}
                </Button>
                {hasDetails && (
                  <Button type="button" variant="ghost" size="sm" onClick={clear}
                          style={{ color: 'var(--red-600)' }}
                          iconLeft={<Icon name="trash-2" size={15} />}>
                    Clear
                  </Button>
                )}
              </div>
            </form>
            <Alert tone="warning" icon={<Icon name="flask-conical" size={17} />} style={{ marginTop: 14 }}>
              These four stay in <strong>this browser only</strong>. They are not
              on your account, no administrator can see them, and they are gone
              if you use another computer or clear your browsing data. Clear
              removes them for good.
            </Alert>
          </Card>
        </div>

        {/* ----------------------------- right ---------------------------- */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>

          <div>
            <div className="racco-eyebrow" style={{ marginBottom: 10 }}>At a glance</div>
            <div className="racco-profile-stats">
              {stats === null ? (
                [0, 1, 2].map((i) => <Skeleton key={i} height={96} radius="var(--radius-lg)" />)
              ) : (
                <>
                  <StatTile icon="folder-heart" tone="brand" value={stats.active}
                            label={isPsych ? 'Children assigned to you' : 'Active records'}
                            hint={isPsych ? 'Open cases you are responsible for' : 'Cases you can work on'} />
                  <StatTile icon="calendar-clock" tone="amber" value={stats.upcoming}
                            label="Sessions in the next 7 days"
                            hint={isPsych ? 'Booked with you' : 'Across the office'} />
                  <StatTile icon="check" tone="success" value={stats.done}
                            label="Sessions completed"
                            hint={isPsych ? 'Marked complete by you' : 'Marked complete'} />
                </>
              )}
            </div>
          </div>

          <Card eyebrow="Your account" title="Recent activity" padding="0">
            {activity === null && (
              <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[0, 1, 2, 3].map((i) => <Skeleton key={i} height={16} />)}
              </div>
            )}
            {activity !== null && activity.length === 0 && (
              <EmptyState
                icon={<Icon name="history" size={24} />}
                title="Nothing yet"
                description={isPsych
                  ? 'Assignments and updates on your cases will appear here.'
                  : 'Records you add or edit will appear here.'}
              />
            )}
            {activity !== null && activity.length > 0 && (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                {activity.slice(0, 12).map((e) => (
                  <li key={e.id} style={{ borderTop: '1px solid var(--ink-100)' }}>
                    <Link
                      to={eventDestination(e, role)}
                      {...hoverLift({ lift: 0 })}
                      style={{ display: 'flex', gap: 12, padding: '13px 20px',
                               textDecoration: 'none', color: 'inherit', alignItems: 'flex-start' }}
                    >
                      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                     width: 30, height: 30, flex: 'none', marginTop: 1,
                                     borderRadius: 'var(--radius-sm)',
                                     background: 'var(--ink-50)', color: 'var(--text-muted)' }}>
                        <Icon name={e.action === 'created' ? 'plus'
                          : e.action === 'archived' ? 'archive'
                            : e.action === 'login' ? 'log-in' : 'pencil'} size={14} />
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontSize: 13.5, fontWeight: 600,
                                       color: 'var(--text-strong)', overflowWrap: 'anywhere' }}>
                          {eventText(e)}
                        </span>
                        <span style={{ display: 'block', fontSize: 11.5, color: 'var(--text-faint)', marginTop: 2 }}
                              title={exactDate(e.created_at)}>
                          {e.actor_label} · {timeAgo(e.created_at)}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

/* A stat that fits three-up in a column, so StatCard's roomier padding would
 * push the row past the fold on a laptop. */
function StatTile({ icon, tone, value, label, hint }) {
  const colors = { brand: 'var(--blue-600)', amber: 'var(--amber-600)', success: 'var(--success-600)' };
  const soft = { brand: 'var(--blue-50)', amber: 'var(--amber-50)', success: 'var(--success-50)' };
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)',
                  padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                     width: 30, height: 30, borderRadius: 'var(--radius-sm)',
                     background: soft[tone], color: colors[tone] }}>
        <Icon name={icon} size={16} />
      </span>
      <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 27,
                     lineHeight: 1, color: 'var(--text-strong)', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
      <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-body)', lineHeight: 1.35 }}>
        {label}
      </span>
      <span style={{ fontSize: 11.5, color: 'var(--text-faint)', lineHeight: 1.4 }}>{hint}</span>
    </div>
  );
}
