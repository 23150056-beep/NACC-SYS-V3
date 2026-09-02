// RACCO I Design System — primitives ported from the Claude Design workspace kit.
// Token-driven inline styles; one import surface for every screen.
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import * as Lucide from 'lucide-react';

/* ----------------------------- Icon ----------------------------- */
function toPascal(name) {
  return String(name)
    .split(/[-_]/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join('');
}
export function Icon({ name, size = 20, strokeWidth = 2, style = {}, ...rest }) {
  const Cmp = Lucide[toPascal(name)] || Lucide.Circle;
  return <Cmp size={size} strokeWidth={strokeWidth} style={{ display: 'inline-flex', flex: 'none', ...style }} {...rest} />;
}

/* ----------------------- Role / severity meta ----------------------- */
export const ROLE_META = {
  Administrator: { color: 'var(--blue-600)', soft: 'var(--blue-50)', tone: 'brand', icon: 'shield', desc: 'Full system access — users, records, clinical oversight, compliance.' },
  Psychologist: { color: 'var(--red-500)', soft: 'var(--red-50)', tone: 'red', icon: 'heart-handshake', desc: 'Assessment tools, clinical questionnaires & psychologist reporting.' },
  Staff: { color: 'var(--amber-500)', soft: 'var(--amber-50)', tone: 'amber', icon: 'folder-heart', desc: 'Child & guardian records, plus read-only counseling results.' },
};

/* What a role actually opens up, in the words of the people who use it. Lives
 * here rather than on one page because two screens hand out roles — the access
 * queue grants one, User Management corrects one — and they must not describe
 * the same role differently. Mirrors the RBAC matrix in
 * docs/CLOUD-DEPLOYMENT.md; if that matrix moves, this has to move with it. */
const ROLE_ACCESS = {
  Administrator: [
    'User accounts, roles and access requests',
    'Settings, AI switches and catalogue governance',
    'Every report in the agency',
  ],
  Psychologist: [
    'The pre-assessment flow for assigned children',
    'Remarks, treatment plans and result entries',
    'Report uploads and the instruments catalogue',
    'Their own availability and appointments',
  ],
  Staff: [
    'Child and guardian records',
    'Monitoring and agency summaries (read-only)',
    'Booking against psychologist availability',
  ],
};


/* ----------------------------- Avatar ----------------------------- */
export function Avatar({ name = '', initials = '', tone = 'brand', size = 'md', src = null, style = {} }) {
  const tones = {
    brand: ['var(--blue-100)', 'var(--blue-700)'],
    amber: ['var(--amber-100)', 'var(--amber-700)'],
    red: ['var(--red-100)', 'var(--red-700)'],
    neutral: ['var(--ink-100)', 'var(--ink-600)'],
  };
  const [bg, fg] = tones[tone] || tones.brand;
  const sizes = { sm: 28, md: 38, lg: 48, xl: 64 };
  const dim = sizes[size] || (typeof size === 'number' ? size : 38);
  const text = (initials || name.split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('') || '?').toUpperCase();
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: dim, height: dim, borderRadius: '50%', flex: 'none',
        background: src ? `center/cover no-repeat url(${src})` : bg, color: fg,
        fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: dim * 0.4, lineHeight: 1,
        boxShadow: 'inset 0 0 0 1px rgba(22,33,106,0.06)', ...style,
      }}
    >
      {!src && text}
    </span>
  );
}

/* ----------------------------- Badge ----------------------------- */
export function Badge({ children, tone = 'neutral', solid = false, size = 'md', dot = false, style = {} }) {
  const tones = {
    neutral: { soft: ['var(--ink-100)', 'var(--ink-700)'], solid: ['var(--ink-600)', '#fff'] },
    brand: { soft: ['var(--blue-50)', 'var(--blue-700)'], solid: ['var(--blue-600)', '#fff'] },
    success: { soft: ['var(--success-50)', 'var(--success-700)'], solid: ['var(--success-500)', '#fff'] },
    warning: { soft: ['var(--warning-50)', 'var(--warning-700)'], solid: ['var(--warning-500)', '#fff'] },
    danger: { soft: ['var(--red-50)', 'var(--red-700)'], solid: ['var(--red-500)', '#fff'] },
    amber: { soft: ['var(--amber-50)', 'var(--amber-700)'], solid: ['var(--amber-400)', 'var(--amber-900)'] },
  };
  const t = tones[tone] || tones.neutral;
  const [bg, fg] = solid ? t.solid : t.soft;
  const sizes = { sm: { fs: 11, pad: '2px 8px', h: 18 }, md: { fs: 12, pad: '4px 11px', h: 22 }, lg: { fs: 13, pad: '5px 13px', h: 26 } };
  const s = sizes[size] || sizes.md;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: s.h, padding: s.pad, background: bg, color: fg, fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: s.fs, lineHeight: 1, borderRadius: 'var(--radius-pill)', letterSpacing: '0.01em', whiteSpace: 'nowrap', ...style }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: '50%', background: solid ? '#fff' : fg, opacity: solid ? 0.9 : 1 }} />}
      {children}
    </span>
  );
}

/* ----------------------------- Button ----------------------------- */
export function Button({ children, variant = 'primary', size = 'md', iconLeft = null, iconRight = null, fullWidth = false, disabled = false, type = 'button', onClick, style = {}, ...rest }) {
  const sizes = {
    sm: { height: 34, padding: '0 14px', fontSize: 13, gap: 6, radius: 'var(--radius-sm)' },
    md: { height: 42, padding: '0 18px', fontSize: 15, gap: 8, radius: 'var(--radius-md)' },
    lg: { height: 50, padding: '0 26px', fontSize: 17, gap: 10, radius: 'var(--radius-lg)' },
  };
  const variants = {
    primary: { background: 'var(--blue-600)', color: '#fff', border: '1px solid var(--blue-600)', boxShadow: 'var(--shadow-brand)' },
    secondary: { background: 'var(--surface)', color: 'var(--blue-700)', border: '1px solid var(--blue-200)', boxShadow: 'var(--shadow-xs)' },
    accent: { background: 'var(--amber-400)', color: 'var(--amber-900)', border: '1px solid var(--amber-400)', boxShadow: 'var(--shadow-sm)' },
    danger: { background: 'var(--red-500)', color: '#fff', border: '1px solid var(--red-500)', boxShadow: 'var(--shadow-sm)' },
    ghost: { background: 'transparent', color: 'var(--text-body)', border: '1px solid transparent', boxShadow: 'none' },
  };
  const s = sizes[size] || sizes.md;
  const v = variants[variant] || variants.primary;
  return (
    <button
      type={type} disabled={disabled} onClick={onClick}
      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: s.gap, height: s.height, padding: s.padding, fontSize: s.fontSize, fontFamily: 'var(--font-sans)', fontWeight: 700, lineHeight: 1, borderRadius: s.radius, cursor: disabled ? 'not-allowed' : 'pointer', width: fullWidth ? '100%' : 'auto', whiteSpace: 'nowrap', opacity: disabled ? 0.5 : 1, transition: 'transform var(--dur-fast) var(--ease-out), filter var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out)', ...v, ...style }}
      onMouseDown={(e) => { if (!disabled) e.currentTarget.style.transform = 'translateY(1px)'; }}
      onMouseUp={(e) => { if (!disabled) e.currentTarget.style.transform = 'translateY(-1px)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.filter = 'none'; e.currentTarget.style.background = v.background; e.currentTarget.style.boxShadow = v.boxShadow; }}
      onMouseEnter={(e) => { if (disabled) return; e.currentTarget.style.transform = 'translateY(-1px)'; if (variant === 'ghost') { e.currentTarget.style.background = 'var(--ink-50)'; } else { e.currentTarget.style.filter = 'brightness(0.96)'; e.currentTarget.style.boxShadow = 'var(--shadow-md)'; } }}
      {...rest}
    >
      {iconLeft && <span style={{ display: 'inline-flex' }}>{iconLeft}</span>}
      {children}
      {iconRight && <span style={{ display: 'inline-flex' }}>{iconRight}</span>}
    </button>
  );
}

/* ----------------------------- Card ----------------------------- */
export function Card({ children, title = null, eyebrow = null, actions = null, footer = null, padding = 'var(--space-6)', interactive = false, accent = null, style = {} }) {
  return (
    <div
      style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)', overflow: 'hidden', position: 'relative', transition: interactive ? 'box-shadow var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out)' : 'none', ...style }}
      onMouseEnter={interactive ? (e) => { e.currentTarget.style.boxShadow = 'var(--shadow-lg)'; e.currentTarget.style.transform = 'translateY(-2px)'; } : undefined}
      onMouseLeave={interactive ? (e) => { e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; e.currentTarget.style.transform = 'translateY(0)'; } : undefined}
    >
      {accent && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: accent }} />}
      {(title || actions || eyebrow) && (
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, padding: `var(--space-5) ${padding} 0` }}>
          <div>
            {eyebrow && <div className="racco-eyebrow" style={{ marginBottom: 4 }}>{eyebrow}</div>}
            {title && <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-strong)', margin: 0 }}>{title}</h3>}
          </div>
          {actions && <div style={{ flex: 'none' }}>{actions}</div>}
        </div>
      )}
      <div style={{ padding }}>{children}</div>
      {footer && <div style={{ padding: `0 ${padding} var(--space-5)`, borderTop: '1px solid var(--border)', marginTop: -4, paddingTop: 'var(--space-4)' }}>{footer}</div>}
    </div>
  );
}

/* ----------------------------- StatCard ----------------------------- */
export function StatCard({ label, value, tone = 'brand', icon = null, trend = null, trendDir = 'up', hint = null, style = {} }) {
  const tones = { brand: 'var(--blue-600)', red: 'var(--red-500)', amber: 'var(--amber-500)', success: 'var(--success-500)', neutral: 'var(--ink-700)' };
  const chipBg = { brand: 'var(--blue-50)', red: 'var(--red-50)', amber: 'var(--amber-50)', success: 'var(--success-50)', neutral: 'var(--ink-100)' };
  const c = tones[tone] || tones.brand;
  const up = trendDir === 'up';
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)', padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 10, ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 'var(--text-xs)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{label}</span>
        {icon && <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32, borderRadius: 'var(--radius-md)', background: chipBg[tone] || chipBg.brand, color: c }}>{icon}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 'var(--text-4xl)', lineHeight: 1, color: c, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        {trend && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, fontSize: 'var(--text-xs)', fontWeight: 700, marginBottom: 6, whiteSpace: 'nowrap', color: up ? 'var(--success-600)' : 'var(--red-600)' }}>{up ? '▲' : '▼'} {trend}</span>}
      </div>
      {hint && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-faint)' }}>{hint}</span>}
    </div>
  );
}

/* ----------------------------- ConfidenceMeter ----------------------------- */
export function ConfidenceMeter({ value = 0, tone = 'brand', label = 'Confidence', showValue = true, threshold = null, style = {} }) {
  const v = Math.max(0, Math.min(100, value));
  const tones = { brand: 'var(--blue-600)', success: 'var(--success-500)', warning: 'var(--warning-500)', danger: 'var(--red-500)' };
  const c = tones[tone] || tones.brand;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 'var(--text-xs)', letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{label}</span>
        {showValue && <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 'var(--text-base)', color: c, fontVariantNumeric: 'tabular-nums' }}>{v}%</span>}
      </div>
      <div style={{ position: 'relative', height: 9, borderRadius: 'var(--radius-pill)', background: 'var(--ink-100)', overflow: 'hidden' }}>
        <div style={{ width: `${v}%`, height: '100%', borderRadius: 'var(--radius-pill)', background: c, transition: 'width var(--dur-slow) var(--ease-out)' }} />
      </div>
      {threshold != null && (
        <div style={{ position: 'relative', height: 0 }}>
          <span style={{ position: 'absolute', left: `${threshold}%`, top: -16, transform: 'translateX(-50%)', width: 2, height: 13, background: 'var(--ink-400)' }} />
        </div>
      )}
    </div>
  );
}

/* ----------------------------- Alert ----------------------------- */
export function Alert({ children, tone = 'info', title = null, icon = null, disclaimer = false, style = {} }) {
  if (disclaimer) {
    return (
      <div style={{ background: 'var(--ink-50)', borderLeft: '3px solid var(--ink-400)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontStyle: 'italic', lineHeight: 1.5, ...style }}>
        {title && <strong style={{ color: 'var(--text-body)', fontStyle: 'normal' }}>{title} </strong>}
        {children}
      </div>
    );
  }
  const tones = {
    info: ['var(--blue-50)', 'var(--blue-200)', 'var(--blue-700)'],
    success: ['var(--success-50)', 'var(--success-100)', 'var(--success-700)'],
    warning: ['var(--warning-50)', 'var(--warning-100)', 'var(--warning-700)'],
    danger: ['var(--red-50)', 'var(--red-100)', 'var(--red-700)'],
  };
  const [bg, bd, fg] = tones[tone] || tones.info;
  return (
    <div style={{ display: 'flex', gap: 12, background: bg, border: `1px solid ${bd}`, borderRadius: 'var(--radius-md)', padding: 'var(--space-4)', ...style }}>
      {icon && <span style={{ flex: 'none', color: fg, display: 'inline-flex', marginTop: 1 }}>{icon}</span>}
      <div style={{ flex: 1 }}>
        {title && <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 'var(--text-base)', color: fg, marginBottom: 3 }}>{title}</div>}
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-body)', lineHeight: 1.55 }}>{children}</div>
      </div>
    </div>
  );
}

/* ----------------------------- EmptyState ----------------------------- */
export function EmptyState({ title, description = null, icon = null, action = null, style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 10, padding: 'var(--space-9) var(--space-6)', ...style }}>
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: '50%', background: 'var(--blue-50)', color: 'var(--blue-400)', marginBottom: 4 }}>{icon}</span>}
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>{title}</div>
      {description && <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', maxWidth: 340, lineHeight: 1.55 }}>{description}</div>}
      {action && <div style={{ marginTop: 8 }}>{action}</div>}
    </div>
  );
}

/* ----------------------------- FormField ----------------------------- */
export function FormField({ label, htmlFor, hint = null, error = null, required = false, children, style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      {label && (
        <label htmlFor={htmlFor} style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--text-strong)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          {label}
          {required && <span style={{ color: 'var(--red-500)' }}>*</span>}
        </label>
      )}
      {children}
      {error ? (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--red-600)', fontWeight: 600 }}>{error}</span>
      ) : (
        hint && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{hint}</span>
      )}
    </div>
  );
}

/* ----------------------------- Input ----------------------------- */
export function Input({ value, onChange, placeholder, type = 'text', size = 'md', leading = null, trailing = null, invalid = false, disabled = false, fullWidth = true, style = {}, ...rest }) {
  const heights = { sm: 'var(--field-h-sm)', md: 'var(--field-h)', lg: 50 };
  const h = heights[size] || heights.md;
  const [focus, setFocus] = useState(false);
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, width: fullWidth ? '100%' : 'auto', height: h, padding: '0 12px', background: disabled ? 'var(--ink-50)' : 'var(--surface)', border: `1px solid ${invalid ? 'var(--red-400)' : focus ? 'var(--blue-500)' : 'var(--border-strong)'}`, borderRadius: 'var(--radius-md)', boxShadow: focus ? (invalid ? '0 0 0 3px var(--red-100)' : 'var(--shadow-focus)') : 'none', transition: 'border-color var(--dur-fast), box-shadow var(--dur-fast)', ...style }}>
      {leading && <span style={{ display: 'inline-flex', color: 'var(--text-faint)', flex: 'none' }}>{leading}</span>}
      <input
        type={type} value={value} onChange={onChange} placeholder={placeholder} disabled={disabled}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', boxShadow: 'none', background: 'transparent', fontFamily: 'var(--font-sans)', fontSize: size === 'sm' ? 13 : 15, color: 'var(--text-strong)', height: '100%' }}
        {...rest}
      />
      {trailing && <span style={{ display: 'inline-flex', color: 'var(--text-faint)', flex: 'none' }}>{trailing}</span>}
    </div>
  );
}

/* ----------------------------- FileUpload ----------------------------- */
function humanFileSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
const FILE_TYPE_ICONS = { pdf: 'file-text', doc: 'file-text', docx: 'file-text', jpg: 'image', jpeg: 'image', png: 'image' };

/* Styled replacement for the bare <input type="file">: an explicit upload
 * button, then a green "attached" preview chip (file-type icon + name + size)
 * so it's obvious at a glance that the file is in place before submitting. */
export function FileUpload({ file, onChange, accept = '', buttonLabel = 'Choose file', style = {} }) {
  const inputRef = useRef(null);
  const pick = () => inputRef.current?.click();
  const ext = file && file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, ...style }}>
      <input
        ref={inputRef} type="file" accept={accept} style={{ display: 'none' }}
        onChange={(e) => { onChange(e.target.files?.[0] || null); e.target.value = ''; }}
      />
      {!file ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px', border: '1.5px dashed var(--border-strong)', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)' }}>
          <Icon name="file-up" size={20} style={{ color: 'var(--text-faint)' }} />
          <span style={{ flex: 1, fontSize: 13, color: 'var(--text-muted)' }}>No file selected yet.</span>
          <Button variant="secondary" size="sm" onClick={pick} iconLeft={<Icon name="upload" size={15} />}>{buttonLabel}</Button>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px', border: '1px solid var(--success-100)', borderRadius: 'var(--radius-md)', background: 'var(--success-50)' }}>
          <Icon name={FILE_TYPE_ICONS[ext] || 'file'} size={20} style={{ color: 'var(--success-600)' }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, fontWeight: 600, color: 'var(--success-700)' }}>
              <Icon name="check-circle-2" size={13} />
              Attached{file.size ? ` · ${humanFileSize(file.size)}` : ''} — ready to upload
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={pick} iconLeft={<Icon name="refresh-cw" size={14} />}>Replace</Button>
          <button type="button" title="Remove file" onClick={() => onChange(null)} style={iconBtn('var(--red-500)', 28)}>
            <Icon name="x" size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

/* ----------------------------- Select ----------------------------- */
export function Select({ value, onChange, children, size = 'md', invalid = false, disabled = false, fullWidth = true, style = {}, ...rest }) {
  const heights = { sm: 'var(--field-h-sm)', md: 'var(--field-h)', lg: 50 };
  const h = heights[size] || heights.md;
  const [focus, setFocus] = useState(false);
  return (
    <div style={{ position: 'relative', display: 'inline-flex', width: fullWidth ? '100%' : 'auto', ...style }}>
      <select
        value={value} onChange={onChange} disabled={disabled}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{ appearance: 'none', WebkitAppearance: 'none', width: '100%', height: h, padding: '0 38px 0 12px', background: disabled ? 'var(--ink-50)' : 'var(--surface)', border: `1px solid ${invalid ? 'var(--red-400)' : focus ? 'var(--blue-500)' : 'var(--border-strong)'}`, borderRadius: 'var(--radius-md)', boxShadow: focus ? 'var(--shadow-focus)' : 'none', fontFamily: 'var(--font-sans)', fontSize: size === 'sm' ? 13 : 15, color: 'var(--text-strong)', cursor: disabled ? 'not-allowed' : 'pointer', outline: 'none', transition: 'border-color var(--dur-fast), box-shadow var(--dur-fast)' }}
        {...rest}
      >
        {children}
      </select>
      <span style={{ position: 'absolute', right: 13, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--text-muted)', fontSize: 11 }}>▼</span>
    </div>
  );
}

/* ----------------------------- Switch ----------------------------- */
export function Switch({ checked = false, onChange, size = 'md', disabled = false, label = null, style = {} }) {
  const dims = { sm: { w: 34, h: 20, k: 14 }, md: { w: 44, h: 26, k: 20 } };
  const d = dims[size] || dims.md;
  const toggle = () => { if (!disabled && onChange) onChange(!checked); };
  const control = (
    <span
      role="switch" aria-checked={checked} tabIndex={disabled ? -1 : 0} onClick={toggle}
      onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); } }}
      style={{ position: 'relative', width: d.w, height: d.h, flex: 'none', borderRadius: 'var(--radius-pill)', background: checked ? 'var(--blue-600)' : 'var(--ink-300)', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1, transition: 'background var(--dur-base) var(--ease-out)', display: 'inline-block' }}
    >
      <span style={{ position: 'absolute', top: (d.h - d.k) / 2, left: checked ? d.w - d.k - (d.h - d.k) / 2 : (d.h - d.k) / 2, width: d.k, height: d.k, borderRadius: '50%', background: '#fff', boxShadow: 'var(--shadow-sm)', transition: 'left var(--dur-base) var(--ease-out)' }} />
    </span>
  );
  if (!label) return control;
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 10, cursor: disabled ? 'not-allowed' : 'pointer', ...style }}>
      {control}
      <span style={{ fontFamily: 'var(--font-sans)', fontSize: 'var(--text-base)', color: 'var(--text-body)', fontWeight: 600 }}>{label}</span>
    </label>
  );
}

/* ----------------------------- RoleBadge ----------------------------- */
const ROLES = {
  Administrator: { color: 'var(--blue-600)', bg: 'var(--blue-50)', fg: 'var(--blue-700)' },
  Staff: { color: 'var(--amber-500)', bg: 'var(--amber-50)', fg: 'var(--amber-700)' },
  Psychologist: { color: 'var(--red-500)', bg: 'var(--red-50)', fg: 'var(--red-700)' },
};
export function RoleBadge({ role = 'Staff', size = 'md', solid = false, style = {} }) {
  const r = ROLES[role] || ROLES.Staff;
  const sizes = { sm: { fs: 11, pad: '3px 9px', dot: 6 }, md: { fs: 12, pad: '4px 11px', dot: 7 } };
  const s = sizes[size] || sizes.md;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: s.pad, background: solid ? r.color : r.bg, color: solid ? '#fff' : r.fg, borderRadius: 'var(--radius-pill)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: s.fs, lineHeight: 1, whiteSpace: 'nowrap', ...style }}>
      <span style={{ width: s.dot, height: s.dot, borderRadius: '50%', background: solid ? '#fff' : r.color, flex: 'none' }} />
      {role}
    </span>
  );
}

/* -------------------------- RoleAccessPanel -------------------------- *
 * Granting a role and correcting one are the same decision seen twice, so both
 * get the same panel. With `from` it reads as a change — what the person picks
 * up, what they put down; without it, simply what the role opens up. The two
 * lists are derived rather than written per pair: three roles make six
 * directions, and prose for each would drift out of step with ROLE_ACCESS the
 * first time the matrix moves. */
export function RoleAccessPanel({ from = null, to, style = {} }) {
  const before = ROLE_ACCESS[from] || [];
  const after = ROLE_ACCESS[to] || [];
  const changing = !!from && from !== to;
  const gains = changing ? after.filter((x) => !before.includes(x)) : after;
  const loses = changing ? before.filter((x) => !after.includes(x)) : [];
  const list = (tone, icon, title, items) => (items.length === 0 ? null : (
    <div key={title}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: tone, marginBottom: 5 }}>
        <Icon name={icon} size={13} />{title}
      </div>
      <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 3 }}>
        {items.map((x) => <li key={x} style={{ fontSize: 12.5, color: 'var(--text-body)', lineHeight: 1.5 }}>{x}</li>)}
      </ul>
    </div>
  ));
  const none = (label) => <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{label}</span>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '13px 15px', background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {changing && <>{from ? <RoleBadge role={from} size="sm" /> : none('No role')}<Icon name="arrow-right" size={15} style={{ color: 'var(--text-faint)' }} /></>}
        {to ? <RoleBadge role={to} size="sm" solid /> : none('No role chosen yet')}
      </div>
      {list('var(--success-700)', changing ? 'plus' : 'key-round', changing ? 'Gains' : 'This role can', gains)}
      {list('var(--red-600)', 'minus', 'Loses', loses)}
    </div>
  );
}

/* ----------------------------- Tabs ----------------------------- */
export function Tabs({ tabs = [], active, onChange, style = {} }) {
  return (
    <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', ...style }}>
      {tabs.map((t) => {
        const on = t.id === active;
        return (
          <button key={t.id} type="button" onClick={() => onChange && onChange(t.id)}
            onMouseEnter={(e) => { if (!on) { e.currentTarget.style.color = 'var(--text-strong)'; e.currentTarget.style.borderBottomColor = 'var(--ink-300)'; } }}
            onMouseLeave={(e) => { if (!on) { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderBottomColor = 'transparent'; } }}
            style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 7, padding: '10px 14px', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 'var(--text-base)', color: on ? 'var(--blue-700)' : 'var(--text-muted)', marginBottom: -1, borderBottom: `2px solid ${on ? 'var(--blue-600)' : 'transparent'}`, transition: 'color var(--dur-fast), border-color var(--dur-fast)' }}>
            {t.label}
            {t.count != null && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, padding: '1px 7px', borderRadius: 'var(--radius-pill)', background: on ? 'var(--blue-100)' : 'var(--ink-100)', color: on ? 'var(--blue-700)' : 'var(--text-muted)' }}>{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

/* ----------------------------- Skeleton ----------------------------- *
 * Loading placeholder shaped like the content it replaces. Tables should
 * render a few skeleton ROWS rather than a spinner: the layout stops jumping,
 * and an empty list can no longer be mistaken for "there is nothing here". */
export function Skeleton({ width = '100%', height = 12, radius = 'var(--radius-xs)', style = {} }) {
  return <span className="racco-skeleton" aria-hidden="true" style={{ display: 'block', width, height, borderRadius: radius, ...style }} />;
}

/* ------------------------ Dialog behaviour (a11y) ------------------------ *
 * Everything a modal/drawer owes the keyboard: focus moves in on open, Tab is
 * trapped inside, Escape closes (when the dialog allows it), and focus returns
 * to whatever opened it. Attach the returned ref to the dialog element. */
const FOCUSABLE_SELECTOR = 'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/* Dialogs stack — a confirm can open on top of a drawer. Only the topmost one
 * may answer Escape or trap Tab, or the layer underneath drags focus back out
 * of the dialog the user is actually looking at. */
const dialogStack = [];

function useDialogBehaviour({ active = true, onClose, closeOnEscape = true } = {}) {
  const ref = useRef(null);
  // The handlers live in a ref so the effect's only dependency is `active`.
  // Re-running it would pull focus back to the first control — and callers
  // legitimately change these mid-dialog (a form flips `closeOnEscape` off the
  // moment it becomes dirty, i.e. on the user's first keystroke).
  const latest = useRef({ onClose, closeOnEscape });
  latest.current = { onClose, closeOnEscape };
  useEffect(() => {
    if (!active) return undefined;
    const token = {};
    dialogStack.push(token);
    const opener = document.activeElement;
    const node = ref.current;
    const visible = () => Array.from(node?.querySelectorAll(FOCUSABLE_SELECTOR) || [])
      .filter((el) => el.offsetParent !== null || el === document.activeElement);
    // Focus the first real control, else the dialog itself, so screen readers
    // land inside the dialog instead of continuing behind it.
    (visible()[0] || node)?.focus();
    const onKey = (e) => {
      if (dialogStack[dialogStack.length - 1] !== token) return;
      const { onClose: close, closeOnEscape: escapeCloses } = latest.current;
      if (e.key === 'Escape' && escapeCloses && close) {
        e.preventDefault(); e.stopPropagation(); close(); return;
      }
      if (e.key !== 'Tab' || !node) return;
      const items = visible();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === node)) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      const at = dialogStack.indexOf(token);
      if (at !== -1) dialogStack.splice(at, 1);
      if (opener instanceof HTMLElement && document.contains(opener)) opener.focus();
    };
  }, [active]);
  return ref;
}

/* ----------------------------- Modal ----------------------------- *
 * `dismissible={false}` for anything the user cannot get back — a one-time
 * secret, an unsaved form: a stray backdrop click must not destroy it. */
export function Modal({ open = true, onClose, title, subtitle = null, icon = null, tone = 'neutral', width = 460, dismissible = true, children, footer = null, style = {} }) {
  const ref = useDialogBehaviour({ active: open, onClose, closeOnEscape: dismissible });
  const titleId = useId();
  if (!open) return null;
  const tones = {
    neutral: ['var(--ink-100)', 'var(--ink-600)'],
    brand: ['var(--blue-50)', 'var(--blue-600)'],
    warning: ['var(--warning-50)', 'var(--warning-600)'],
    danger: ['var(--red-50)', 'var(--red-600)'],
    success: ['var(--success-50)', 'var(--success-600)'],
  };
  const [chipBg, chipFg] = tones[tone] || tones.neutral;
  return createPortal(
    <div
      onMouseDown={(e) => { if (dismissible && e.target === e.currentTarget) onClose?.(); }}
      style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 90, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}
    >
      <div
        ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        style={{ width, maxWidth: '100%', maxHeight: '100%', overflow: 'auto', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', animation: 'racco-pop-in var(--dur-base) var(--ease-out)', ...style }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 13, padding: '22px 22px 0' }}>
          {icon && <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 40, flex: 'none', borderRadius: 'var(--radius-md)', background: chipBg, color: chipFg }}>{icon}</span>}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 id={titleId} style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)', margin: 0 }}>{title}</h2>
            {subtitle && <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
          </div>
          {dismissible && (
            <button type="button" onClick={onClose} aria-label="Close" {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--text-muted)')}><Icon name="x" size={16} /></button>
          )}
        </div>
        <div style={{ padding: '16px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>{children}</div>
        {footer && <div style={{ padding: '4px 22px 22px', display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

/* ----------------------------- ConfirmDialog ----------------------------- *
 * Replaces window.confirm(). Two things the native dialog cannot do and this
 * screen needs: name the consequence in the button ("Deactivate", not "OK"),
 * and demand `confirmPhrase` be typed out for the handful of actions serious
 * enough that a mis-click must not be enough. */
export function ConfirmDialog({ open = true, onClose, onConfirm, title, description, confirmLabel = 'Confirm', cancelLabel = 'Cancel', tone = 'danger', icon = null, confirmPhrase = null, confirmHint = null, busy = false, children = null }) {
  const [typed, setTyped] = useState('');
  useEffect(() => { if (open) setTyped(''); }, [open]);
  if (!open) return null;
  const ready = !confirmPhrase || typed.trim().toLowerCase() === String(confirmPhrase).trim().toLowerCase();
  const variant = tone === 'danger' ? 'danger' : tone === 'warning' ? 'accent' : 'primary';
  const defaultConfirmHint = (
    <>Type <span className="racco-mono" style={{ fontWeight: 800, color: 'var(--text-strong)' }}>{confirmPhrase}</span> to confirm</>
  );
  return (
    <Modal
      open={open} onClose={onClose} title={title} tone={tone} icon={icon}
      subtitle={null} width={470}
      footer={<>
        <Button variant="ghost" onClick={onClose}>{cancelLabel}</Button>
        <Button variant={variant} onClick={onConfirm} disabled={!ready || busy}>{confirmLabel}</Button>
      </>}
    >
      {description && <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: 'var(--text-body)' }}>{description}</p>}
      {children}
      {/* The label is wrapped in one node on purpose: FormField's label is an
          inline-flex row with a gap, so loose siblings would be spaced apart
          in the middle of the sentence. */}
      {confirmPhrase && (
        <FormField label={<span>{confirmHint || defaultConfirmHint}</span>}>
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={confirmPhrase} autoComplete="off" />
        </FormField>
      )}
    </Modal>
  );
}

/* ----------------------------- Drawer ----------------------------- *
 * Right-hand panel for detail + edit. `dismissible` is expected to be wired to
 * a dirty check so a click on the backdrop cannot silently bin typed input. */
export function Drawer({ open = true, onClose, title, subtitle = null, avatar = null, width = 460, dismissible = true, onDismissBlocked = null, children, footer = null, as = 'div', ...rest }) {
  const close = useCallback(() => {
    if (dismissible) onClose?.(); else onDismissBlocked?.();
  }, [dismissible, onClose, onDismissBlocked]);
  const ref = useDialogBehaviour({ active: open, onClose: close });
  const titleId = useId();
  if (!open) return null;
  const Panel = as;
  return createPortal(
    <div
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
      style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.32)', display: 'flex', justifyContent: 'flex-end', zIndex: 80, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}
    >
      <Panel
        ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        style={{ width, maxWidth: '94%', height: '100%', background: 'var(--surface)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', animation: 'racco-slide-left var(--dur-slow) var(--ease-out)' }}
        {...rest}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          {avatar}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 id={titleId} style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</h2>
            {subtitle && <div style={{ fontSize: 12.5, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{subtitle}</div>}
          </div>
          <button type="button" onClick={close} aria-label="Close" {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--text-muted)')}><Icon name="x" size={17} /></button>
        </div>
        <div className="racco-scroll" style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 15 }}>{children}</div>
        {footer && <div style={{ padding: 16, borderTop: '1px solid var(--border)', display: 'flex', gap: 10 }}>{footer}</div>}
      </Panel>
    </div>,
    document.body,
  );
}

/* ----------------------------- Menu ----------------------------- *
 * Row-level action menu. One neutral trigger instead of a stripe of coloured
 * icon buttons: at ten rows those stripes are the loudest thing on the page,
 * and colour then means "there is a button here" rather than "this is
 * destructive". Rendered in a portal with fixed coordinates so an overflow
 * container cannot clip it. */
export function Menu({ items = [], label = 'More actions', trigger = null, align = 'right', size = 30 }) {
  const btnRef = useRef(null);
  const listRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(null);
  const enabled = items.filter((i) => !i.disabled && !i.separator);

  useLayoutEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const r = btnRef.current?.getBoundingClientRect();
      if (!r) return;
      const w = 252;
      const h = listRef.current?.offsetHeight || items.length * 38 + 12;
      const below = window.innerHeight - r.bottom;
      setPos({
        top: below < h + 12 && r.top > h + 12 ? r.top - h - 6 : r.bottom + 6,
        left: Math.max(8, Math.min(window.innerWidth - w - 8, align === 'right' ? r.right - w : r.left)),
        width: w,
      });
    };
    place();
    // Any scroll or resize moves the trigger out from under a fixed menu, so
    // close rather than chase it.
    const bail = () => setOpen(false);
    window.addEventListener('scroll', bail, true);
    window.addEventListener('resize', bail);
    return () => { window.removeEventListener('scroll', bail, true); window.removeEventListener('resize', bail); };
  }, [open, align, items.length]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (!listRef.current?.contains(e.target) && !btnRef.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); btnRef.current?.focus(); return; }
      const focusables = Array.from(listRef.current?.querySelectorAll('button:not([disabled])') || []);
      if (!focusables.length) return;
      const i = focusables.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); focusables[(i + 1) % focusables.length].focus(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); focusables[(i - 1 + focusables.length) % focusables.length].focus(); }
      if (e.key === 'Tab') { e.preventDefault(); setOpen(false); btnRef.current?.focus(); }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey, true);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey, true); };
  }, [open]);

  useEffect(() => {
    if (open && pos) listRef.current?.querySelector('button:not([disabled])')?.focus();
  }, [open, pos]);

  return (
    <>
      <button
        ref={btnRef} type="button" aria-label={label} aria-haspopup="menu" aria-expanded={open}
        disabled={!enabled.length}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.background = 'var(--ink-100)'; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.background = 'transparent'; }}
        style={{ ...iconBtn('var(--text-muted)', size), border: '1px solid transparent', background: open ? 'var(--ink-100)' : 'transparent', color: open ? 'var(--text-strong)' : 'var(--text-muted)', opacity: enabled.length ? 1 : 0.35, cursor: enabled.length ? 'pointer' : 'not-allowed' }}
      >
        {trigger || <Icon name="more-horizontal" size={17} />}
      </button>
      {open && createPortal(
        <div
          ref={listRef} role="menu" aria-label={label}
          onClick={(e) => e.stopPropagation()}
          style={{ position: 'fixed', top: pos?.top ?? -9999, left: pos?.left ?? -9999, width: pos?.width ?? 252, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', padding: 5, zIndex: 95, animation: 'racco-pop-in var(--dur-fast) var(--ease-out)' }}
        >
          {items.map((item, idx) => (item.separator ? (
            <div key={`sep-${idx}`} role="separator" style={{ height: 1, background: 'var(--border)', margin: '5px 4px' }} />
          ) : (
            <button
              key={item.id || item.label} type="button" role="menuitem" disabled={item.disabled}
              title={item.hint || undefined}
              onClick={() => { setOpen(false); item.onSelect?.(); }}
              onMouseEnter={(e) => { if (!item.disabled) e.currentTarget.style.background = item.tone === 'danger' ? 'var(--red-50)' : 'var(--ink-50)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', border: 'none', background: 'transparent', borderRadius: 'var(--radius-sm)', cursor: item.disabled ? 'not-allowed' : 'pointer', textAlign: 'left', fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 13.5, color: item.disabled ? 'var(--text-faint)' : item.tone === 'danger' ? 'var(--red-600)' : 'var(--text-body)', opacity: item.disabled ? 0.75 : 1 }}
            >
              {item.icon && <Icon name={item.icon} size={15} />}
              <span style={{ flex: 1 }}>{item.label}</span>
            </button>
          )))}
        </div>,
        document.body,
      )}
    </>
  );
}

/* ----------------------------- FilterPills ----------------------------- *
 * Counted status filter. The counts are the point: they double as the summary
 * of the collection, so the toolbar answers "how many need attention?" without
 * a separate row of stat tiles. */
export function FilterPills({ options = [], value, onChange, label = 'Filter', style = {} }) {
  return (
    <div role="tablist" aria-label={label} style={{ display: 'flex', gap: 7, flexWrap: 'wrap', ...style }}>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <button
            key={o.key} role="tab" aria-selected={on} type="button" onClick={() => onChange?.(o.key)}
            {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 13px', cursor: 'pointer', borderRadius: 'var(--radius-pill)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', color: on ? 'var(--blue-700)' : 'var(--text-body)', transition: 'var(--transition-base)' }}
          >
            {o.dot && <span style={{ width: 7, height: 7, borderRadius: '50%', background: o.dot, flex: 'none' }} />}
            {o.label}
            {o.count != null && <span className="racco-mono" style={{ fontSize: 11, fontWeight: 700, color: on ? 'var(--blue-600)' : 'var(--text-faint)' }}>{o.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

/* Small shared icon-button style used by drawers/tables */
export function iconBtn(color, dim = 30) {
  return { width: dim, height: dim, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', color, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', transition: 'var(--transition-base)' };
}

/* ----------------------------- Shared hover ----------------------------- *
 * One prominent hover treatment for every clickable SURFACE (cards, selection
 * tiles, option pills, icon buttons, role buttons): lift + elevated shadow +
 * a touch of brightness. Spread {...hoverLift()} onto the element. It captures
 * and restores the element's own inline transform/shadow/filter, so it composes
 * with selected/active states without clobbering them. Give the element a
 * `transition` (var(--transition-base)) so the change animates.
 * Rows and flat text controls can't lift — use hoverTint() for those. */
export function hoverLift({ lift = -2, shadow = 'var(--shadow-lg)', brightness = 0.98 } = {}) {
  return {
    onMouseEnter: (e) => {
      const el = e.currentTarget;
      el.dataset.hlShadow = el.style.boxShadow;
      el.dataset.hlTransform = el.style.transform;
      el.dataset.hlFilter = el.style.filter;
      el.style.transform = `translateY(${lift}px)`;
      el.style.boxShadow = shadow;
      el.style.filter = `brightness(${brightness})`;
    },
    onMouseLeave: (e) => {
      const el = e.currentTarget;
      el.style.transform = el.dataset.hlTransform || '';
      el.style.boxShadow = el.dataset.hlShadow || '';
      el.style.filter = el.dataset.hlFilter || '';
    },
  };
}

/* Background-tint hover for elements that must not lift (table rows, flat list
 * items). Restores whatever inline background the element already had. */
export function hoverTint(tint = 'var(--blue-50)') {
  return {
    onMouseEnter: (e) => { const el = e.currentTarget; el.dataset.htBg = el.style.background; el.style.background = tint; },
    onMouseLeave: (e) => { const el = e.currentTarget; el.style.background = el.dataset.htBg || 'transparent'; },
  };
}

export const PAGE = { padding: '24px 26px', maxWidth: 'var(--content-max)', margin: '0 auto' };
