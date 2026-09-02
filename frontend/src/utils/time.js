/* One answer to "when was this?", for every screen that asks.
 *
 * There were three of these — in Topbar, Users and AccessRequests — copied
 * and then drifted apart. They disagreed on the things a reader actually
 * notices: one floored at "1 min ago" and one happily printed "0 min ago";
 * one wrote "2 days ago" and the others "2 d ago"; one said nothing at all
 * for something that happened seconds ago. The same event was described
 * differently depending on which screen you were looking at.
 *
 * The rules below are the union of what the three were reaching for:
 * a plain phrase while it is still recent, an exact date once "n days ago"
 * stops being easier to read than the date itself.
 */

const DATE = { day: 'numeric', month: 'short', year: 'numeric' };

/** "12 Aug 2026, 3:40 PM" — the full moment, for tooltips and fact rows. */
export function exactDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    ...DATE, hour: 'numeric', minute: '2-digit',
  });
}

/** "12 Aug 2026" — the day, without the time. */
export function shortDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(undefined, DATE);
}

/** "just now" · "5 min ago" · "3 hr ago" · "2 d ago" · "12 Aug 2026". */
export function timeAgo(iso) {
  if (!iso) return '—';
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 60) return 'just now';
  // Rounding alone produced "0 min ago" for anything under 30 seconds that
  // slipped past the check above (a clock skewed a little into the future).
  if (secs < 3600) return `${Math.max(1, Math.round(secs / 60))} min ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)} hr ago`;
  if (secs < 604800) return `${Math.round(secs / 86400)} d ago`;
  // Past a week, "9 d ago" makes the reader do arithmetic. Give them the date.
  return new Date(iso).toLocaleDateString(undefined, DATE);
}
