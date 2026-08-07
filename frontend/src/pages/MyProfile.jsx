import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Card, Button, Badge, Alert, Input, FormField, Avatar, RoleBadge, Icon, PAGE } from '../ui';

// DEMO PROTOTYPE ONLY (product decision 2026-07-18): optional extra details
// for Social Worker / Psychologist accounts — social media links and address.
// Nothing here touches the backend; entries live in this browser's
// localStorage so the demo survives a refresh but is not real account data.
const EMPTY = { facebook: '', twitter: '', instagram: '', address: '' };

const FIELDS = [
  ['facebook', 'Facebook Profile', 'facebook', 'https://facebook.com/your.name'],
  ['twitter', 'X (Twitter)', 'twitter', 'https://x.com/yourhandle'],
  ['instagram', 'Instagram', 'instagram', 'https://instagram.com/yourhandle'],
  ['address', 'Home Address', 'map-pin', 'House No., Street, Barangay, City/Municipality, Province'],
];

export default function MyProfile() {
  const { user } = useAuth();
  const toast = useToast();
  const storageKey = `nacc-profile-demo:${user?.id ?? 'anon'}`;
  const [form, setForm] = useState(EMPTY);
  const [savedAt, setSavedAt] = useState(null);

  useEffect(() => {
    try { setForm({ ...EMPTY, ...JSON.parse(localStorage.getItem(storageKey) || '{}') }); }
    catch { setForm(EMPTY); }
  }, [storageKey]);

  const save = (e) => {
    e.preventDefault();
    try { localStorage.setItem(storageKey, JSON.stringify(form)); } catch { /* private browsing */ }
    setSavedAt(new Date());
    toast.success('Profile details saved (demo only — not sent to the system).');
  };

  return (
    <div style={{ ...PAGE, maxWidth: 720 }}>
      <Alert tone="warning" icon={<Icon name="flask-conical" size={18} />} style={{ marginBottom: 16 }}>
        <strong>Prototype preview.</strong> These optional details are a demo of a
        planned feature — they are stored only in this browser and are not part
        of your real account yet.
      </Alert>

      <Card padding="24px" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Avatar name={user?.fullname || user?.username || 'User'} tone="brand" size="lg" />
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 18, color: 'var(--text-strong)' }}>
              {user?.fullname || user?.username}
            </div>
            <div className="racco-mono" style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{user?.email}</div>
          </div>
          {user?.role_name && <RoleBadge role={user.role_name} />}
        </div>
        {user?.contact_details && (
          <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="phone" size={14} /> {user.contact_details}
          </div>
        )}
      </Card>

      <Card eyebrow="Optional Details" title="Social Media & Address" padding="24px">
        <form onSubmit={save} style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 8 }}>
          {FIELDS.map(([key, label, icon, placeholder]) => (
            <FormField key={key} label={label}>
              <Input value={form[key]} placeholder={placeholder} leading={<Icon name={icon} size={16} />}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            </FormField>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button type="submit" variant="primary" iconLeft={<Icon name="save" size={16} />}>Save Details</Button>
            {savedAt && <Badge tone="success" size="sm" dot>Saved {savedAt.toLocaleTimeString()}</Badge>}
          </div>
        </form>
      </Card>
    </div>
  );
}
