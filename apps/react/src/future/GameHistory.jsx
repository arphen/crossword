import React, { useEffect, useState } from 'react';

function dayLabel(value) {
  if (typeof value !== 'string' || !value) return 'personal';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function dateLabel(value) {
  return typeof value === 'string' && value.length >= 10
    ? value.slice(0, 10)
    : 'undated';
}

export function gameHistoryStats(item) {
  const analysis = item?.analysis;
  if (!analysis || analysis.version !== 'private-session-analysis-summary-v1') {
    return item?.finished ? 'Replay saved · analysis pending' : 'In progress';
  }
  return `${analysis.independentCount || 0} independent · ${analysis.supportedCount || 0} supported · ${analysis.assistedCount || 0} assisted`;
}

export function personalizationHistorySummary(item) {
  const personalization = item?.personalization;
  if (
    personalization?.version !== 'private-history-personalization-v1' ||
    !Number.isInteger(personalization.epistemeRevision)
  ) {
    return '';
  }
  const lanes = [];
  if (personalization.claimCount > 0) lanes.push('signals');
  if (personalization.associationCount > 0) lanes.push('threads');
  if (personalization.recentExposureCount > 0) lanes.push('recent words');
  if (personalization.languageThread) lanes.push('language');
  const steering = personalization.associationSteering;
  if (Number.isInteger(steering?.eligibleCount) && steering.eligibleCount > 0) {
    lanes.push(`${steering.eligibleCount} active path${steering.eligibleCount === 1 ? '' : 's'}`);
  }
  const clueDiversity = personalization.clueDiversity;
  if (clueDiversity?.status === 'varied') lanes.push('varied clue surfaces');
  if (Number.isInteger(clueDiversity?.repairRewrittenCount) && clueDiversity.repairRewrittenCount > 0) {
    lanes.push(`${clueDiversity.repairRewrittenCount} surface repair${clueDiversity.repairRewrittenCount === 1 ? '' : 's'}`);
  }
  const laneText = lanes.length ? ` · ${lanes.join(' · ')}` : '';
  return `Episteme revision ${personalization.epistemeRevision}${laneText}`;
}

export function playtestHistorySummary(item) {
  const pulse = item?.playtest;
  if (
    !pulse ||
    pulse.schemaVersion !== 1 ||
    !['yes', 'maybe', 'no'].includes(pulse.worth) ||
    typeof pulse.returnIntent !== 'string' ||
    typeof pulse.roughEdge !== 'string'
  ) {
    return '';
  }
  const worth = { yes: 'worth another', maybe: 'uncertain', no: 'not this time' }[pulse.worth];
  const direction = {
    'another-like-this': 'another like this',
    'same-world-new-angle': 'a new angle',
    'more-footholds': 'more footholds',
    'harder-stretch': 'a harder stretch',
    'let-it-rest': 'a pause',
  }[pulse.returnIntent];
  if (!direction) return '';
  return `Playtest: ${worth} · next: ${direction}${pulse.roughEdge === 'none' ? '' : ` · edge: ${pulse.roughEdge.replaceAll('-', ' ')}`}`;
}

export function calibrationSummary(report) {
  if (
    !report ||
    report.version !== 'private-play-calibration-report-v1' ||
    !Number.isInteger(report.sessionCount) ||
    !report.totals
  )
    return '';
  if (report.sessionCount < (report.requiredSessions || 3)) {
    return `${report.sessionCount} finished game${report.sessionCount === 1 ? '' : 's'} recorded; more traces will make the difficulty signal steadier.`;
  }
  const completion = Math.round(Number(report.totals.completionRate || 0) * 100);
  const support = Math.round(Number(report.totals.supportRate || 0) * 100);
  return `Observed across ${report.sessionCount} finished games: ${completion}% completed · ${support}% used crossings or assistance.`;
}

export default function GameHistory({ profileId, open }) {
  const [state, setState] = useState('idle');
  const [history, setHistory] = useState([]);
  const [calibration, setCalibration] = useState(null);
  const [error, setError] = useState('');
  const [exportState, setExportState] = useState('idle');
  const [exportError, setExportError] = useState('');

  useEffect(() => {
    if (!open || !profileId) return undefined;
    const controller = new AbortController();
    setState('loading');
    setError('');
    setExportState('idle');
    setExportError('');
    fetch(`/api/future/profile/${encodeURIComponent(profileId)}/history?limit=12`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.error || 'The game history is unavailable.');
        return body;
      })
      .then((body) => {
        if (controller.signal.aborted) return;
        setHistory(Array.isArray(body.history) ? body.history : []);
        setCalibration(body.calibration || null);
        setState('ready');
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : 'The game history is unavailable.');
        setState('error');
      });
    return () => controller.abort();
  }, [open, profileId]);

  async function downloadCalibration() {
    if (!profileId || exportState === 'loading') return;
    setExportState('loading');
    setExportError('');
    try {
      const response = await fetch(
        `/api/future/profile/${encodeURIComponent(profileId)}/calibration-export?limit=50`,
        {
          headers: { Accept: 'application/json' },
          cache: 'no-store',
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || 'The calibration trace is unavailable.');
      const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `personal-calibration-${profileId}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setExportState('ready');
    } catch (reason) {
      setExportState('error');
      setExportError(reason instanceof Error ? reason.message : 'The calibration trace is unavailable.');
    }
  }

  if (!open) return null;
  if (state === 'loading' || state === 'idle') {
    return (
      <section className="future-game-history" aria-label="Game history" aria-busy="true">
        <p className="future-eyebrow">The path so far</p>
        <p className="future-small">Opening the saved games…</p>
      </section>
    );
  }
  if (state === 'error') {
    return (
      <section className="future-game-history" aria-label="Game history" role="status">
        <p className="future-eyebrow">The path so far</p>
        <p className="future-small">The saved games are resting.</p>
        {error && <small role="alert">{error}</small>}
      </section>
    );
  }

  return (
    <section className="future-game-history" aria-labelledby="future-game-history-title">
      <div className="future-game-history-heading">
        <div>
          <p className="future-eyebrow">The path so far</p>
          <h3 id="future-game-history-title">Games leave a trace.</h3>
        </div>
        <span className="future-episteme-revision">{history.length} saved</span>
      </div>
      {history.length === 0 ? (
        <p className="future-small">Your first personal game will appear here after it is saved.</p>
      ) : (
        <ol className="future-game-history-list">
          {history.map((item) => (
            <li key={item.sessionId} className="future-game-history-item">
              <div>
                <strong>{item.title || 'Personal crossword'}</strong>
                <small>
                  {dateLabel(item.createdAt)} · {dayLabel(item.weekday)}
                  {item.model ? ` · ${item.model}` : ''}
                </small>
                {personalizationHistorySummary(item) && (
                  <small>{personalizationHistorySummary(item)}</small>
                )}
                {playtestHistorySummary(item) && (
                  <small>{playtestHistorySummary(item)}</small>
                )}
              </div>
              <span>{gameHistoryStats(item)}</span>
            </li>
          ))}
        </ol>
      )}
      {calibrationSummary(calibration) && (
        <p className="future-small future-game-history-calibration" aria-label="Observed difficulty calibration">
          {calibrationSummary(calibration)} The signal adjusts footholds only; it is not a verdict about ability or mastery.
        </p>
      )}
      <div className="future-game-history-actions">
        <button
          type="button"
          className="future-secondary-button"
          onClick={() => void downloadCalibration()}
          disabled={exportState === 'loading'}
        >
          {exportState === 'loading' ? 'Preparing trace…' : 'Download calibration trace'}
        </button>
        <span className="future-small" role={exportError ? 'alert' : undefined}>
          {exportError || (exportState === 'ready' ? 'Saved locally.' : 'For local tuning; puzzle content stays out.')}
        </span>
      </div>
      <p className="future-small future-game-history-note">
        Answers stay in the private replay record; this view keeps only the route and its bounded analysis.
      </p>
    </section>
  );
}
