import { sunEvents } from '../sunTimes';

const hhmm = (d) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
const mins = (s) => +s.slice(0, 2) * 60 + +s.slice(3);

// Reference times (timeanddate.com / NOAA): Tel Aviv-Yafo 21 Jun 2025 05:33 / 19:49 (IDT);
// 21 Dec 2025 06:36 / 16:41 (IST); Eilat 21 Jun 05:42 / 19:44 (sunrisesunset.io).
test.each([
  ['Yafo', 2025, 5, 21, '05:33', '19:49'],
  ['Yafo', 2025, 11, 21, '06:36', '16:41'],
  ['Eilat', 2025, 5, 21, '05:42', '19:44'],
])('%s %i-%i-%i', (station, y, m, d, rise, set) => {
  const ev = sunEvents(new Date(y, m, d), new Date(y, m, d), station);
  const r = ev.find((e) => e.type === 'sunrise');
  const s = ev.find((e) => e.type === 'sunset');
  expect(Math.abs(mins(hhmm(r.time)) - mins(rise))).toBeLessThanOrEqual(2);
  expect(Math.abs(mins(hhmm(s.time)) - mins(set))).toBeLessThanOrEqual(2);
});

test('two events per day over a week', () => {
  expect(sunEvents(new Date(2026, 10, 18), new Date(2026, 10, 24), 'Haifa')).toHaveLength(14);
});
