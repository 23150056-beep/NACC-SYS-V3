# Records schedule labels — design

**Date:** 2026-07-19
**Status:** Approved
**Scope:** Frontend only (`frontend/src/pages/Children.jsx`)

## Goal

Make it easy to see, from the Records roster, which children have a session
**today** and which have one coming up soon — without opening each record. Add
a dynamic schedule label to each row, and a list of upcoming appointments in
the child detail drawer.

## Approach

Frontend join. Records already loads the children list; it will additionally
fetch `/appointments/?from=<today>&to=<today+7>`, keep only
`status === 'scheduled'`, and build a `childId → [appointments]` map sorted by
start time. No backend changes.

Rejected alternatives: a `next_appointment` serializer field (duplicates the
role-scoping already in `AppointmentViewSet`, risks N+1, grows a heavy
serializer) and a dedicated summary endpoint (a new endpoint to maintain for
one page). At this agency's scale the frontend join is simplest.

## Behavior

### Roster chip — Active / All views only

A new **Schedule** column between "Psychologist" and "Status". Each row shows:

- **`Today · 2:00 PM`** — amber chip when the child has a scheduled session
  today.
- **`Mon · Jul 21`** — neutral chip for the next scheduled booking within the
  7-day window.
- **`—`** — nothing booked in the window.

The **Archived** view (admin/staff terminated-case columns) is unchanged —
terminated cases have no active bookings.

### Drawer — "Upcoming appointments"

The child detail drawer (`ChildDrawer`) gains an **Upcoming appointments**
section listing up to 3 scheduled appointments in the next 7 days: date, time,
purpose (Pre-Assessment / Session / Follow-up), and psychologist. Placed
**above** the existing "Next possible sessions" block, so *booked*
appointments read as distinct from *suggested open slots*. Omitted when empty.

## Role behavior

No special-casing. The `/appointments/` endpoint already filters to the
requesting psychologist's own appointments, so psychologists get chips only for
their own caseload; admin/staff see all.

## Implementation notes

- Build "today" and "today+7" as **local** `YYYY-MM-DD` strings (not
  `toISOString()`, which shifts the date in UTC+8 evenings).
- Time formatting: `new Date(start)` → `toLocaleTimeString([], { hour:
  'numeric', minute: '2-digit' })`.
- Purpose labels reuse the mapping already in `Schedule.jsx`
  (`pre_assessment → Pre-Assessment`, etc.).
- Appointments fetch failure is non-fatal: the map defaults empty, chips render
  `—`, the roster still loads.
