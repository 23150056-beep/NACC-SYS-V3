import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useAuth } from '../context/AuthContext';
import { StatCard, Button, Badge, Icon, ROLE_META } from '../ui';
import api from '../api/client';
import { useActivity } from '../context/ActivityContext';
import { eventText, timeAgo, eventDestination } from '../components/Topbar';
import MiniCalendar from '../components/MiniCalendar';

const EMPTY = {
  census: { active: 0, inactive: 0, by_case_type: {}, by_case_status: {} },
  total_children: 0, unassessed: 0, pending_pre_assessments: 0,
  today_schedule: [], availability_today: [], intake_vs_termination: [],
  trend: [], per_psychologist: [], by_case_type: {}, care_gaps: [],
  counseling_per_psychologist: [],
};
const PURPOSE_LABEL = { pre_assessment: 'Pre-Assessment', session: 'Session', follow_up: 'Follow-up' };
const GAP_TONE = { danger: 'var(--red-500)', warning: 'var(--amber-500)', info: 'var(--blue-400)' };

// Self-contained tile: mirrors Card's visual chrome (border/shadow/radius/eyebrow/title
// tokens) but owns its own header + scroll-body divs directly, rather than nesting a
// scrolling child inside Card's opaque content wrapper. Card's internal `<div style={{padding}}>`
// has neither `min-height: 0` nor non-visible overflow, so a `flex:1` scroll child dropped
// inside it hits the classic flexbox "won't shrink below content size" trap and never
// actually scrolls — it just grows the tile past the grid row instead. Owning the whole
// chain here lets `minHeight: 0` genuinely take effect on the scrolling element.
const Tile = ({ eyebrow, title, span = 1, actions = null, children, style = {} }) => (
  <div style={{
    background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-sm)', overflow: 'hidden', position: 'relative',
    gridColumn: `span ${span}`, minHeight: 0, display: 'flex', flexDirection: 'column', ...style,
  }}>
    <div style={{ flex: 'none', padding: '13px 14px 0', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
      <div>
        {eyebrow && <div className="racco-eyebrow" style={{ marginBottom: 3 }}>{eyebrow}</div>}
        {title && <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-strong)', margin: 0 }}>{title}</h3>}
      </div>
      {actions}
    </div>
    <div className="racco-scroll" style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', padding: 14 }}>
      {children}
    </div>
  </div>
);

// Census range selector: label → backend `range` value (reports.bucket).
const RANGES = [
  ['Weekly', 'weekly'],
  ['Monthly', 'monthly'],
  ['Quarterly', 'quarterly'],
  ['Annual', 'yearly'],
];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const role = user?.role_name || 'Staff';
  const isPsychologist = role === 'Psychologist';
  const m = ROLE_META[role] || ROLE_META.Staff;
  const [stats, setStats] = useState(EMPTY);
  const [range, setRange] = useState('monthly');
  const [appointments, setAppointments] = useState([]);
  const { events } = useActivity();
  const feed = events.slice(0, 15);

  useEffect(() => {
    api.get(`/reports/dashboard/?range=${range}`).then((r) => setStats({ ...EMPTY, ...r.data })).catch(() => setStats(EMPTY));
  }, [range]);

  useEffect(() => {
    api.get('/appointments/').then((r) => setAppointments(r.data)).catch(() => {});
  }, []);

  const census = stats.census || EMPTY.census;
  const caseMix = Object.entries(census.by_case_type || {});
  const sessionsThisPeriod = (stats.trend || []).reduce((sum, t) => sum + t.count, 0);
  const gaps = stats.care_gaps || [];

  const actions = [
    { label: 'Records', icon: 'folder-heart', variant: 'secondary', to: '/children', roles: ['Administrator', 'Psychologist', 'Staff'] },
    { label: 'Start Pre-Assessment', icon: 'clipboard-list', variant: 'primary', to: '/pre-assessment', roles: ['Psychologist'] },
    { label: 'Calendar', icon: 'calendar', variant: 'secondary', to: '/schedule', roles: ['Administrator', 'Psychologist', 'Staff'] },
    { label: 'Agency Summary', icon: 'bar-chart-3', variant: 'primary', to: '/reports/summary', roles: ['Administrator', 'Staff'] },
  ].filter((a) => a.roles.includes(role));

  return (
    <div style={{ padding: '14px 20px', height: 'calc(100vh - var(--topbar-h, 64px))', display: 'flex', flexDirection: 'column', gap: 10, overflow: 'hidden auto' }}>
      {/* Row 1 — slim quick actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', flex: 'none' }}>
        <span style={{ width: 28, height: 28, borderRadius: 'var(--radius-md)', background: m.soft, color: m.color, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}><Icon name="sparkles" size={15} /></span>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 14, color: 'var(--text-strong)', marginRight: 4 }}>Quick actions</span>
        {actions.map((a) => (
          <Button key={a.label} variant={a.variant} onClick={() => navigate(a.to)} iconLeft={<Icon name={a.icon} size={16} />}>{a.label}</Button>
        ))}
      </div>

      {/* Row 2 — census stat tiles. Compact padding (Dashboard-only, via the
          style prop — AgencySummary's own StatCard usage is untouched)
          frees up real height for the Census chart row below. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 10, flex: 'none' }}>
        <StatCard label={isPsychologist ? 'My Active Cases' : 'Active Children'} value={census.active} tone="success" icon={<Icon name="users" size={18} />} style={{ padding: '12px 16px', gap: 4 }} />
        <StatCard label="In Counseling" value={(census.by_case_status || {}).counseling || 0} tone="brand" icon={<Icon name="heart-pulse" size={18} />} hint={`${(census.by_case_status || {}).pre_assessment || 0} in pre-assessment`} style={{ padding: '12px 16px', gap: 4 }} />
        <StatCard label="Inactive (Terminated)" value={census.inactive} tone="brand" icon={<Icon name="archive" size={18} />} style={{ padding: '12px 16px', gap: 4 }} />
        <StatCard label="Pending Pre-Assessments" value={stats.pending_pre_assessments} tone="amber" icon={<Icon name="loader" size={18} />} hint={stats.unassessed ? `${stats.unassessed} not yet assessed` : undefined} style={{ padding: '12px 16px', gap: 4 }} />
      </div>

      {/* Bento body — three rows. Census gets its own full-width row at the
          top so the Intake vs. termination chart + case-mix badges are
          unmistakably the dashboard's most prominent element — the
          remaining five tiles compact into two denser rows below.

          Each row has a real pixel floor (via minmax(Npx, …fr)), and the
          grid is NOT forced to minHeight:0 — its natural min-height is the
          sum of those floors. On a tall window the flex:1/fr weighting
          still lets it grow to fill the screen with no page scroll (as
          verified at 1440x900); on a short window (a maximized Chrome
          window on a 1366x768 laptop typically leaves well under 700px of
          actual content height once the tab/address bars and taskbar are
          subtracted) the grid can no longer be crushed below the point
          where a bar chart stops rendering or a calendar becomes unusable
          — the page scrolls instead, which is a far better failure mode
          than invisible charts or badly clipped tiles.

          The floor lives on the GRID CONTAINER (minHeight:580px), not on
          individual rows: per-row px floors (minmax(180px,1.1fr) etc.)
          turned out to distort the fr distribution unpredictably once a
          row's floor exceeds its proportional fr share — measured on a
          real browser, that produced WORSE per-tile fits than plain fr
          weights despite an identical total pool. Plain `minmax(0,Nfr)`
          rows plus one minHeight on the container reproduces the exact
          1:1.25:0.75 proportions already verified to fit every tile with
          zero clipping at a 596px pool, while still giving `fr` a
          definite number to resolve against on short screens (container
          clamped to 580px) instead of falling back to unclipped
          max-content sizing, which is what broke chart rendering
          entirely on short windows before this fix. */}
      <div style={{ flex: 1, minHeight: 580, display: 'grid', gap: 10, gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gridTemplateRows: 'minmax(0,1fr) minmax(0,1.25fr) minmax(0,0.75fr)' }}>
        {/* Intake vs. termination — full width, top priority */}
        <Tile eyebrow="Census" title="Intake vs. termination" span={4}
          actions={(
            <div role="tablist" aria-label="Census date range" style={{ display: 'flex', gap: 4 }}>
              {RANGES.map(([label, value]) => (
                <button key={value} role="tab" aria-selected={range === value} onClick={() => setRange(value)}
                  style={{ padding: '4px 11px', borderRadius: 'var(--radius-pill)', fontSize: 11.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-sans)', background: range === value ? 'var(--blue-600)' : 'var(--ink-50)', color: range === value ? '#fff' : 'var(--text-muted)', border: `1px solid ${range === value ? 'var(--blue-600)' : 'var(--border)'}` }}>
                  {label}
                </button>
              ))}
            </div>
          )}>
          {stats.intake_vs_termination.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No intake activity yet.</div>
          ) : (
            <div style={{ display: 'flex', height: '100%', gap: 14 }}>
              <div style={{ flex: '1 1 auto', minWidth: 0, minHeight: 120 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.intake_vs_termination}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="intake" name="Intake" fill="var(--blue-600)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="terminations" name="Terminations" fill="var(--amber-500)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {caseMix.length > 0 && (
                <div style={{ flex: '0 0 180px', paddingLeft: 14, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto' }}>
                  <span className="racco-eyebrow" style={{ fontSize: 10 }}>Active case mix</span>
                  {caseMix.map(([type, n]) => <Badge key={type} tone="success" size="sm" dot>{type} — {n}</Badge>)}
                </div>
              )}
            </div>
          )}
        </Tile>

        {/* Today's schedule strip (athena scheduling-tile pattern) */}
        <Tile eyebrow="Today" title="Schedule" span={2}>
          {stats.today_schedule.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No appointments today.</div>
          ) : (
            <div className="racco-scroll" style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
              {stats.today_schedule.map((a) => (
                <button key={a.id} onClick={() => navigate('/schedule')}
                  style={{ flex: 'none', width: 190, textAlign: 'left', padding: '12px 14px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', background: a.status === 'completed' ? 'var(--success-50)' : 'var(--surface)', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span className="racco-mono" style={{ fontWeight: 800, fontSize: 14, color: 'var(--blue-700)' }}>{a.time}</span>
                    <Badge tone={a.status === 'completed' ? 'success' : a.status === 'no_show' ? 'amber' : 'brand'} size="sm">{a.status.replace('_', '-')}</Badge>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.child_name}{a.age != null ? `, ${a.age}` : ''}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{PURPOSE_LABEL[a.purpose] || a.purpose}{!isPsychologist && a.psychologist ? ` · ${a.psychologist}` : ''}</div>
                </button>
              ))}
            </div>
          )}
          {stats.availability_today.length > 0 && (
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="racco-eyebrow" style={{ fontSize: 10 }}>Available today</span>
              {stats.availability_today.map((b, i) => (
                <Badge key={i} tone="success" size="sm" dot>{b.psychologist} · {b.start}–{b.end}</Badge>
              ))}
            </div>
          )}
        </Tile>

        {/* Mini calendar — click opens the full schedule page */}
        <Tile eyebrow="Schedule" title="Calendar">
          <MiniCalendar appointments={appointments} onOpen={() => navigate('/schedule')} />
        </Tile>

        {/* Care-gap alerts */}
        <Tile eyebrow="Follow-up needed" title="Care-gap alerts">
          {gaps.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--success-600)' }}>
              <Icon name="check-circle-2" size={16} /> No gaps detected.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {gaps.map((g, i) => (
                <button key={i} onClick={() => navigate(`/report/child/${g.child_id}`)}
                  style={{ display: 'flex', gap: 10, alignItems: 'flex-start', textAlign: 'left', padding: '7px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-50)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', marginTop: 5, flex: 'none', background: GAP_TONE[g.severity] || 'var(--blue-400)' }} />
                  <span>
                    <span style={{ display: 'block', fontWeight: 700, fontSize: 12.5, color: 'var(--text-strong)' }}>{g.child_name}</span>
                    <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.4 }}>{g.message}</span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </Tile>

        {/* Sessions by psychologist */}
        <Tile eyebrow="Clinical team" title="Sessions by psychologist" span={2}>
          {(stats.per_psychologist || []).length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No completed sessions yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {stats.per_psychologist.map((p) => (
                <div key={p.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-strong)' }}>{p.name}</span>
                  <span className="racco-mono" style={{ fontSize: 13, fontWeight: 700, color: 'var(--blue-600)' }}>{p.count}</span>
                </div>
              ))}
            </div>
          )}
          {(stats.counseling_per_psychologist || []).length > 0 && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
              <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 6 }}>Cases in counseling</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {stats.counseling_per_psychologist.map((p) => (
                  <Badge key={p.name} tone="brand" size="sm" dot>{p.name} · {p.count}</Badge>
                ))}
              </div>
            </div>
          )}
        </Tile>

        {/* Activity feed */}
        <Tile eyebrow="Live" title="Activity Feed" span={2}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {feed.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-faint)', padding: '8px 0' }}>No recent activity.</div>
            ) : feed.map((a, i) => (
              <button key={a.id ?? i} onClick={() => navigate(eventDestination(a, role))}
                style={{ display: 'flex', gap: 11, padding: '10px 0', borderBottom: i < feed.length - 1 ? '1px solid var(--ink-100)' : 'none', width: '100%', textAlign: 'left', border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-50)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', marginTop: 5, flex: 'none', background: a.action === 'archived' ? 'var(--red-500)' : a.action === 'created' ? 'var(--success-500)' : a.action === 'login' ? 'var(--amber-500)' : 'var(--blue-500)' }} />
                <span>
                  <span style={{ display: 'block', fontSize: 13, color: 'var(--text-strong)', fontWeight: 600, lineHeight: 1.4 }}>{eventText(a)}</span>
                  <span style={{ display: 'block', fontSize: 11.5, color: 'var(--text-faint)', marginTop: 2 }}>{a.actor_label} · {timeAgo(a.created_at)}</span>
                </span>
              </button>
            ))}
          </div>
        </Tile>
      </div>
    </div>
  );
}
