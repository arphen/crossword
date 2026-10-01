import React, { useEffect, useMemo, useState } from 'react';
import {
  SPECIMEN_VERDICTS,
  attestSpecimens,
  errorCode,
  linkPair,
  loadSpecimens,
  recordVerdict,
  seedSpecimens,
} from './specimens';

const VERDICT_GUIDE = {
  leak: {
    title: 'Leak',
    help: 'Clue gives the answer away — contains it or its form.',
    example: '“shadier character” → SHADY',
  },
  tautology: {
    title: 'Tautology',
    help: 'Clue just restates the answer.',
    example: '“more shady” → SHADIER',
  },
  'name-slot': {
    title: 'Name-slot',
    help: 'Generic famous-X with no wordplay.',
    example: '“Famous singer’s name” → ADELE',
  },
  'pseudo-pun': {
    title: 'Fake pun',
    help: 'Ends in ? but no real pivot or misdirection.',
    example: '“A quiet room?” → DEN',
  },
  acceptable: {
    title: 'Good clue',
    help: 'Fair definition, real pun, or honest fill-blank. When unsure, pick this.',
    example: '“Without light” → DARK',
  },
  'better-of-pair': {
    title: 'Pair winner',
    help: 'Only for linked same-answer pairs: the better of the two.',
    example: '“Full of light” beats “more bright”',
  },
};

export default function SpecimenLabelPanel({ open }) {
  const [state, setState] = useState('idle');
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState(null);
  const [view, setView] = useState('judge');
  const [currentId, setCurrentId] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [attestation, setAttestation] = useState(null);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    if (!open) return undefined;
    const controller = new AbortController();
    setState('loading');
    setError('');
    setAttestation(null);
    loadSpecimens({ signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        setRecords(value.records);
        const first = value.records.find((record) => !record.verdict);
        setCurrentId((first || value.records[0] || {}).id ?? null);
        setState('ready');
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        if (errorCode(cause) === 'missing-ledger') {
          setRecords([]);
          setState('empty');
        } else {
          setError(cause instanceof Error ? cause.message : 'The specimen ledger could not be read.');
          setState('error');
        }
      });
    return () => controller.abort();
  }, [open]);

  const counts = useMemo(() => {
    let unlabeled = 0;
    for (const record of records) if (!record.verdict) unlabeled += 1;
    return { unlabeled, total: records.length, judged: records.length - unlabeled };
  }, [records]);

  const queue = useMemo(() => records.filter((record) => !record.verdict), [records]);
  const current = useMemo(
    () => records.find((record) => record.id === currentId) || queue[0] || records[0] || null,
    [records, currentId, queue],
  );
  const currentIndex = current ? queue.findIndex((record) => record.id === current.id) : -1;

  const pairSuggestions = useMemo(() => {
    const groups = new Map();
    for (const record of records) {
      const key = String(record.answer || '').toUpperCase();
      if (!key) continue;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(record);
    }
    return [...groups.entries()].filter(([, members]) => members.length > 1).slice(0, 6);
  }, [records]);

  async function prepare() {
    setState('seeding');
    setError('');
    try {
      await seedSpecimens({});
      const value = await loadSpecimens({});
      setRecords(value.records);
      const first = value.records.find((record) => !record.verdict);
      setCurrentId((first || value.records[0] || {}).id ?? null);
      setView('judge');
      setState('ready');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The specimen ledger could not be prepared.');
      setState('error');
    }
  }

  function advanceAfter(updated, judgedId) {
    const rest = updated.filter((record) => !record.verdict && record.id !== judgedId);
    // Prefer the next item after the judged one; fall back to the first remaining.
    const judgedAt = updated.findIndex((record) => record.id === judgedId);
    const after = updated.slice(judgedAt + 1).find((record) => !record.verdict && record.id !== judgedId);
    setCurrentId((after || rest[0] || {}).id ?? null);
  }

  async function judge(id, verdict) {
    setBusyId(id);
    setError('');
    try {
      const next = await recordVerdict(id, verdict);
      let updated = records;
      setRecords((currentRecords) => {
        updated = currentRecords.map((record) => (record.id === id ? { ...record, verdict } : record));
        return updated;
      });
      setSummary(next);
      advanceAfter(updated, id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The verdict could not be recorded.');
    } finally {
      setBusyId(null);
    }
  }

  function stepQueue(direction) {
    if (queue.length === 0) return;
    const at = currentIndex < 0 ? 0 : (currentIndex + direction + queue.length) % queue.length;
    setCurrentId(queue[at].id);
  }

  function toggleSelect(id) {
    setSelected((currentSelected) => {
      const next = new Set(currentSelected);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function linkSelected() {
    const [a, b] = [...selected];
    if (!a || !b) return;
    setError('');
    try {
      const receipt = await linkPair(a, b);
      setRecords((currentRecords) =>
        currentRecords.map((record) =>
          record.id === a || record.id === b ? { ...record, pairId: receipt.pairId } : record,
        ),
      );
      setSelected(new Set());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The pair could not be linked.');
    }
  }

  async function linkGroup(members) {
    if (members.length !== 2) return;
    setError('');
    try {
      const receipt = await linkPair(members[0].id, members[1].id);
      setRecords((currentRecords) =>
        currentRecords.map((record) =>
          record.id === members[0].id || record.id === members[1].id
            ? { ...record, pairId: receipt.pairId }
            : record,
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The pair could not be linked.');
    }
  }

  async function attest() {
    setError('');
    try {
      const receipt = await attestSpecimens({});
      setAttestation(receipt);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The ledger is not closed yet.');
    }
  }

  if (!open) return null;
  const percent = counts.total === 0 ? 0 : Math.round((counts.judged / counts.total) * 100);

  return (
    <section className="future-specimens" aria-label="Clue specimen labeling">
      <div>
        <p className="future-eyebrow">Judge the clues — 3 steps</p>
        <p className="future-small">
          {counts.total === 0
            ? 'Step 0: build the 62 judging surfaces on this host, then work through them.'
            : `Step 1: judge · ${counts.judged} of ${counts.total} done${counts.unlabeled > 0 ? ` · ${counts.unlabeled} to go` : ' · all judged'}`}
        </p>
        {counts.total > 0 && (
          <div
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Judging progress"
            style={{ height: 8, borderRadius: 4, background: '#e5e0d5', overflow: 'hidden', margin: '8px 0' }}
          >
            <div style={{ width: `${percent}%`, height: '100%', background: '#2f6f4e' }} />
          </div>
        )}
      </div>

      {state === 'loading' && <p className="future-small" aria-busy="true">Opening the ledger…</p>}
      {state === 'empty' && (
        <div>
          <p className="future-small">No ledger on this host yet. This builds 62 short clue → answer cards locally.</p>
          <button className="future-text-button" onClick={() => void prepare()}>
            Prepare 62 judging surfaces
          </button>
        </div>
      )}

      {state === 'ready' && counts.total > 0 && (
        <>
          <ol className="future-small" style={{ paddingLeft: 18, margin: '8px 0' }}>
            <li><strong>Read one card</strong> and pick the verdict that fits best. Unsure? Choose “Good clue” and move on.</li>
            <li><strong>Skip pairs</strong> unless two clues share the same answer — only 1–2 cards need this.</li>
            <li><strong>Attest</strong> when the counter hits 0. That locks in your verdicts.</li>
          </ol>

          <div className="future-specimens-filters" role="group" aria-label="Judging view">
            <button
              className="future-text-button"
              aria-pressed={view === 'judge'}
              onClick={() => setView('judge')}
            >
              Judge one at a time
            </button>
            <button
              className="future-text-button"
              aria-pressed={view === 'review'}
              onClick={() => setView('review')}
            >
              Review all
            </button>
          </div>

          {view === 'judge' && current && (
            <article
              className="future-specimens-card"
              aria-label="Current judging card"
              style={{ border: '1px solid #d8d0c0', borderRadius: 8, padding: 12, marginTop: 8 }}
            >
              <p className="future-small">
                {current.verdict
                  ? `Judged as “${current.verdict}” — change it below if needed.`
                  : counts.unlabeled > 0
                    ? `Card ${counts.judged + 1} of ${counts.total} · needs your verdict`
                    : 'All judged — you can still revise.'}
              </p>
              <div style={{ margin: '8px 0' }}>
                <div style={{ fontSize: '1.15rem' }}>“{current.clue}”</div>
                <div style={{ marginTop: 4 }}>
                  answer: <strong style={{ letterSpacing: 1 }}>{current.answer}</strong>
                </div>
                {current.note && <div className="future-small">hint: {current.note}</div>}
                {current.pairId && <div className="future-small">linked pair: {current.pairId}</div>}
              </div>
              <div className="future-specimens-verdicts" role="group" aria-label={`Verdict for ${current.id}`}>
                {SPECIMEN_VERDICTS.map((verdict) => {
                  const guide = VERDICT_GUIDE[verdict] || { title: verdict, help: '', example: '' };
                  return (
                    <button
                      key={verdict}
                      className="future-text-button"
                      aria-pressed={current.verdict === verdict}
                      disabled={busyId === current.id}
                      onClick={() => void judge(current.id, verdict)}
                      title={`${guide.help} ${guide.example}`}
                      style={current.verdict === verdict ? { fontWeight: 700 } : undefined}
                    >
                      {guide.title}
                      <span className="future-small" style={{ display: 'block' }}>{guide.help}</span>
                    </button>
                  );
                })}
              </div>
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button className="future-text-button" onClick={() => stepQueue(-1)} disabled={queue.length < 2}>
                  ← Back
                </button>
                <button className="future-text-button" onClick={() => stepQueue(1)} disabled={queue.length < 2}>
                  Skip →
                </button>
              </div>
            </article>
          )}

          {view === 'review' && (
            <ul className="future-specimens-list" style={{ marginTop: 8 }}>
              {records.map((record) => (
                <li key={record.id} className="future-specimens-card" style={{ padding: '6px 0', borderTop: '1px solid #eee' }}>
                  <div>
                    <strong>{record.answer}</strong> <span>“{record.clue}”</span>{' '}
                    <span className="future-small">{record.verdict ? `→ ${record.verdict}` : '→ needs verdict'}</span>
                  </div>
                  {!record.verdict && (
                    <button className="future-text-button" onClick={() => { setCurrentId(record.id); setView('judge'); }}>
                      Judge this card
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          <details style={{ marginTop: 12 }}>
            <summary className="future-small">
              <strong>Step 2 (optional): compare a same-answer pair</strong> — skip this unless two clues share one answer.
            </summary>
            <p className="future-small">
              The “pair candidate” tickbox only marks two cards to compare. Nothing happens until you press a link
              button. Almost everything needs no pair at all.
            </p>
            {pairSuggestions.length === 0 ? (
              <p className="future-small">No repeated answers — nothing to link.</p>
            ) : (
              <ul className="future-small" style={{ paddingLeft: 18 }}>
                {pairSuggestions.map(([answer, members]) => (
                  <li key={answer} style={{ margin: '6px 0' }}>
                    <strong>{answer}</strong> ({members.length}): {members.map((member) => `“${member.clue}”`).join(' vs ')}
                    {members.length === 2 && !members[0].pairId && (
                      <button
                        className="future-text-button"
                        style={{ marginLeft: 8 }}
                        onClick={() => void linkGroup(members)}
                      >
                        Link these 2
                      </button>
                    )}
                    {members[0].pairId && <span> · linked ✓</span>}
                  </li>
                ))}
              </ul>
            )}
            <div className="future-small" style={{ marginTop: 8 }}>
              <p>Manual fallback: tick exactly 2 cards below, then link them.</p>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span>{selected.size} of 2 selected</span>
                <button
                  className="future-text-button"
                  disabled={selected.size !== 2}
                  onClick={() => void linkSelected()}
                >
                  Link selected pair
                </button>
                {selected.size !== 2 && <span>(tick 2 boxes in Review to enable)</span>}
              </div>
              {view !== 'review' && (
                <button className="future-text-button" onClick={() => setView('review')}>
                  Show tickboxes in Review
                </button>
              )}
              {view === 'review' && (
                <div style={{ marginTop: 4 }}>
                  {records.slice(0, 8).map((record) => (
                    <label key={record.id} className="future-small" style={{ display: 'block' }}>
                      <input
                        type="checkbox"
                        checked={selected.has(record.id)}
                        onChange={() => toggleSelect(record.id)}
                      />{' '}
                      {record.answer} — “{record.clue}”
                    </label>
                  ))}
                  <span className="future-small">First 8 shown; use Judge view for the rest.</span>
                </div>
              )}
            </div>
          </details>

          <div style={{ marginTop: 12 }}>
            {counts.unlabeled === 0 ? (
              <>
                <p className="future-small"><strong>Step 3: lock it in.</strong> All cards judged — attest to write the counts + digest.</p>
                <button className="future-text-button" onClick={() => void attest()}>
                  Attest the closed ledger
                </button>
              </>
            ) : (
              <p className="future-small">
                <strong>Step 3 unlocks at 0 to go</strong> ({counts.unlabeled} left). Attesting early is refused — that refusal is expected.
              </p>
            )}
          </div>
        </>
      )}

      {attestation && (
        <p className="future-small" role="status">
          Attested {attestation.pairs} pairs · {attestation.digest} · {attestation.out}
        </p>
      )}
      {summary && summary.problems?.length > 0 && (
        <p className="future-small" role="alert">{summary.problems.join('; ')}</p>
      )}
      {error && <p className="future-small" role="alert">{error}</p>}
    </section>
  );
}
