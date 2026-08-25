import api from './client';

// Every call here degrades silently at the call site: the assistant returns 503
// when it is switched off, and no screen may break because of that.
export const polishRemark = (text) =>
  api.post('/assistant/polish-remark/', { text }).then((r) => r.data);

export const sendFeedback = (jobId, outcome) =>
  api.post(`/assistant/jobs/${jobId}/feedback/`, { outcome }).then((r) => r.data);

export const getAssistantSettings = () =>
  api.get('/assistant/settings/').then((r) => r.data);

export const saveAssistantSettings = (payload) =>
  api.put('/assistant/settings/', payload).then((r) => r.data);

export const getLatestBrief = (childId) =>
  api.get(`/assistant/brief/child/${childId}/latest/`).then((r) => r.data);

export const generateBrief = (childId) =>
  api.post(`/assistant/brief/child/${childId}/`).then((r) => r.data);

// Fire and forget. Failures here are invisible on purpose: a schedule screen
// must not report that a background convenience did not happen.
export const prefetchBriefs = () =>
  api.post('/assistant/prefetch-briefs/').catch(() => null);
