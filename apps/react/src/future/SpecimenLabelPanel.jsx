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

export default function SpecimenLabelPanel({ open }) {
  const [state, setState] = useState('idle');
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filter, setFilter] = useState('unlabeled');
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
    const verdictCounts = {};
    let unlabeled = 0;
    for (const record of records) {
      if (record.verdict) verdictCounts[record.verdict] = (verdictCounts[record.verdict] || 0) + 1;
      else unlabeled += 1;
    }
    return { verdictCounts, unlabeled, total: records.length };
  }, [records]);

  async function prepare() {
    setState('seeding');
    setError('');
    try {
      await seedSpecimens({});
      const value = await loadSpecimens({});
      setRecords(value.records);
      setState('ready');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The specimen ledger could not be prepared.');
      setState('error');
    }
  }

  async function judge(id, verdict) {
    setBusyId(id);
    setError('');
    try {
      const next = await recordVerdict(id, verdict);
      setRecords((current) => current.map((record) => (record.id === id ? { ...record, verdict } : record)));
      setSummary(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The verdict could not be recorded.');
    } finally {
      setBusyId(null);
    }
  }

  function toggleSelect(id) {
    setSelected((current) => {
      const next = new Set(current);
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
      setRecords((current) =>
        current.map((record) =>
          record.id === a || record.id === b ? { ...record, pairId: receipt.pairId } : record,
        ),
      );
      setSelected(new Set());
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

  const visible = records.filter((record) => {
    if (filter === 'unlabeled') return !record.verdict;
    if (filter === 'all') return true;
    return record.verdict === filter;
  });

  return (
    <section className="future-specimens" aria-label="Clue specimen labeling">
      <div>
        <p className="future-eyebrow">Judge the specimens</p>
        <p className="future-small">
          {counts.total === 0
            ? 'No ledger on this host yet. Prepare the surfaces, then judge each one.'
            : `${counts.total - counts.unlabeled} of ${counts.total} judged${counts.unlabeled > 0 ? ` · ${counts.unlabeled} to go` : ' · closed'}`}
        </p>
      </div>
      {state === 'loading' && <p className="future-small" aria-busy="true">Opening the ledger…</p>}
      {state === 'empty' && (
        <button className="future-text-button" onClick={() => void prepare()}>
          Prepare 62 judging surfaces
        </button>
      )}
      {state === 'ready' && counts.total > 0 && (
        <>
          <div className="future-specimens-filters" role="group" aria-label="Filter surfaces">
            {['unlabeled', 'all', ...SPECIMEN_VERDICTS].map((name) => (
              <button
                key={name}
                className="future-text-button"
                aria-pressed={filter === name}
                onClick={() => setFilter(name)}
              >
                {name}
              </button>
            ))}
          </div>
          <ul className="future-specimens-list">
            {visible.map((record) => (
              <li key={record.id} className="future-specimens-card">
                <div>
                  <strong>{record.answer}</strong>
                  <span>{record.clue}</span>
                  {record.note && <span className="future-small">{record.note}</span>}
                  {record.pairId && <span className="future-small">pair {record.pairId}</span>}
                </div>
                <div className="future-specimens-verdicts" role="group" aria-label={`Verdict for ${record.id}`}>
                  {SPECIMEN_VERDICTS.map((verdict) => (
                    <button
                      key={verdict}
                      className="future-text-button"
                      aria-pressed={record.verdict === verdict}
                      disabled={busyId === record.id}
                      onClick={() => void judge(record.id, verdict)}
                    >
                      {verdict}
                    </button>
                  ))}
                </div>
                <label className="future-small">
                  <input
                    type="checkbox"
                    checked={selected.has(record.id)}
                    onChange={() => toggleSelect(record.id)}
                  />{' '}
                  pair candidate
                </label>
              </li>
            ))}
          </ul>
          {visible.length === 0 && <p className="future-small">Nothing under this filter.</p>}
          <div>
            <button
              className="future-text-button"
              disabled={selected.size !== 2}
              onClick={() => void linkSelected()}
            >
              Link selected pair
            </button>
            {counts.unlabeled === 0 ? (
              <button className="future-text-button" onClick={() => void attest()}>
                Attest the closed ledger
              </button>
            ) : null}
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
