import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useActivity } from '../context/ActivityContext';
import { Card, Button, Badge, Input, Select, FormField, Avatar, Alert, EmptyState, Icon, iconBtn, hoverLift, PAGE } from '../ui';
import { useToast } from '../context/ToastContext';
import { CASE_TYPES, CASE_CATEGORIES, SURRENDERED_BY, TERMINATION_REASONS, PROVINCES, MUNICIPALITIES, BARANGAYS, BIRTH_STATUSES, LEGAL_STATUSES, TYPES_OF_ADOPTION } from '../config/caseData';

// Live "who else has this record open" chip — polls the presence heartbeat endpoint.
function usePresence(childId) {
  const [others, setOthers] = useState([]);
  useEffect(() => {
    if (!childId) { setOthers([]); return; }
    let alive = true;
    const beat = () => api.post(`/children/${childId}/presence/`)
      .then((r) => alive && setOthers(r.data.others || [])).catch(() => {});
    beat();
    const t = setInterval(beat, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [childId]);
  return others;
}

function ageFrom(birth) {
  if (!birth) return null;
  const d = new Date(birth);
  if (Number.isNaN(d.getTime())) return null;
  const diff = Date.now() - d.getTime();
  return Math.max(0, Math.floor(diff / (365.25 * 24 * 3600 * 1000)));
}
// Adviser-optimized age groups: Child 1-12, Teen 13-17.
function ageGroup(age) {
  if (age == null) return null;
  if (age <= 12) return 'Child';
  if (age <= 17) return 'Teen';
  return 'Adult';
}
function caseRef(id) {
  return `C-${String(id).padStart(4, '0')}`;
}

// V2 status chip: `Active · Foster Care` / `Archived (Terminated)`.
function StatusChip({ child, size = 'sm' }) {
  if (child.status === 'inactive') return <Badge tone="neutral" size={size} dot>Archived (Terminated)</Badge>;
  return <Badge tone="success" size={size} dot>Active{child.case_type ? ` · ${child.case_type}` : ''}</Badge>;
}

// Purpose labels mirror Schedule.jsx.
const PURPOSE_LABEL = { pre_assessment: 'Pre-Assessment', session: 'Session', follow_up: 'Follow-up' };
// Local YYYY-MM-DD (never toISOString — it shifts the date in UTC+8 evenings).
const localDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
const fmtDay = (iso) => new Date(iso).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });

// Roster schedule chip: today's session (amber) or next booking within the
// 7-day window (neutral), else nothing.
function ScheduleChip({ appts = [] }) {
  if (appts.length === 0) return <span style={{ color: 'var(--text-faint)' }}>—</span>;
  const today = localDate(new Date());
  const next = appts[0]; // pre-sorted by start
  const isToday = next.start.slice(0, 10) === today;
  return (
    <Badge tone={isToday ? 'amber' : 'neutral'} size="sm" dot>
      {isToday ? `Today · ${fmtTime(next.start)}` : `${fmtDay(next.start)}`}
    </Badge>
  );
}

const EMPTY = {
  first_name: '', middle_initial: '', last_name: '',
  birth_date: '', gender: '', province: '', municipality: '', barangay: '',
  case_type: '', case_category: '', surrendered_by: '', psychologist: '', assignee_sees_history: true,
  place_of_birth_or_found: '', birth_status: '', legal_status: '',
  date_of_admission: '', date_of_placement_to_custodian: '', type_of_adoption: '',
  referral_source: '', referral_reason: '', education_level: '', current_placement: '', medical_notes: '',
  recommendation: '',
};

export default function Children() {
  const { user } = useAuth();
  const { refresh: refreshActivity } = useActivity();
  const toast = useToast();
  const navigate = useNavigate();
  const canManage = ['Administrator', 'Staff'].includes(user?.role_name);
  const isAdmin = user?.role_name === 'Administrator';
  const isPsych = user?.role_name === 'Psychologist';
  const [children, setChildren] = useState([]);
  const [psychologists, setPsychologists] = useState([]);
  const [blocks, setBlocks] = useState([]);
  // childId -> [scheduled appointments in the next 7 days], sorted by start.
  const [apptsByChild, setApptsByChild] = useState({});
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get('q') || '';
  const [status, setStatus] = useState('active');
  const [sortMode, setSortMode] = useState('newest');
  const [reasonFilter, setReasonFilter] = useState(''); // Archived tab only (admin/staff)
  const [sel, setSel] = useState(null); // detail drawer record
  const [form, setForm] = useState(null); // add/edit drawer
  const [terminating, setTerminating] = useState(null); // terminate modal record
  const [error, setError] = useState('');
  const others = usePresence(form?.id || sel?.id);
  // The old standalone Archive page folded in here: admin/staff viewing the
  // Archived filter get the termination-detail columns + reopen; psychologists
  // keep the plain roster (they can't reopen, see decision 2026-07-18).
  const showArchiveColumns = canManage && status === 'inactive';

  useEffect(() => { if (status !== 'inactive') setReasonFilter(''); }, [status]);

  const load = () => {
    // Include inactive (terminated) cases — the V2 roster shows them with chips.
    api.get('/children/?include_archived=true').then((r) => setChildren(r.data));
    // Active psychologists + current caseload (admin/staff endpoint — also lets Staff assign).
    api.get('/psychologists/').then((r) => setPsychologists(r.data)).catch(() => {});
    // Availability blocks power the assignment-time comparison panel — admin/staff only.
    if (canManage) api.get('/availability/').then((r) => setBlocks(r.data)).catch(() => {});
    // Upcoming (next 7 days) scheduled appointments → roster chips + drawer list.
    // Role-scoped server-side: psychologists get only their own caseload.
    const today = new Date();
    const weekAhead = new Date(today); weekAhead.setDate(today.getDate() + 7);
    api.get(`/appointments/?from=${localDate(today)}&to=${localDate(weekAhead)}`)
      .then((r) => {
        const map = {};
        (r.data || [])
          .filter((a) => a.status === 'scheduled')
          .sort((a, b) => a.start.localeCompare(b.start))
          .forEach((a) => { (map[a.child] ||= []).push(a); });
        setApptsByChild(map);
      })
      .catch(() => setApptsByChild({}));
  };
  useEffect(() => { load(); }, []);

  const setQ = (v) => setSearchParams(v ? { q: v } : {}, { replace: true });

  const rows = useMemo(() => children.map((c) => ({
    ...c,
    age: ageFrom(c.birth_date),
    group: ageGroup(ageFrom(c.birth_date)),
    ref: caseRef(c.id),
  })), [children]);

  const counts = { all: rows.length, active: 0, inactive: 0 };
  rows.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });

  // Adviser: improve alphabetical sorting throughout the system.
  const visible = rows
    .filter((c) => c.fullname.toLowerCase().includes(q.toLowerCase()) || c.ref.toLowerCase().includes(q.toLowerCase()))
    .filter((c) => status === 'all' || c.status === status)
    .filter((c) => !showArchiveColumns || !reasonFilter || c.termination?.reason_category === reasonFilter)
    .sort((a, b) => sortMode === 'newest'
      ? b.id - a.id  // LIFO: newest record first
      : a.fullname.localeCompare(b.fullname, undefined, { sensitivity: 'base' }));

  const STATUS_FILTERS = [
    { key: 'active', label: 'Active' },
    { key: 'inactive', label: 'Archived' },
    { key: 'all', label: 'All' },
  ];
  const dotColor = { active: 'var(--success-500)', inactive: 'var(--text-faint)' };
  const td = { padding: '11px 16px', fontSize: 13, color: 'var(--text-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' };

  const canTerminate = (c) => c.status === 'active'
    && (isAdmin || (isPsych && String(c.psychologist) === String(user?.id)));
  const canEditRecord = (c) => canManage
    || (isPsych && c.status === 'active' && String(c.psychologist) === String(user?.id));

  // Per-user draft key so an unsaved intake typed by one user never leaks
  // into another user's "Add Record" session on a shared workstation.
  const draftKey = `nacc-child-draft:${user?.id ?? 'anon'}`;

  const openCreate = () => {
    setError('');
    let draft = null;
    try { draft = JSON.parse(localStorage.getItem(draftKey) || 'null'); } catch { /* corrupt draft */ }
    const meaningful = draft && Object.entries(draft).some(([k, v]) => k !== 'assignee_sees_history' && v);
    setForm({ ...EMPTY, _draft: meaningful ? draft : null });
  };
  const openEdit = (c) => { setError(''); setForm({ ...EMPTY, ...c, psychologist: c.psychologist || '', _origPsychologist: c.psychologist || '' }); };

  const save = async (e) => {
    e.preventDefault();
    setError('');
    const payload = { ...form, expected_updated_at: form.updated_at };
    delete payload.age; delete payload.group; delete payload.ref;
    delete payload.psychologist_name; delete payload.guardian_name;
    delete payload._origPsychologist; delete payload.termination; delete payload.photo;
    delete payload.updated_at; delete payload._conflict; delete payload._draft;
    if (!payload.psychologist) payload.psychologist = null;
    if (!payload.birth_date) delete payload.birth_date;
    if (!payload.date_of_admission) delete payload.date_of_admission;
    if (!payload.date_of_placement_to_custodian) delete payload.date_of_placement_to_custodian;
    if (form.id) delete payload.fullname;
    try {
      if (form.id) await api.put(`/children/${form.id}/`, payload);
      else await api.post('/children/', payload);
      try { localStorage.removeItem(draftKey); } catch { /* private browsing */ }
      toast.success(form.id ? 'Record updated' : 'Record added');
      setForm(null);
      load();
      refreshActivity();
    } catch (err) {
      if (err.response?.status === 409) {
        const fresh = err.response.data.current;
        setError('');
        setForm((f) => ({ ...f, _conflict: fresh }));
        toast.error('Someone updated this record while you were editing.');
        return;
      }
      setError(JSON.stringify(err.response?.data || 'Save failed'));
      toast.error('Could not save the record. Please try again.');
    }
  };

  const terminate = async (c, reason, note) => {
    try {
      await api.post(`/children/${c.id}/terminate/`, { reason_category: reason, note });
      toast.success(`${c.fullname}'s case is now inactive`);
      setTerminating(null);
      setSel(null);
      load();
      refreshActivity();
    } catch (err) {
      const d = err.response?.data;
      toast.error(d?.note || d?.reason_category || d?.detail || 'Could not terminate the case.');
    }
  };

  const reopen = async (c) => {
    try {
      await api.post(`/children/${c.id}/reopen/`);
      toast.success(`${c.fullname}'s case is active again — previous records retained`);
      setSel(null);
      load();
      refreshActivity();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not reopen the case.');
    }
  };

  // Duplicate-check warning shortcuts (Add Record form): reuse the existing
  // reopen() for archived matches, or just open the active match's drawer.
  const onDupReopen = async (m) => { await reopen({ id: m.id, fullname: m.fullname }); setForm(null); };
  const onDupOpenExisting = (m) => { setForm(null); const c = rows.find((r) => r.id === m.id); if (c) setSel(c); };

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ width: 320, maxWidth: '100%' }}>
          <Input placeholder="Search by name or case ID…" value={q} onChange={(e) => setQ(e.target.value)} leading={<Icon name="search" size={16} />} />
        </div>
        {canManage && (
          <Button variant="primary" onClick={openCreate} iconLeft={<Icon name="plus" size={17} />}>Add Record</Button>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div role="tablist" aria-label="Filter children by status" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {STATUS_FILTERS.map((f) => {
              const on = status === f.key;
              return (
                <button key={f.key} role="tab" aria-selected={on} onClick={() => setStatus(f.key)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 13px', cursor: 'pointer', borderRadius: 'var(--radius-pill)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', color: on ? 'var(--blue-700)' : 'var(--text-body)', transition: 'var(--transition-base)' }}>
                  {dotColor[f.key] && <span style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor[f.key] }} />}
                  {f.label}
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: on ? 'var(--blue-600)' : 'var(--text-faint)' }}>{counts[f.key] || 0}</span>
                </button>
              );
            })}
          </div>
          <div style={{ display: 'inline-flex', gap: 4, background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)', padding: 3 }}>
            {[['newest', 'Newest first'], ['az', 'A–Z']].map(([k, label]) => (
              <button key={k} onClick={() => setSortMode(k)} style={{ padding: '5px 12px', borderRadius: 'var(--radius-pill)', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12, background: sortMode === k ? 'var(--blue-600)' : 'transparent', color: sortMode === k ? '#fff' : 'var(--text-muted)' }}>{label}</button>
            ))}
          </div>
          {showArchiveColumns && (
            <div style={{ width: 220 }}>
              <Select value={reasonFilter} onChange={(e) => setReasonFilter(e.target.value)} aria-label="Filter by termination reason">
                <option value="">All termination reasons</option>
                {TERMINATION_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </Select>
            </div>
          )}
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
          Showing <strong style={{ color: 'var(--text-strong)' }}>{visible.length}</strong> of {rows.length} children
        </div>
      </div>

      {canManage && psychologists.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 14, padding: '10px 14px', borderRadius: 'var(--radius-lg)', background: 'var(--surface)', border: '1px solid var(--border)' }}>
          <span className="racco-eyebrow" style={{ fontSize: 10, color: 'var(--text-muted)' }}>Psychologist caseload</span>
          {psychologists.map((p) => (
            <span key={p.id} title={`${p.name}: ${p.caseload} active case${p.caseload === 1 ? '' : 's'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 11px', borderRadius: 'var(--radius-pill)', background: 'var(--ink-50)', border: '1px solid var(--border)', fontSize: 12.5 }}>
              <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{p.name}</span>
              <span className="racco-mono" style={{ fontWeight: 800, color: p.caseload >= 5 ? 'var(--red-600)' : 'var(--blue-600)' }}>{p.caseload}</span>
            </span>
          ))}
        </div>
      )}

      <Card padding="0">
        {visible.length === 0 ? (
          <EmptyState icon={<Icon name="folder-search" size={24} />} title="No records found" description="Try a different name, case ID, or status filter." />
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: showArchiveColumns ? 860 : 820, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                  {(showArchiveColumns
                    ? ['Child', 'Case Type', 'Terminated On', 'Reason', 'Terminated By', 'Note', 'Actions']
                    : ['Child', 'Gender / Age', 'Psychologist', 'Schedule', 'Status']
                  ).map((h) => (
                    <th key={h} scope="col" style={{ textAlign: 'left', padding: '11px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr key={c.id} tabIndex={0} role="button" aria-label={`${c.fullname}, case ${c.ref}. Open details.`}
                    onClick={() => setSel(c)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSel(c); } }}
                    style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer', transition: 'background var(--dur-fast) var(--ease-out)', opacity: c.status === 'inactive' ? 0.72 : 1 }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-50)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                    <td style={{ padding: '11px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
                        <Avatar name={c.fullname} tone={showArchiveColumns ? 'neutral' : 'brand'} size="sm" />
                        <div style={{ minWidth: 0, maxWidth: 200 }}>
                          <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--blue-700)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.fullname}</div>
                          <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.ref}</div>
                        </div>
                      </div>
                    </td>
                    {showArchiveColumns ? (
                      <>
                        <td style={{ ...td, whiteSpace: 'nowrap' }}>{c.case_type || '—'}</td>
                        <td style={{ ...td, whiteSpace: 'nowrap' }} className="racco-mono">{c.termination?.date || '—'}</td>
                        <td style={td}>{c.termination?.reason_category
                          ? <Badge tone="amber" size="sm" dot>{c.termination.reason_category}</Badge> : '—'}</td>
                        <td style={{ ...td, whiteSpace: 'nowrap' }}>{c.termination?.terminated_by || '—'}</td>
                        <td style={{ ...td, maxWidth: 260 }}>
                          <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }} title={c.termination?.note || ''}>
                            {c.termination?.note || '—'}
                          </span>
                        </td>
                        <td style={{ padding: '11px 16px' }}>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button title="View full record" aria-label={`View ${c.fullname}'s record`} onClick={(e) => { e.stopPropagation(); navigate(`/report/child/${c.id}`); }} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--blue-600)')}><Icon name="eye" size={15} /></button>
                            {isAdmin && (
                              <button title="Reopen case" aria-label={`Reopen ${c.fullname}'s case`}
                                onClick={(e) => { e.stopPropagation(); if (window.confirm('Reopen this case? All previous records and termination history are kept, but the psychologist assignment is cleared — assign one fresh afterwards.')) reopen(c); }}
                                {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--success-600)')}><Icon name="rotate-ccw" size={15} /></button>
                            )}
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td style={td}>{c.gender || '—'} {c.age != null ? `· ${c.age} (${c.group})` : ''}</td>
                        <td style={td}>
                          {c.psychologist_name
                            ? c.psychologist_name
                            : canManage && c.status === 'active'
                              ? (
                                <button title={`Assign a psychologist to ${c.fullname}`} aria-label={`Assign psychologist to ${c.fullname}`}
                                  onClick={(e) => { e.stopPropagation(); openEdit(c); }} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })}
                                  style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 'var(--radius-pill)', border: '1px dashed var(--blue-300)', background: 'var(--blue-50)', color: 'var(--blue-700)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12, cursor: 'pointer', transition: 'var(--transition-base)' }}>
                                  <Icon name="user-plus" size={13} /> Assign
                                </button>
                              )
                              : '—'}
                        </td>
                        <td style={td}>{c.status === 'active' ? <ScheduleChip appts={apptsByChild[c.id]} /> : <span style={{ color: 'var(--text-faint)' }}>—</span>}</td>
                        <td style={{ padding: '11px 16px' }}><StatusChip child={c} /></td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {sel && <ChildDrawer child={sel} upcoming={apptsByChild[sel.id] || []} canEdit={canEditRecord(sel)} canTerminate={canTerminate(sel)} isAdmin={isAdmin} others={others} onEdit={() => { openEdit(sel); setSel(null); }} onTerminate={() => setTerminating(sel)} onReopen={() => { if (window.confirm('Reopen this case? All previous records and termination history are kept, but the psychologist assignment is cleared — assign one fresh afterwards.')) reopen(sel); }} onClose={() => setSel(null)} />}
      {form && <ChildForm form={form} setForm={setForm} draftKey={draftKey} psychologists={psychologists} blocks={blocks} error={error} isPsych={isPsych} isAdmin={isAdmin} others={others} onSubmit={save} onClose={() => setForm(null)} onReopen={onDupReopen} onOpenExisting={onDupOpenExisting} />}
      {terminating && <TerminateModal child={terminating} onConfirm={terminate} onClose={() => setTerminating(null)} />}
    </div>
  );
}

function ChildDrawer({ child, upcoming = [], canEdit, canTerminate, isAdmin = false, others = [], onEdit, onTerminate, onReopen, onClose }) {
  const toast = useToast();
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  // "Next possible sessions" — when can this child next be counseled, given
  // their assigned psychologist's availability. Named function (not an
  // inline effect body) so a later task can re-invoke it after booking.
  const [slots, setSlots] = useState(null);
  const canSuggestSlots = child.status === 'active' && !!child.psychologist_name;
  const loadSlots = () => {
    if (!canSuggestSlots) { setSlots(null); return; }
    api.get(`/availability/next-slots/?child=${child.id}`).then((r) => setSlots(r.data)).catch(() => setSlots(null));
  };
  useEffect(() => { loadSlots(); /* eslint-disable-next-line */ }, [child.id, child.status, child.psychologist_name]);
  // One-click first booking — clicking a suggested slot opens an inline
  // confirm (purpose + Book/Cancel) instead of navigating to /schedule.
  const [pendingSlot, setPendingSlot] = useState(null);
  const [purpose, setPurpose] = useState(null);
  const [bookingBusy, setBookingBusy] = useState(false);
  // Answered/Completed both mean the pre-assessment was administered.
  const defaultPurpose = ['Answered', 'Completed'].includes(child.pre_assessment_status) ? 'session' : 'pre_assessment';
  const bookSlot = async () => {
    setBookingBusy(true);
    try {
      await api.post('/appointments/', {
        child: child.id, psychologist: child.psychologist,
        start: `${pendingSlot.date}T${pendingSlot.start}:00`,
        duration_minutes: 60, purpose, notes: '',
      });
      toast.success(`Booked — ${pendingSlot.weekday} ${pendingSlot.date} at ${pendingSlot.start}`);
      setPendingSlot(null);
      loadSlots();
    } catch (err) {
      const d = err.response?.data;
      toast.error(d?.start || d?.psychologist || d?.detail || 'Could not book this slot.');
    } finally { setBookingBusy(false); }
  };
  const location = [child.barangay, child.municipality, child.province].filter(Boolean).join(', ') || child.address || '—';
  const showReopen = isAdmin && child.status === 'inactive';
  const hasRecommendationContent = child.recommendation || child.referral_source || child.education_level || child.current_placement;
  const fields = [
    ['Sex', child.gender || '—'],
    ['Place of Birth or Place Found', child.place_of_birth_or_found || '—'],
    ['Birth Status', child.birth_status || '—'],
    ['Category', child.case_category || '—'],
    ['Legal Status', child.legal_status || '—'],
    ['Assigned Psychologist', child.psychologist_name || '—'],
    ['Previous Custodian', child.surrendered_by || '—'],
    ['Address', location],
    ['Date of Admission to the Agency', child.date_of_admission || '—'],
    ['Date of Placement to Custodian', child.date_of_placement_to_custodian || '—'],
    ['Type of Adoption', child.type_of_adoption || '—'],
    ['Pre-Assessment', child.pre_assessment_status || '—'],
  ];
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 60, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
      <div role="dialog" aria-modal="true" aria-label={`Case record for ${child.fullname}`} onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(980px, 96vw)', height: 'min(86vh, 820px)', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, background: 'var(--ink-50)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Avatar name={child.fullname} tone="brand" size="lg" />
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>{child.fullname}</div>
              <div className="racco-mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{child.ref}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                <StatusChip child={child} size="md" />
                {child.case_type && <Badge tone="neutral" size="sm">{child.case_type}</Badge>}
                {child.age != null && <span style={{ fontSize: 12.5, color: 'var(--text-muted)', fontWeight: 600 }}>{child.age} yrs old ({child.group})</span>}
              </div>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close panel" title="Close" {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--text-muted)')}><Icon name="x" size={17} /></button>
        </div>
        {others.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '8px 24px', background: 'var(--blue-50)', borderBottom: '1px solid var(--blue-100)' }}>
            <Icon name="users" size={14} style={{ color: 'var(--blue-600)' }} />
            {others.map((o, i) => <Badge key={i} tone="brand" size="sm" dot>{o.name} ({o.role}) is here</Badge>)}
          </div>
        )}
        <div className="racco-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px 24px' }}>
          <div className="racco-case-grid">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {fields.map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, paddingBottom: 12, borderBottom: '1px solid var(--ink-100)' }}>
                  <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 }}>{k}</span>
                  <span style={{ fontSize: 13.5, color: 'var(--text-strong)', fontWeight: 700, textAlign: 'right' }}>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {child.status === 'inactive' && (child.terminations || []).length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div className="racco-eyebrow" style={{ fontSize: 10 }}>Termination history ({child.terminations.length})</div>
                  {child.terminations.map((t, i) => (
                    <div key={i} style={{ padding: '12px 14px', borderRadius: 'var(--radius-lg)', background: 'var(--ink-50)', border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)' }}>{t.reason_category}</div>
                      <p style={{ fontSize: 12.5, color: 'var(--text-body)', margin: '4px 0 0', lineHeight: 1.5 }}>{t.note}</p>
                      <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 6 }}>{t.date}{t.terminated_by ? ` · by ${t.terminated_by}` : ''}</div>
                    </div>
                  ))}
                </div>
              )}
              {(child.instruments_used || []).length > 0 && (
                <div>
                  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Instrument titles used</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {child.instruments_used.map((t) => <Badge key={t} tone="brand" size="sm">{t}</Badge>)}
                  </div>
                </div>
              )}
              {hasRecommendationContent && (
                <div>
                  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Recommendation</div>
                  {child.recommendation && <p style={{ fontSize: 13, color: 'var(--text-body)', margin: '0 0 10px', lineHeight: 1.55 }}>{child.recommendation}</p>}
                  {[['Referral Source', child.referral_source], ['Educational Placement', child.education_level], ['Current Whereabouts', child.current_placement]]
                    .filter(([, v]) => v).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, paddingBottom: 10, borderBottom: '1px solid var(--ink-100)', marginBottom: 10 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 }}>{k}</span>
                        <span style={{ fontSize: 13.5, color: 'var(--text-strong)', fontWeight: 700, textAlign: 'right' }}>{v}</span>
                      </div>
                  ))}
                </div>
              )}
              {child.referral_reason && (
                <div>
                  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 6 }}>Referral reason</div>
                  <p style={{ fontSize: 13, color: 'var(--text-body)', margin: 0, lineHeight: 1.55 }}>{child.referral_reason}</p>
                </div>
              )}
              {child.medical_notes && (
                <div>
                  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 6 }}>Medical notes</div>
                  <p style={{ fontSize: 13, color: 'var(--text-body)', margin: 0, lineHeight: 1.55 }}>{child.medical_notes}</p>
                </div>
              )}
              {upcoming.length > 0 && (
                <div>
                  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Upcoming appointments</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {upcoming.slice(0, 3).map((a) => {
                      const isToday = a.start.slice(0, 10) === localDate(new Date());
                      return (
                        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 13px', borderRadius: 'var(--radius-md)', background: isToday ? 'var(--amber-50)' : 'var(--ink-50)', border: `1px solid ${isToday ? 'var(--amber-200)' : 'var(--border)'}` }}>
                          <Icon name="calendar" size={15} style={{ color: isToday ? 'var(--amber-600)' : 'var(--blue-600)', flex: 'none' }} />
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)' }}>
                              {isToday ? 'Today' : fmtDay(a.start)} · {fmtTime(a.start)}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                              {PURPOSE_LABEL[a.purpose] || a.purpose}{a.psychologist_name ? ` · ${a.psychologist_name}` : ''}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {canSuggestSlots && slots?.slots?.length > 0 && (
                <div>
                  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Next possible sessions — {slots.psychologist}</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {slots.slots.map((s, i) => (
                      <button key={i} type="button" onClick={() => { setPendingSlot(s); setPurpose(defaultPurpose); }}
                        style={{ padding: '5px 11px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--success-100)', background: 'var(--success-50)', color: 'var(--success-600)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 11.5, cursor: 'pointer' }}>
                        {s.weekday.slice(0, 3)} {s.date.slice(5)} · {s.start}–{s.end}
                      </button>
                    ))}
                  </div>
                  {pendingSlot && (
                    <div style={{ marginTop: 10, padding: '11px 13px', borderRadius: 'var(--radius-md)', background: 'var(--blue-50)', border: '1px solid var(--blue-200)', display: 'flex', flexDirection: 'column', gap: 9 }}>
                      <span style={{ fontSize: 12.5, color: 'var(--text-strong)', fontWeight: 600 }}>
                        Book {child.fullname} with {slots.psychologist} — {pendingSlot.weekday} {pendingSlot.date} at {pendingSlot.start}?
                      </span>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <Select value={purpose} onChange={(e) => setPurpose(e.target.value)} style={{ maxWidth: 180 }}>
                          <option value="pre_assessment">Pre-Assessment</option>
                          <option value="session">Session</option>
                          <option value="follow_up">Follow-up</option>
                        </Select>
                        <Button variant="primary" disabled={bookingBusy} onClick={bookSlot} iconLeft={<Icon name="calendar" size={15} />}>Book</Button>
                        <Button variant="ghost" onClick={() => setPendingSlot(null)}>Cancel</Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        {(canEdit || canTerminate || showReopen) && (
          <div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {showReopen && (
              <Button variant="primary" fullWidth onClick={onReopen} iconLeft={<Icon name="rotate-ccw" size={16} />}>Reopen Case</Button>
            )}
            {(canEdit || canTerminate) && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                {canEdit && <Button variant="secondary" onClick={onEdit} iconLeft={<Icon name="pencil" size={16} />}>Edit</Button>}
                {canTerminate && <Button variant="danger" onClick={onTerminate} iconLeft={<Icon name="archive" size={16} />}>Terminate Case</Button>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TerminateModal({ child, onConfirm, onClose }) {
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 80, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
      <div role="dialog" aria-modal="true" aria-label={`Terminate ${child.fullname}'s case`} onClick={(e) => e.stopPropagation()} style={{ width: 460, maxWidth: '92%', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>Terminate case — {child.fullname}</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
            The record becomes <strong>Inactive (Terminated)</strong> and is archived from active caseloads. A reason is required.
          </div>
        </div>
        <FormField label="Reason" required>
          <Select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">— Select termination reason —</option>
            {TERMINATION_REASONS.map((r) => <option key={r}>{r}</option>)}
          </Select>
        </FormField>
        <FormField label="Closing summary" required>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} placeholder="Describe why this case is being terminated…"
            style={{ width: '100%', resize: 'vertical', padding: '11px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14, lineHeight: 1.55 }} />
        </FormField>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
          <Button variant="danger" fullWidth disabled={!reason || !note.trim()} onClick={() => onConfirm(child, reason, note.trim())} iconLeft={<Icon name="archive" size={16} />}>Terminate</Button>
        </div>
      </div>
    </div>
  );
}

function ChildForm({ form, setForm, draftKey, psychologists, blocks = [], error, isPsych = false, isAdmin = false, others = [], onSubmit, onClose, onReopen, onOpenExisting }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  const isEdit = !!form.id;
  // Draft autosave (create mode only) — debounced write to localStorage so an
  // accidental modal close (or crash) never loses a half-typed intake record.
  useEffect(() => {
    if (form.id) return; // edits are server-backed; drafts are create-only
    const t = setTimeout(() => {
      const data = { ...form };
      delete data._draft; delete data._conflict;
      if (Object.entries(data).some(([k, v]) => k !== 'assignee_sees_history' && v)) {
        try { localStorage.setItem(draftKey, JSON.stringify(data)); } catch { /* storage full */ }
      }
    }, 500);
    return () => clearTimeout(t);
  }, [form, draftKey]);
  // Duplicate/returning-child detection (create mode only): debounce-check
  // while typing so intake staff can reopen an archived record instead of
  // accidentally creating a second one.
  const [dupes, setDupes] = useState([]);
  useEffect(() => {
    if (form.id || !form.last_name?.trim() || !(form.first_name?.trim() || form.birth_date)) { setDupes([]); return; }
    const t = setTimeout(() => {
      const p = new URLSearchParams({ first_name: form.first_name || '', last_name: form.last_name, birth_date: form.birth_date || '' });
      api.get(`/children/check-duplicate/?${p}`).then((r) => setDupes(r.data.matches || [])).catch(() => setDupes([]));
    }, 600);
    return () => clearTimeout(t);
  }, [form.first_name, form.last_name, form.birth_date, form.id]);
  // Availability-comparison panel helpers (Task 18) — matches AvailabilityBlock 0=Monday.
  const DAY_ABBR = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const availFor = (pid) => blocks.filter((b) => String(b.psychologist) === String(pid));
  const blockLabel = (b) => `${b.date || DAY_ABBR[b.weekday]} ${String(b.start_time).slice(0, 5)}–${String(b.end_time).slice(0, 5)}`;
  // Cascading location pickers; clear children when a parent changes.
  const munis = MUNICIPALITIES[form.province] || [];
  const brgys = BARANGAYS[form.municipality] || [];
  const fieldLabel = { fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 };
  const textarea = { width: '100%', resize: 'vertical', padding: '10px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14, lineHeight: 1.5 };
  // Agency only serves children aged 5-17: the birth date picker's bounds
  // mirror that (max = today minus 5 years, min = today minus 18 years);
  // the backend's validate_birth_date is the authoritative check.
  const today = new Date();
  const maxBirthDate = new Date(today.getFullYear() - 5, today.getMonth(), today.getDate()).toISOString().slice(0, 10);
  const minBirthDate = new Date(today.getFullYear() - 18, today.getMonth(), today.getDate()).toISOString().slice(0, 10);
  const requiredFieldsFilled = form.first_name && form.last_name && form.birth_date && form.gender && form.case_type;
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 70, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
      <form onSubmit={onSubmit} onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(980px, 96vw)', height: 'min(86vh, 820px)', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--ink-50)' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>{isEdit ? 'Edit Record' : 'Add Record'}</div>
          <button type="button" onClick={onClose} aria-label="Close" {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--text-muted)')}><Icon name="x" size={17} /></button>
        </div>
        {others.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '8px 24px', background: 'var(--blue-50)', borderBottom: '1px solid var(--blue-100)' }}>
            <Icon name="users" size={14} style={{ color: 'var(--blue-600)' }} />
            {others.map((o, i) => <Badge key={i} tone="brand" size="sm" dot>{o.name} ({o.role}) is here</Badge>)}
          </div>
        )}
        <div className="racco-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
          {form._draft && (
            <Alert tone="info" icon={<Icon name="history" size={18} />} title="Unsaved draft found">
              You started a record earlier that wasn&apos;t saved. Continue where you left off?
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <Button variant="secondary" size="sm" onClick={() => setForm({ ...EMPTY, ...form._draft, _draft: null })} iconLeft={<Icon name="rotate-ccw" size={14} />}>Restore draft</Button>
                <Button variant="ghost" size="sm" onClick={() => { try { localStorage.removeItem(draftKey); } catch { /* private browsing */ } setForm((f) => ({ ...f, _draft: null })); }}>Discard</Button>
              </div>
            </Alert>
          )}
          {error && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />}>{error}</Alert>}
          {form._conflict && (
            <Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />} title="This record was just changed by a teammate.">
              Load their latest version, then re-apply your edits.
              <div style={{ marginTop: 10 }}>
                <Button type="button" variant="secondary" size="sm" onClick={() => setForm({ ...EMPTY, ...form._conflict, psychologist: form._conflict.psychologist || '', _origPsychologist: form._conflict.psychologist || '' })}>
                  Load latest
                </Button>
              </div>
            </Alert>
          )}

          <section>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Identity</div>
            <div className="racco-case-grid">
              {/* Child name is not editable once a record exists (adviser). */}
              {isEdit ? (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ ...fieldLabel, marginBottom: 6 }}>Full Name</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 13px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)', color: 'var(--text-strong)', fontWeight: 700, fontSize: 14 }}>
                    {form.fullname}
                    <Icon name="lock" size={13} style={{ color: 'var(--text-faint)', marginLeft: 'auto' }} />
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 5 }}>The child&apos;s name cannot be changed after the record is created.</div>
                </div>
              ) : (
                <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: '2fr 64px 2fr', gap: 10 }}>
                  <FormField label="First Name" required>
                    <Input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
                  </FormField>
                  <FormField label="M.I.">
                    <Input value={form.middle_initial} maxLength={3} onChange={(e) => setForm({ ...form, middle_initial: e.target.value })} />
                  </FormField>
                  <FormField label="Last Name" required>
                    <Input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
                  </FormField>
                </div>
              )}
              {!isEdit && dupes.length > 0 && (
                <Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />} title="A similar record already exists" style={{ gridColumn: '1 / -1' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 6 }}>
                    {dupes.map((m) => (
                      <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: 13 }}>{m.fullname}</strong>
                        <Badge tone={m.status === 'inactive' ? 'neutral' : 'success'} size="sm" dot>
                          {m.status === 'inactive' ? 'Archived (Terminated)' : 'Active'}
                        </Badge>
                        {m.birth_date && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>b. {m.birth_date}</span>}
                        {m.status === 'inactive'
                          ? (isAdmin
                              ? <Button variant="secondary" onClick={() => onReopen(m)} iconLeft={<Icon name="rotate-ccw" size={14} />}>Reopen this record instead</Button>
                              : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Ask an administrator to reopen this archived record instead of creating a new one.</span>)
                          : <Button variant="secondary" onClick={() => onOpenExisting(m)} iconLeft={<Icon name="eye" size={14} />}>Open existing record</Button>}
                      </div>
                    ))}
                  </div>
                </Alert>
              )}
              <FormField label="Date of Birth" required={!isEdit}>
                <Input type="date" value={form.birth_date || ''} min={!isEdit ? minBirthDate : undefined} max={!isEdit ? maxBirthDate : undefined} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} required={!isEdit} />
              </FormField>
              <FormField label="Sex" required={!isEdit}>
                <Select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} required={!isEdit}>
                  <option value="">—</option><option>Male</option><option>Female</option>
                </Select>
              </FormField>
              <FormField label="Place of Birth or Place Found">
                <Input value={form.place_of_birth_or_found || ''} onChange={(e) => setForm({ ...form, place_of_birth_or_found: e.target.value })} />
              </FormField>
              <FormField label="Birth Status">
                <Select value={form.birth_status || ''} onChange={(e) => setForm({ ...form, birth_status: e.target.value })}>
                  <option value="">— Select —</option>
                  {BIRTH_STATUSES.map((s) => <option key={s}>{s}</option>)}
                </Select>
              </FormField>
            </div>
          </section>

          <section>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Address</div>
            <div className="racco-case-grid">
              <FormField label="Province">
                <Select value={form.province || ''} onChange={(e) => setForm({ ...form, province: e.target.value, municipality: '', barangay: '' })}>
                  <option value="">— Select province —</option>
                  {PROVINCES.map((p) => <option key={p}>{p}</option>)}
                </Select>
              </FormField>
              <FormField label="Municipality / City">
                <Select value={form.municipality || ''} disabled={!form.province} onChange={(e) => setForm({ ...form, municipality: e.target.value, barangay: '' })}>
                  <option value="">{form.province ? '— Select municipality —' : 'Select a province first'}</option>
                  {munis.map((mn) => <option key={mn}>{mn}</option>)}
                </Select>
              </FormField>
              <FormField label="Barangay">
                <Select value={form.barangay || ''} disabled={!form.municipality} onChange={(e) => setForm({ ...form, barangay: e.target.value })}>
                  <option value="">{form.municipality ? '— Select barangay —' : 'Select a municipality first'}</option>
                  {brgys.map((b) => <option key={b}>{b}</option>)}
                </Select>
              </FormField>
            </div>
          </section>

          <section>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Case</div>
            <div className="racco-case-grid">
              <FormField label="Case Type" required={!isEdit}>
                <Select value={form.case_type || ''} onChange={(e) => setForm({ ...form, case_type: e.target.value })} required={!isEdit}>
                  <option value="">— Select case type —</option>
                  {CASE_TYPES.map((t) => <option key={t}>{t}</option>)}
                </Select>
              </FormField>
              <FormField label="Category">
                <Select value={form.case_category || ''} onChange={(e) => setForm({ ...form, case_category: e.target.value })}>
                  <option value="">— Select category —</option>
                  {CASE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </Select>
              </FormField>
              <FormField label="Previous Custodian">
                <Select value={form.surrendered_by || ''} onChange={(e) => setForm({ ...form, surrendered_by: e.target.value })}>
                  <option value="">— Select —</option>
                  {SURRENDERED_BY.map((s) => <option key={s}>{s}</option>)}
                </Select>
              </FormField>
              <FormField label="Legal Status" hint="With issued CDCLAA / IVC / judicially declared abandoned">
                <Select value={form.legal_status || ''} onChange={(e) => setForm({ ...form, legal_status: e.target.value })}>
                  <option value="">— Select —</option>
                  {LEGAL_STATUSES.map((s) => <option key={s}>{s}</option>)}
                </Select>
              </FormField>
              <FormField label="Date of Admission to the Agency">
                <Input type="date" value={form.date_of_admission || ''} onChange={(e) => setForm({ ...form, date_of_admission: e.target.value })} />
              </FormField>
              <FormField label="Date of Placement to Custodian" hint="For Relative/Stepparent/Adult/FA/IP">
                <Input type="date" value={form.date_of_placement_to_custodian || ''} onChange={(e) => setForm({ ...form, date_of_placement_to_custodian: e.target.value })} />
              </FormField>
              <FormField label="Type of Adoption">
                <Select value={form.type_of_adoption || ''} onChange={(e) => setForm({ ...form, type_of_adoption: e.target.value })}>
                  <option value="">— Select —</option>
                  {TYPES_OF_ADOPTION.map((t) => <option key={t}>{t}</option>)}
                </Select>
              </FormField>
            </div>
          </section>

          <section>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 4 }}>Recommendation</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 10 }}>Details beyond the agency&apos;s intake interview.</div>
            <div className="racco-case-grid">
              <FormField label="Referral Source" hint="Agency, LGU, or person who referred the child.">
                <Input value={form.referral_source || ''} onChange={(e) => setForm({ ...form, referral_source: e.target.value })} />
              </FormField>
              <FormField label="Educational Placement">
                <Input value={form.education_level || ''} onChange={(e) => setForm({ ...form, education_level: e.target.value })} placeholder="e.g. Grade 4" />
              </FormField>
              <FormField label="Current Whereabouts">
                <Input value={form.current_placement || ''} onChange={(e) => setForm({ ...form, current_placement: e.target.value })} placeholder="e.g. Foster family, residential facility" />
              </FormField>
              <FormField label="Referral Reason" style={{ gridColumn: '1 / -1' }}>
                <textarea value={form.referral_reason || ''} onChange={(e) => setForm({ ...form, referral_reason: e.target.value })} rows={3} style={textarea} />
              </FormField>
              <FormField label="Medical Notes" style={{ gridColumn: '1 / -1' }}>
                <textarea value={form.medical_notes || ''} onChange={(e) => setForm({ ...form, medical_notes: e.target.value })} rows={3} style={textarea} />
              </FormField>
              <FormField label="Recommendation" hint="Follow-ups, referrals, and notes outside the intake timeline." style={{ gridColumn: '1 / -1' }}>
                <textarea value={form.recommendation || ''} onChange={(e) => setForm({ ...form, recommendation: e.target.value })} rows={3} style={textarea} />
              </FormField>
            </div>
          </section>

          <section>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Assignment</div>
            {isPsych ? (
              <FormField label="Assigned Psychologist" hint="Reassignment is done by admin/staff.">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 13px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)', color: 'var(--text-strong)', fontWeight: 700, fontSize: 14 }}>
                  {form.psychologist_name || '—'}
                  <Icon name="lock" size={13} style={{ color: 'var(--text-faint)', marginLeft: 'auto' }} />
                </div>
              </FormField>
            ) : (
              <>
                <FormField label="Assign Psychologist">
                  <Select value={form.psychologist || ''} onChange={(e) => setForm({ ...form, psychologist: e.target.value })}>
                    <option value="">— Unassigned —</option>
                    {psychologists.map((p) => <option key={p.id} value={p.id}>{p.name} — {p.caseload} case{p.caseload === 1 ? '' : 's'}</option>)}
                  </Select>
                </FormField>
                {psychologists.length > 0 && (
                  <div style={{ marginTop: 10, border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 12, background: 'var(--ink-50)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div className="racco-eyebrow" style={{ fontSize: 10 }}>Availability — check before you assign</div>
                    {psychologists.map((p) => {
                      const av = availFor(p.id);
                      const on = String(form.psychologist) === String(p.id);
                      return (
                        <button type="button" key={p.id}
                          onClick={() => setForm({ ...form, psychologist: String(p.id) })}
                          aria-pressed={on}
                          style={{ textAlign: 'left', padding: '9px 11px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'var(--font-sans)', border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', transition: 'var(--transition-base)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 5 }}>
                            <span style={{ fontWeight: 700, fontSize: 13, color: on ? 'var(--blue-700)' : 'var(--text-strong)' }}>{p.name}</span>
                            <Badge tone={p.caseload >= 5 ? 'amber' : 'neutral'} size="sm">{p.caseload} case{p.caseload === 1 ? '' : 's'}</Badge>
                          </div>
                          {av.length === 0 ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--amber-600)', fontWeight: 600 }}>
                              <Icon name="alert-triangle" size={12} /> No availability set — sessions can&apos;t be booked yet
                            </span>
                          ) : (
                            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                              {av.map((b) => <Badge key={b.id} tone="success" size="sm">{blockLabel(b)}</Badge>)}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
                {isEdit && form.psychologist && String(form.psychologist) !== String(form._origPsychologist) && (
                  <div style={{ marginTop: 10, padding: '11px 13px', borderRadius: 'var(--radius-md)', background: 'var(--blue-50)', border: '1px solid var(--blue-200)' }}>
                    <label style={{ display: 'flex', gap: 9, alignItems: 'flex-start', fontSize: 12.5, color: 'var(--text-strong)', cursor: 'pointer' }}>
                      <input type="checkbox" checked={form.assignee_sees_history !== false} onChange={(e) => setForm({ ...form, assignee_sees_history: e.target.checked })} style={{ marginTop: 2, accentColor: 'var(--blue-600)' }} />
                      <span>Carry this child&apos;s session history to the new psychologist (they&apos;ll see prior records). Uncheck to give them a fresh start.</span>
                    </label>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
        <div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={!isEdit && !requiredFieldsFilled} iconLeft={<Icon name="save" size={16} />}>Save Record</Button>
        </div>
      </form>
    </div>
  );
}
