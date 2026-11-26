import React, { useMemo } from 'react';
import { Button } from 'react-bootstrap';

/**
 * Drift detection results (relative mode): deviation strip, episodes, slow-drift notice.
 *
 * deviation d(t) = (target − reference) − expected gap, smoothed; the band is ±threshold.
 * Each episode can be loaded into the correction form with "Correct this" (nothing is written
 * until the operator previews and commits).
 */
const W = 200;
const H = 56;

const fmtM = (v) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)} m`;
const fmtTime = (iso) => String(iso).replace('T', ' ').slice(5, 16); // "MM-DD HH:MM"
const fmtDuration = (min) => (min >= 120 ? `${(min / 60).toFixed(1)} h` : `${Math.round(min)} min`);

export function buildStrip(series, threshold, episodes) {
  if (!series || series.length < 2) return null;
  const t0 = new Date(series[0].t).getTime();
  const t1 = new Date(series[series.length - 1].t).getTime();
  const span = Math.max(t1 - t0, 1);
  const maxAbs = Math.max(threshold * 2, ...series.map((p) => Math.abs(p.d)));
  const x = (t) => ((new Date(t).getTime() - t0) / span) * W;
  const y = (d) => H / 2 - (d / maxAbs) * (H / 2 - 2);
  const path = series.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)} ${y(p.d).toFixed(1)}`).join(' ');
  return {
    path,
    bandTop: y(threshold),
    bandHeight: y(-threshold) - y(threshold),
    zero: y(0),
    shaded: (episodes || []).map((e) => ({ x: x(e.start), w: Math.max(x(e.end) - x(e.start), 1.5) })),
  };
}

const DriftPanel = ({ drift, threshold, onApplyEpisode }) => {
  const strip = useMemo(
    () => (drift ? buildStrip(drift.deviation, threshold, drift.episodes) : null),
    [drift, threshold]
  );
  if (!drift) return null;
  const episodes = drift.episodes || [];

  return (
    <section aria-label="Drift detection results" className="mt-2"
             style={{ border: '1px solid #2a3f5f', borderRadius: 6, padding: 8, background: 'rgba(0,0,0,0.2)' }}>
      <div className="d-flex justify-content-between align-items-baseline" style={{ fontSize: '0.72rem' }}>
        <strong style={{ color: '#E6EEF8' }}>
          {episodes.length ? `${episodes.length} drift episode${episodes.length > 1 ? 's' : ''}` : 'No drift'}
        </strong>
        <span style={{ color: '#8FA3BD' }}>
          vs {drift.reference_station} · coverage {Math.round((drift.coverage ?? 0) * 100)}%
        </span>
      </div>

      {strip && (
        <svg role="img" width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
             aria-label={`Deviation from expected gap, threshold ±${threshold} m`} style={{ display: 'block', marginTop: 4 }}>
          <rect x="0" y={strip.bandTop} width={W} height={strip.bandHeight} fill="#4CC3FF" opacity="0.10" />
          {strip.shaded.map((s, i) => (
            <rect key={i} x={s.x} y="0" width={s.w} height={H} fill="#FFB454" opacity="0.25" />
          ))}
          <line x1="0" x2={W} y1={strip.zero} y2={strip.zero} stroke="#2a3f5f" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          <path d={strip.path} fill="none" stroke="#C9A7FF" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
        </svg>
      )}

      {drift.slow_drift && (
        <div role="status" className="mt-1" style={{ fontSize: '0.7rem', color: '#FFD49A' }}>
          Slow drift {drift.slow_drift.mm_per_day > 0 ? '+' : ''}{drift.slow_drift.mm_per_day} mm/day
          {' '}since {fmtTime(drift.slow_drift.since)} (outside the episodes). Not corrected automatically.
        </div>
      )}

      {episodes.length > 0 && (
        <ol className="list-unstyled mb-0 mt-1" style={{ fontSize: '0.7rem' }}>
          {episodes.map((e, i) => (
            <li key={e.start} className="d-flex align-items-center gap-2 py-1"
                style={{ borderTop: i ? '1px solid #1C2F49' : 'none' }}>
              <div style={{ flex: 1, minWidth: 0, color: '#C8D6E8' }}>
                <div>{fmtTime(e.start)} → {fmtTime(e.end)} <span style={{ color: '#8FA3BD' }}>({fmtDuration(e.duration_minutes)})</span></div>
                <div style={{ color: '#8FA3BD' }}>
                  {e.type === 'step' ? 'Step (persists)' : 'Plateau (returns)'} · max {fmtM(e.max_deviation)}
                </div>
              </div>
              <Button size="sm" variant="outline-warning" className="py-0 px-2" style={{ fontSize: '0.68rem' }}
                      onClick={() => onApplyEpisode(e)} aria-label={`Correct episode starting ${fmtTime(e.start)}`}>
                Correct this
              </Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
};

export default DriftPanel;
