import React, { useEffect, useState } from 'react';

function integer(value) {
  return Number.isInteger(value) ? value : null;
}

function score(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(1)
    : '—';
}

function receiptStats(provenance) {
  const fill = provenance?.fillQuality || {};
  const clues = provenance?.clueQuality || {};
  const challenge = provenance?.semanticClueChallenge || {};
  const exposure = provenance?.themeExposure || {};
  const diversity = provenance?.clueDiversity || clues.diversity || {};
  const domainHints =
    provenance?.personalizationReceipt?.domainHints ||
    provenance?.themeProposal?.domainHints;
  const stats = [
    { label: 'fill mean', value: score(fill.meanScore) },
    { label: 'minimum fill', value: score(fill.minimumScore) },
    { label: 'weak entries', value: integer(fill.weakCount) ?? '—' },
    { label: 'clues checked', value: integer(clues.checkedCount) ?? '—' },
    { label: 'surface flags', value: integer(clues.issueCount) ?? '—' },
    {
      label: 'challenger pass',
      value: challenge.enabled === true ? 'bounded' : 'off',
    },
    {
      label: 'fresh themes',
      value: integer(exposure.freshThemeCount) ?? '—',
    },
    {
      label: 'surface mix',
      value:
        diversity.status === 'varied'
          ? `varied (${integer(diversity.nonDefinitionFamilies?.length) ?? 0})`
          : diversity.status === 'definition-heavy'
            ? 'definition-heavy'
            : '—',
    },
  ];
  if (String(provenance?.weekday).toLowerCase() === 'thursday') {
    const status = provenance?.mechanicEvaluation?.status;
    stats.push({
      label: 'theme mechanic',
      value:
        status === 'pass'
          ? 'checked'
          : status === 'fallback-safe'
            ? 'ordinary grid'
            : 'unavailable',
    });
  }
  if (domainHints?.status === 'loaded') {
    stats.push({
      label: 'domain hints',
      value: integer(domainHints.placeableCount) ?? 0,
    });
  }
  return stats;
}

export default function PrivatePuzzleReceipt({ sessionId, profileId }) {
  const [state, setState] = useState('idle');
  const [receipt, setReceipt] = useState(null);

  useEffect(() => {
    if (!sessionId || !profileId) return undefined;
    const controller = new AbortController();
    setState('loading');
    fetch(
      `/api/future/sessions/${encodeURIComponent(sessionId)}/private-provenance?profileId=${encodeURIComponent(profileId)}`,
      {
        signal: controller.signal,
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      },
    )
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.error || 'Receipt unavailable');
        return body;
      })
      .then((body) => {
        if (controller.signal.aborted) return;
        if (
          body.version !== 'private-puzzle-provenance-v1' ||
          !body.provenance
        ) {
          throw new Error('Receipt format unavailable');
        }
        setReceipt(body);
        setState('ready');
      })
      .catch(() => {
        if (!controller.signal.aborted) setState('unavailable');
      });
    return () => controller.abort();
  }, [sessionId, profileId]);

  if (!sessionId || !profileId || state === 'idle') return null;
  if (state === 'loading') {
    return (
      <section
        className="future-puzzle-receipt"
        aria-busy="true"
        aria-label="Puzzle receipt"
      >
        <p className="future-eyebrow">The board’s receipt</p>
        <p className="future-small">Reopening the local construction trace…</p>
      </section>
    );
  }
  if (state === 'unavailable') return null;

  const provenance = receipt.provenance;
  const weekday = provenance.weekday
    ? `${String(provenance.weekday).charAt(0).toUpperCase()}${String(provenance.weekday).slice(1)}`
    : 'Personal';
  return (
    <section
      className="future-puzzle-receipt"
      aria-labelledby="future-puzzle-receipt-title"
    >
      <div className="future-puzzle-receipt-heading">
        <div>
          <p className="future-eyebrow">The board’s receipt</p>
          <h2 id="future-puzzle-receipt-title">How this game was made.</h2>
        </div>
        <span>
          {weekday} · {provenance.model || 'local model'}
        </span>
      </div>
      <div className="future-puzzle-receipt-stats" role="list">
        {receiptStats(provenance).map((item) => (
          <span role="listitem" key={item.label}>
            <strong>{item.value}</strong>
            {item.label}
          </span>
        ))}
      </div>
      <p className="future-small">
        A bounded local diagnostic, kept with the private replay. It describes
        construction signals and clue surfaces; it does not grade the solver
        or establish that a clue’s meaning is true.
      </p>
    </section>
  );
}
