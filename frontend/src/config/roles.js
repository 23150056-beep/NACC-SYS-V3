// Roles allowed to manage assessment instruments (questionnaires).
// Capstone RBAC = admin-only; Psychologist added per product decision 2026-06-27.
// TO REVERT instrument management to admin-only: remove 'Psychologist' from this list.
export const INSTRUMENT_MANAGER_ROLES = ['Administrator', 'Psychologist'];
