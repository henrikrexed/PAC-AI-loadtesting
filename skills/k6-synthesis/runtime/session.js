// session.js — per-VU-iteration cookie isolation (G2, §3.3 rule 3).
// k6-only (imports k6/http); not imported by Node unit tests.
import http from 'k6/http';

// Reset the cookie jar at the start of each journey iteration so every
// iteration models a FRESH user (k6 persists cookies across iterations per VU
// by default, which would bleed session state between simulated users).
export function resetUserSession(url) {
  const jar = http.cookieJar();
  if (!jar) return;
  if (url && typeof jar.clear === 'function') jar.clear(url);
  else if (typeof jar.clear === 'function') jar.clear();
}
