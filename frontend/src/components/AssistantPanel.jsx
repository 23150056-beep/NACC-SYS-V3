import React, { useCallback, useRef, useState } from 'react';
import { askAssistant } from '../api/assistant';
import { Icon, Input } from '../ui';

/* The chatbot, docked on every protected screen.
 *
 * The model picks a tool; the server runs the query and sends back plain data.
 * Nothing rendered here is model prose — every name, date and count below came
 * out of the database under the caller's own scope. That is what makes an
 * invented child name impossible rather than merely unlikely.
 *
 * The echo line is not decoration. A turn can go wrong in exactly one way the
 * validator cannot catch: the model hears "this week" as "today" and produces
 * a plausible answer to a question nobody asked. Showing what was understood,
 * above the answer, is the mitigation.
 */

const SUGGESTIONS = [
  'Who am I seeing tomorrow?',
  'How many children am I handling?',
  'Who still needs a follow-up?',
];

/* Server-side cap. Mirrored so the user is stopped by a counter rather than a
 * 400 they cannot see coming. */
const MAX_QUESTION = 150;

function Line({ children, muted = false }) {
  return (
    <div style={{
      fontSize: 'var(--text-sm)',
      color: muted ? 'var(--text-muted)' : 'var(--text-body)',
      padding: '3px 0',
    }}>{children}</div>
  );
}

function Answer({ result }) {
  const { kind } = result || {};

  if (kind === 'count') {
    return (
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{
          fontFamily: 'var(--font-display)', fontSize: 'var(--text-2xl)',
          fontWeight: 700, color: 'var(--text-strong)',
        }}>{result.count}</span>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {result.status === 'any' ? 'children on record' : `${result.status} children`}
        </span>
      </div>
    );
  }

  if (kind === 'appointments') {
    if (!result.items.length) return <Line muted>Nothing scheduled.</Line>;
    return result.items.map((a, i) => (
      <Line key={i}>
        <strong>{a.child}</strong>
        <span style={{ color: 'var(--text-muted)' }}> · {a.when} · {a.purpose}</span>
      </Line>
    ));
  }

  if (kind === 'children') {
    if (result.items.length) {
      return result.items.map((c) => <Line key={c.id}>{c.name}</Line>);
    }
    // No match. Rather than a bare "none", show what the agency actually
    // records — the model's clinical vocabulary and this agency's do not always
    // use the same words, and a dead end tells the user nothing.
    return (
      <>
        <Line muted>No open concern matches that wording.</Line>
        {result.available?.length > 0 && (
          <div style={{ marginTop: 6 }}>
            <Line muted>Concerns currently recorded in your caseload:</Line>
            {result.available.map((d) => <Line key={d}>· {d}</Line>)}
          </div>
        )}
      </>
    );
  }

  if (kind === 'care_gaps') {
    if (!result.items.length) return <Line muted>Nobody is overdue.</Line>;
    return result.items.map((g, i) => (
      <Line key={i}>
        <strong>{g.child}</strong>
        {/* The sentence the Monitoring screen shows, not the internal slug. */}
        <span style={{ color: 'var(--text-muted)' }}> · {g.message || g.type}</span>
      </Line>
    ));
  }

  if (kind === 'summary') {
    if (result.match === 'none') {
      return <Line muted>No child of yours matches “{result.name}”.</Line>;
    }
    if (result.match === 'several') {
      return (
        <>
          <Line muted>Several children match — which one?</Line>
          {result.items.map((c) => <Line key={c.id}>· {c.name}</Line>)}
        </>
      );
    }
    return (
      <>
        <Line><strong>{result.child.name}</strong>
          <span style={{ color: 'var(--text-muted)' }}> · {result.child.status}</span>
        </Line>
        {result.gaps?.length > 0 && (
          <Line muted>Needs attention: {result.gaps.join(', ')}</Line>
        )}
        {result.remarks?.length > 0 && (
          <div style={{ marginTop: 6 }}>
            {result.remarks.map((r, i) => (
              <Line key={i} muted>{r.date}: {r.text}</Line>
            ))}
          </div>
        )}
      </>
    );
  }

  if (kind === 'message') return <Line muted>{result.text}</Line>;
  return null;
}

export default function AssistantPanel() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState([]);
  const scroller = useRef(null);

  const send = useCallback(async (text) => {
    const asked = (text ?? '').trim();
    if (!asked || busy) return;
    setBusy(true);
    setQuestion('');
    let turn;
    try {
      const data = await askAssistant(asked);
      turn = { asked, ...data };
    } catch (err) {
      // 503 is the assistant switched off or the runtime down. Neither is an
      // error the user caused, and neither may break the panel.
      const off = err?.response?.status === 503;
      turn = {
        asked,
        ok: false,
        message: off
          ? 'The assistant is unavailable right now. Everything else still works.'
          : 'Something went wrong on the way to the assistant.',
      };
    }
    setTurns((prev) => [...prev, turn]);
    setBusy(false);
    requestAnimationFrame(() => {
      if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
    });
  }, [busy]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open the assistant"
        style={{
          position: 'fixed', right: 20, bottom: 20, zIndex: 60,
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 16px', cursor: 'pointer',
          background: 'var(--brand)', color: 'var(--text-on-brand)',
          border: 'none', borderRadius: 'var(--radius-pill)',
          boxShadow: 'var(--shadow-lg)',
          fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', fontWeight: 600,
        }}
      >
        <Icon name="message-circle" size={18} />
        Ask
      </button>
    );
  }

  return (
    <div
      style={{
        position: 'fixed', right: 20, bottom: 20, zIndex: 60,
        width: 'min(380px, calc(100vw - 40px))',
        maxHeight: 'min(560px, calc(100vh - 40px))',
        display: 'flex', flexDirection: 'column',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-xl)',
        overflow: 'hidden',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--space-3) var(--space-4)',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 700,
          fontSize: 'var(--text-sm)', color: 'var(--text-strong)',
        }}>Assistant</div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Close the assistant"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', display: 'flex', padding: 4,
          }}
        >
          <Icon name="x" size={16} />
        </button>
      </div>

      <div
        ref={scroller}
        className="racco-scroll"
        style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-4)' }}
      >
        {turns.length === 0 && (
          <div>
            <Line muted>
              I answer from your own records — your schedule, your children,
              and who needs follow-up.
            </Line>
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  style={{
                    textAlign: 'left', cursor: 'pointer',
                    padding: '7px 10px',
                    background: 'var(--surface-sunken)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-body)', font: 'inherit',
                    fontSize: 'var(--text-sm)',
                  }}
                >{s}</button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <div key={i} style={{ marginBottom: 'var(--space-4)' }}>
            <div style={{
              fontSize: 'var(--text-sm)', fontWeight: 600,
              color: 'var(--text-strong)', marginBottom: 4,
            }}>{t.asked}</div>

            {/* What the system understood, above the answer it gives. */}
            {t.echo && (
              <div style={{
                fontSize: 'var(--text-xs)', color: 'var(--text-muted)',
                marginBottom: 6, fontStyle: 'italic',
              }}>{t.echo}</div>
            )}

            <div style={{
              padding: 'var(--space-3)',
              background: 'var(--surface-sunken)',
              borderRadius: 'var(--radius-md)',
            }}>
              {t.ok ? <Answer result={t.result} /> : <Line muted>{t.message}</Line>}
            </div>
          </div>
        ))}

        {busy && <Line muted>Thinking…</Line>}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(question); }}
        style={{
          display: 'flex', gap: 8, alignItems: 'center',
          padding: 'var(--space-3) var(--space-4)',
          borderTop: '1px solid var(--border)',
        }}
      >
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value.slice(0, MAX_QUESTION))}
          placeholder="Ask about your caseload…"
          size="sm"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          aria-label="Send"
          style={{
            flex: 'none', display: 'flex', padding: 8,
            cursor: busy || !question.trim() ? 'default' : 'pointer',
            opacity: busy || !question.trim() ? 0.4 : 1,
            background: 'var(--brand)', color: 'var(--text-on-brand)',
            border: 'none', borderRadius: 'var(--radius-md)',
          }}
        >
          <Icon name="send" size={16} />
        </button>
      </form>
    </div>
  );
}
