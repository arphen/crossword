import React, { useEffect, useState } from 'react';
import { acceptProfileSuggestion, generateProfileNarrative, loadProfileNarrative } from './profileNarrative';

export default function ProfileNarrativePanel({ profileId, open, refreshKey = 0, onAccepted }) {
  const [state, setState] = useState('idle');
  const [fieldNote, setFieldNote] = useState(null);
  const [error, setError] = useState('');
  const [accepted, setAccepted] = useState(new Set());

  useEffect(() => {
    if (!open || !profileId) return undefined;
    const controller = new AbortController();
    setState('loading');
    setError('');
    setAccepted(new Set());
    loadProfileNarrative(profileId, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) {
          setFieldNote(value);
          setState('ready');
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setFieldNote(null);
          setError(cause instanceof Error ? cause.message : 'The profile field note could not be read.');
          setState('error');
        }
      });
    return () => controller.abort();
  }, [open, profileId, refreshKey]);

  async function writeFieldNote() {
    setState('generating');
    setError('');
    setAccepted(new Set());
    try {
      const value = await generateProfileNarrative(profileId);
      setFieldNote(value);
      setState('ready');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The profile field note could not be written.');
      setState('error');
    }
  }

  async function keepSuggestion(index) {
    if (!fieldNote?.receipt?.narrativeId || !Number.isInteger(fieldNote.receipt.epistemeRevision)) return;
    setError('');
    try {
      await acceptProfileSuggestion(profileId, fieldNote.receipt.narrativeId, index, fieldNote.receipt.epistemeRevision);
      setAccepted((current) => new Set([...current, index]));
      onAccepted?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The field note path could not be kept.');
    }
  }

  if (!open) return null;
  if (state === 'loading') {
    return <section className="future-profile-narrative" aria-label="Profile field note" aria-busy="true">Opening a field note from the saved evidence…</section>;
  }
  const narrative = fieldNote?.narrative;
  const generation = fieldNote?.receipt?.generation;
  const model = generation?.returnedModel || generation?.requestedModel;
  return (
    <section className="future-profile-narrative" aria-label="Profile field note">
      <div className="future-profile-narrative-heading">
        <div>
          <p className="future-eyebrow">A field note, if you want one</p>
          <p className="future-small">Local model prose, regenerated from the saved record.</p>
        </div>
        {fieldNote?.receipt?.epistemeRevision !== undefined && (
          <span className="future-episteme-revision">revision {fieldNote.receipt.epistemeRevision}</span>
        )}
      </div>
      {generation && (
        <p className="future-small future-profile-narrative-receipt" role="status">
          {model ? `Written locally with ${model}` : 'Written locally'}
          {generation.promptVersion ? ` · ${generation.promptVersion}` : ''}
        </p>
      )}
      {narrative ? (
        <>
          <div className="future-profile-narrative-copy">
            {narrative.paragraphs.map((paragraph, index) => (
              <p key={`${paragraph.text}-${index}`}>{paragraph.text}</p>
            ))}
          </div>
          {narrative.openQuestions.length > 0 && (
            <div className="future-profile-narrative-questions">
              <span className="future-episteme-lane-label">Still open</span>
              {narrative.openQuestions.map((question, index) => (
                <span key={`${question.text}-${index}`}>{question.text}</span>
              ))}
            </div>
          )}
          {narrative.suggestions?.length > 0 && (
            <div className="future-profile-narrative-suggestions">
              <span className="future-episteme-lane-label">Possible paths</span>
              {narrative.suggestions.map((suggestion, index) => (
                <div className="future-profile-narrative-suggestion" key={`${suggestion.conceptId}-${index}`}>
                  <div>
                    <strong>{suggestion.label}</strong>
                    <span>{suggestion.rationale}</span>
                  </div>
                  <button
                    className="future-text-button"
                    disabled={accepted.has(index) || fieldNote.stale}
                    onClick={() => void keepSuggestion(index)}
                  >
                    {accepted.has(index) ? 'Kept' : suggestion.action === 'exclude' ? 'Set aside' : 'Keep this path'}
                  </button>
                </div>
              ))}
            </div>
          )}
          {fieldNote.stale && <p className="future-small">The evidence has changed since this note. Write a fresh one when the field calls for it.</p>}
        </>
      ) : (
        <p className="future-small">No prose portrait has been written. The underlying signals remain available above.</p>
      )}
      <button className="future-text-button" onClick={() => void writeFieldNote()} disabled={state === 'generating'}>
        {state === 'generating' ? 'Listening to the field…' : narrative ? 'Write a fresh field note' : 'Write a field note'}
        <span aria-hidden="true">✧</span>
      </button>
      {fieldNote?.status === 'unavailable' && <p className="future-small" role="status">The local model is unavailable; the saved episteme is unchanged.</p>}
      {error && <p className="future-small" role="alert">{error}</p>}
    </section>
  );
}
