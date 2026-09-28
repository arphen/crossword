import React, { useEffect, useState } from 'react';
import { loadEpistemeSnapshot } from './epistemeSnapshot';
import { recordEpistemePreference } from './episteme';

function claimLabel(claim) {
  const concept = claim?.concept?.label || claim?.concept?.conceptId;
  if (typeof concept !== 'string' || !concept.trim()) return null;
  const stance = claim.stance === 'avoid' ? 'set aside' : claim.stance === 'seek' ? 'drawn toward' : 'in tension with';
  return `${concept} · ${stance}`;
}

function claimTensionLabel(claim) {
  if (claim?.stance === 'ambivalent') return 'conflicting controls';
  if (claim?.adequacy !== 'contradictory') return '';
  const support = Array.isArray(claim.evidenceIds) ? claim.evidenceIds.length : 0;
  const counter = Array.isArray(claim.counterEvidenceIds) ? claim.counterEvidenceIds.length : 0;
  return `${support} toward · ${counter} counter-signal${counter === 1 ? '' : 's'}`;
}

function associationLabel(association) {
  const phrase = association?.phrase;
  if (typeof phrase !== 'string' || !phrase.trim()) return null;
  const response = association.response === 'kept'
    ? 'kept'
    : association.response === 'rejected'
      ? 'set aside'
      : association.response === 'passed'
        ? 'passed'
        : 'unanswered';
  return `${phrase} · ${response}`;
}

export default function EpistemeSnapshot({ profileId, open, refreshKey = 0, onChanged }) {
  const [state, setState] = useState('idle');
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState('');
  const [busyClaim, setBusyClaim] = useState(null);
  const [noteClaim, setNoteClaim] = useState(null);
  const [correctionNote, setCorrectionNote] = useState('');

  useEffect(() => {
    if (!open || !profileId) return undefined;
    const controller = new AbortController();
    setState('loading');
    setError('');
    loadEpistemeSnapshot(profileId, { signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        setSnapshot(value);
        setState('ready');
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setSnapshot(null);
        setError(cause instanceof Error ? cause.message : 'The local episteme could not be read.');
        setState('error');
      });
    return () => controller.abort();
  }, [open, profileId, refreshKey]);

  async function correctClaim(claim, action) {
    const claimId = claim?.claimId || claim?.concept?.conceptId;
    const note = noteClaim === claimId ? correctionNote : '';
    setBusyClaim(claimId);
    setError('');
    try {
      await recordEpistemePreference(profileId, claim, action, { userText: note });
      setNoteClaim(null);
      setCorrectionNote('');
      onChanged?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The local episteme could not be updated.');
    } finally {
      setBusyClaim(null);
    }
  }

  if (!open) return null;
  if (state === 'loading' || state === 'idle') {
    return <section className="future-episteme-snapshot" aria-label="Living episteme" aria-busy="true">Opening the living episteme…</section>;
  }
  if (state === 'error') {
    return (
      <section className="future-episteme-snapshot" aria-label="Living episteme" role="status">
        <span>The living episteme is resting.</span>
        {error && <small>{error}</small>}
      </section>
    );
  }

  const claims = snapshot.claims.filter((claim) => claimLabel(claim)).slice(0, 8);
  const tensionClaims = claims.filter((claim) => claimTensionLabel(claim));
  const signalClaims = claims.filter((claim) => !claimTensionLabel(claim));
  const associations = snapshot.associations.map(associationLabel).filter(Boolean).slice(0, 8);
  const knowledge = snapshot.knowledge.length;
  const renderClaim = (claim, index) => {
    const label = claimLabel(claim);
    const claimId = claim.claimId || claim.concept?.conceptId || index;
    const tension = claimTensionLabel(claim);
    const noteIsOpen = noteClaim === claimId;
    return (
      <span className="future-episteme-claim" key={`${claimId}-${index}`}>
        <span>
          {label}
          {tension && <small className="future-episteme-claim-tension">{tension}</small>}
          {tension && (
            <details className="future-episteme-claim-evidence">
              <summary>Why this is in tension</summary>
              <small>
                {Array.isArray(claim.evidenceIds) ? claim.evidenceIds.length : 0} supporting signal{claim.evidenceIds?.length === 1 ? '' : 's'} ·{' '}
                {Array.isArray(claim.counterEvidenceIds) ? claim.counterEvidenceIds.length : 0} counter-signal{claim.counterEvidenceIds?.length === 1 ? '' : 's'}.
                {' '}Keep or set aside adds an explicit correction; it does not erase this history.
              </small>
            </details>
          )}
        </span>
        <span className="future-episteme-claim-actions">
          <button type="button" disabled={busyClaim === claimId} onClick={() => void correctClaim(claim, 'seek')}>Keep</button>
          <button type="button" disabled={busyClaim === claimId} onClick={() => void correctClaim(claim, 'exclude')}>Set aside</button>
          {claim.lockedByUser === true && (
            <button
              type="button"
              className="future-episteme-claim-release"
              disabled={busyClaim === claimId}
              onClick={() => void correctClaim(claim, 'clear')}
            >
              Release lock
            </button>
          )}
        </span>
        {tension && (
          <details
            className="future-episteme-claim-correction"
            open={noteIsOpen}
            onToggle={(event) => {
              if (event.currentTarget.open) {
                if (noteClaim !== claimId) setCorrectionNote('');
                setNoteClaim(claimId);
              } else if (noteClaim === claimId) {
                setNoteClaim(null);
                setCorrectionNote('');
              }
            }}
          >
            <summary>Add a correction note</summary>
            <textarea
              value={noteIsOpen ? correctionNote : ''}
              maxLength={2000}
              rows={2}
              placeholder="Optional context for this correction"
              aria-label={`Correction note for ${claim.concept?.label || 'this tension'}`}
              onChange={(event) => setCorrectionNote(event.target.value)}
            />
            <div className="future-episteme-claim-correction-actions">
              <button type="button" disabled={busyClaim === claimId} onClick={() => void correctClaim(claim, 'seek')}>Keep with note</button>
              <button type="button" disabled={busyClaim === claimId} onClick={() => void correctClaim(claim, 'exclude')}>Set aside with note</button>
            </div>
          </details>
        )}
      </span>
    );
  };
  return (
    <section className="future-episteme-snapshot" aria-label="Living episteme">
      <div className="future-episteme-heading">
        <div>
          <p className="future-eyebrow">The living episteme</p>
          <p className="future-small">A revisable record of what the games have opened.</p>
        </div>
        <span className="future-episteme-revision">revision {snapshot.revision}</span>
      </div>
      {signalClaims.length > 0 && (
        <div className="future-episteme-lane">
          <span className="future-episteme-lane-label">Signals</span>
          <div className="future-episteme-tags">
            {signalClaims.map(renderClaim)}
          </div>
        </div>
      )}
      {tensionClaims.length > 0 && (
        <div className="future-episteme-lane future-episteme-tension-lane">
          <span className="future-episteme-lane-label">Tensions</span>
          <div className="future-episteme-tags">
            {tensionClaims.map(renderClaim)}
          </div>
        </div>
      )}
      {associations.length > 0 && (
        <div className="future-episteme-lane">
          <span className="future-episteme-lane-label">Open threads</span>
          <div className="future-episteme-tags">
            {associations.map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}
          </div>
        </div>
      )}
      <p className="future-episteme-footnote">
        {knowledge > 0 ? `${knowledge} learning thread${knowledge === 1 ? '' : 's'} are being tracked.` : 'Learning threads will appear as you play.'}
        {' '}Nothing here is a verdict; every signal can change.
      </p>
      {error && <small role="alert">{error}</small>}
    </section>
  );
}

export { associationLabel, claimLabel, claimTensionLabel };
