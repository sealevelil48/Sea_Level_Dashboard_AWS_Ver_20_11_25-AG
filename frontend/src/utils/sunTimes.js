/**
 * Sunrise and sunset for the dashboard's stations (NOAA solar position algorithm, ±1–2 min).
 *
 * The chart draws DB timestamps, which are Israel wall-clock time, as browser-local Dates.
 * Sun times are therefore returned the same way: Israel wall-clock time as a local Date,
 * so the markers line up with the data whatever time zone the browser is in.
 */

export const STATION_COORDS = {
  Acre: { lat: 32.92, lon: 35.07 },
  Haifa: { lat: 32.82, lon: 34.99 },
  Yafo: { lat: 32.05, lon: 34.75 },
  Ashdod: { lat: 31.80, lon: 34.63 },
  Ashkelon: { lat: 31.68, lon: 34.55 },
  Eilat: { lat: 29.55, lon: 34.95 },
};

const rad = (d) => (d * Math.PI) / 180;
const deg = (r) => (r * 180) / Math.PI;

/** UTC minutes after midnight of sunrise/sunset for a UTC calendar day, or null (polar day/night). */
function sunEventUtcMinutes(y, m, d, lat, lon, rising) {
  const jd = Date.UTC(y, m - 1, d) / 86400000 + 2440587.5;
  const t = (jd + 0.5 - 2451545.0) / 36525; // noon
  const L0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360;
  const M = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
  const C = Math.sin(rad(M)) * (1.914602 - t * (0.004817 + 0.000014 * t))
    + Math.sin(rad(2 * M)) * (0.019993 - 0.000101 * t) + Math.sin(rad(3 * M)) * 0.000289;
  const lambda = L0 + C - 0.00569 - 0.00478 * Math.sin(rad(125.04 - 1934.136 * t));
  const eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60;
  const eps = eps0 + 0.00256 * Math.cos(rad(125.04 - 1934.136 * t));
  const decl = deg(Math.asin(Math.sin(rad(eps)) * Math.sin(rad(lambda))));
  const yv = Math.tan(rad(eps / 2)) ** 2;
  const eqTime = 4 * deg(yv * Math.sin(2 * rad(L0)) - 2 * e * Math.sin(rad(M))
    + 4 * e * yv * Math.sin(rad(M)) * Math.cos(2 * rad(L0))
    - 0.5 * yv * yv * Math.sin(4 * rad(L0)) - 1.25 * e * e * Math.sin(2 * rad(M)));
  const cosH = (Math.cos(rad(90.833)) - Math.sin(rad(lat)) * Math.sin(rad(decl)))
    / (Math.cos(rad(lat)) * Math.cos(rad(decl)));
  if (cosH < -1 || cosH > 1) return null;
  const ha = deg(Math.acos(cosH));
  return 720 - 4 * (lon + (rising ? ha : -ha)) - eqTime;
}

const ISRAEL = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Jerusalem', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

/** A UTC instant → Israel wall-clock time as a browser-local Date (the chart's convention). */
function toIsraelWallClock(utcMs) {
  const p = Object.fromEntries(ISRAEL.formatToParts(new Date(utcMs)).map((x) => [x.type, x.value]));
  return new Date(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute);
}

/**
 * Sunrise/sunset events between two dates (inclusive days) for a station.
 * @returns {Array<{type: 'sunrise'|'sunset', time: Date}>}
 */
export function sunEvents(start, end, station = 'Haifa') {
  const { lat, lon } = STATION_COORDS[station] || STATION_COORDS.Haifa;
  const out = [];
  const day = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const last = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  for (let guard = 0; day <= last && guard < 800; guard += 1) {
    const [y, m, d] = [day.getFullYear(), day.getMonth() + 1, day.getDate()];
    [['sunrise', true], ['sunset', false]].forEach(([type, rising]) => {
      const minutes = sunEventUtcMinutes(y, m, d, lat, lon, rising);
      if (minutes != null) out.push({ type, time: toIsraelWallClock(Date.UTC(y, m - 1, d) + minutes * 60000) });
    });
    day.setDate(day.getDate() + 1);
  }
  return out;
}
