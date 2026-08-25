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
