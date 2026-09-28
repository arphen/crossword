import React, { useState } from 'react';
import { submitPlaytestPulse } from './reflection';

const returnChoices = [
  ['another-like-this', 'Another one like this'],
  ['same-world-new-angle', 'Same world, new angle'],
  ['more-footholds', 'More footholds'],
  ['harder-stretch', 'A harder stretch'],
  ['let-it-rest', 'Let this one rest'],
];

const roughChoices = [
  ['none', 'Nothing rough'],
  ['too-opaque', 'A clue felt opaque'],
  ['too-obscure', 'An answer felt too obscure'],
  ['too-easy', 'It gave way too quickly'],
  ['crossings-unhelpful', 'The crossings did not help'],
];

function ChoiceRow({ label, choices, selected, onChange }) {
  return (
    <fieldset className="future-playtest-choice-group">
      <legend>{label}</legend>
      <div className="future-playtest-choice-row">
        {choices.map(([option, text]) => (
          <button
            type="button"
            key={option}
            className={selected === option ? 'is-selected' : ''}
            aria-pressed={selected === option}
            onClick={() => onChange(option)}
          >
            {text}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export default function PlaytestPulse({ sessionId, savedPulse }) {
  const [worth, setWorth] = useState(savedPulse?.worth || null);
  const [returnIntent, setReturnIntent] = useState(savedPulse?.returnIntent || null);
  const [roughEdge, setRoughEdge] = useState(savedPulse?.roughEdge || null);
  const [saved, setSaved] = useState(Boolean(savedPulse));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function save(nextWorth = worth) {
    if (!nextWorth || !returnIntent || !roughEdge || pending || saved) return;
    setError('');
    setPending(true);
    try {
      await submitPlaytestPulse({
        sessionId,
        worth: nextWorth,
        returnIntent,
        roughEdge,
      });
      setSaved(true);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'This playtest signal could not be saved.',
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="future-playtest-pulse" aria-labelledby="future-playtest-title">
      <div className="future-playtest-heading">
        <div>
          <p className="future-eyebrow">One last signal</p>
          <h2 id="future-playtest-title">Leave the next board a small instruction.</h2>
        </div>
        <p>
          This describes this game only. It changes the next experiment, not who
          you are.
        </p>
      </div>
      <ChoiceRow
        label="Would you take another turn in this world?"
        choices={[
          ['yes', 'Yes'],
          ['maybe', 'Maybe'],
          ['no', 'Not this time'],
        ]}
        selected={worth}
        onChange={(value) => {
          setWorth(value);
          void save(value);
        }}
      />
      <ChoiceRow
        label="Where should the next one lean?"
        choices={returnChoices}
        selected={returnIntent}
        onChange={setReturnIntent}
      />
      <ChoiceRow
        label="What should loosen its grip?"
        choices={roughChoices}
        selected={roughEdge}
        onChange={setRoughEdge}
      />
      {!saved && (
        <button
          type="button"
          className="future-playtest-submit"
          disabled={!worth || !returnIntent || !roughEdge || pending}
          onClick={() => void save()}
        >
          {pending ? 'Saving the signal…' : 'Save this signal'}
        </button>
      )}
      {saved && (
        <p className="future-playtest-saved" role="status">
          Saved for this game. The next local puzzle can listen without making a
          verdict.
        </p>
      )}
      {error && (
        <p className="future-playtest-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
