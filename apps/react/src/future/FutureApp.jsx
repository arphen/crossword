import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  orderedCalibrationEvents,
  validateCalibrationSession,
} from '@crossword/domain';
import {
  catalog,
  freshDraft,
  loadSavedProfile,
  LOCAL_MODEL_CHOICES,
  readDraft,
  recordAssociationPreference,
  saveProfile,
  seedProfile,
  STORAGE_KEY,
  validateDraft,
  writeDraft,
} from './episteme';
import Signifier from './Signifier';
import StimulusArtwork from './StimulusArtwork';
import FutureSolver from './FutureSolver';
import LearningReview from './LearningReview';
import EpistemeSnapshot from './EpistemeSnapshotView';
import ProfileNarrativePanel from './ProfileNarrativePanel';
import GameHistory from './GameHistory';
import CalibrationHypotheses from './CalibrationHypotheses';
import {
  createCalibrationHypotheses,
  loadCalibrationHypotheses,
  respondToCalibrationHypothesis,
  reviseCalibrationHypothesisResponse,
} from './calibrationHypothesesApi';
import {
  CalibrationJournalStorageError,
  createCalibrationJournalStore,
} from './calibrationJournal';
import { createFutureJournalStore } from './journalStore';
import {
  PRIVATE_PUZZLE_HISTORY_SUFFIX,
  PRIVATE_PUZZLE_STORAGE_PREFIX,
} from './privatePuzzleStore';
import {
  CALIBRATION_SELECTOR_VERSION_V2,
  createCalibrationPresentation,
  deriveCalibrationSeed,
} from './calibrationPresentation';
import {
  appendCalibrationObservation,
  completeCalibration,
  createInitialCalibrationSession,
  skipCalibration,
  updateCalibrationCursor,
} from './calibrationRuntime';
import {
  createCalibrationRecoveryDraft,
  describeCalibrationConflict,
} from './calibrationRecovery';
import './future.css';

const chapters = [
  'Encounter',
  'Relation',
  'Variation',
  'Traces',
  'Setup',
  'Preview',
];
const titles = [
  'Before the words,',
  'What belongs beside it?',
  'One small change.',
  'A little residue.',
  'Choose your rhythm.',
  'A beginning,',
];
const titleEnds = [
  'a little wonder.',
  '',
  '',
  '',
  '',
  'not a definition.',
];
const descriptions = [
  'No meanings to decode yet. Let one object, mark, or shape find you.',
  'Place another signifier beside it. The connection can stay unexplained.',
  'Keep its shape, or let one color shift the scene.',
  'Keep up to two: a word, a mark, a number, or something between.',
  'Choose a weekday difficulty and, if you like, a language to carry along.',
  'A few possible paths through words. Nothing here has to stay.',
];

/** @typedef {{id: string, version: number, kind: string, accessible_label: string, legacy_ids?: string[], swatch_hex?: string, association_seeds: string[]}} Stimulus */
/** @type {Stimulus[]} */
const stimuli = catalog.stimuli.items;
const stimulusById = (id) => stimuli.find((item) => item.id === id) ?? null;
const stimulusByLegacyId = (id) =>
  stimuli.find((item) => item.legacy_ids?.includes(id)) ?? null;
/** @type {Stimulus[]} */
const objectStimuli = catalog.objects
  .map((item) => stimulusByLegacyId(item.id))
  .filter(Boolean);
const encounterStimuli = [
  ...objectStimuli,
  ...stimuli.filter((item) => item.kind === 'abstract_form').slice(0, 2),
  ...stimuli.filter((item) => item.kind === 'texture_material').slice(0, 2),
  ...stimuli.filter((item) => item.kind === 'numeral').slice(-1),
  ...stimuli.filter((item) => item.id === 'mark-therefore'),
].slice(0, 12);
const languageTags = {
  'None for now': 'en',
  Dutch: 'nl',
  French: 'fr',
  German: 'de',
  Spanish: 'es',
  Italian: 'it',
  Portuguese: 'pt',
  Japanese: 'ja',
};
const localModelLabels = {
  automatic: 'Automatic · installed preference',
  'gemma4:26b': 'Gemma 4 26B',
  'qwen3.8:27b': 'Qwen 3.8 27B',
  'gemma4:31b': 'Gemma 4 31B',
  'gemma3:27b': 'Gemma 3 27B',
};

function hasActiveHypothesisSource(session) {
  const events = orderedCalibrationEvents(session);
  if (!events) return false;
  const observations = new Map();
  const activeChoices = new Set();
  for (const event of events) {
    if (event.kind === 'observation') {
      observations.set(event.value.observationId, event.value);
      if (
        event.value.movement <= 4 &&
        event.value.response.kind === 'choose'
      ) {
        activeChoices.add(event.value.observationId);
      }
    } else if (event.value.action === 'retract') {
      activeChoices.delete(event.value.targetObservationId);
    } else {
      const restored = observations.get(event.value.targetObservationId);
      if (
        restored?.movement <= 4 &&
        restored.response.kind === 'choose'
      ) {
        activeChoices.add(event.value.targetObservationId);
      }
    }
  }
  return activeChoices.size > 0;
}

function stimulusCaption(item) {
  const legacy = item.legacy_ids?.[0];
  const familiarItem = [...catalog.objects, ...catalog.companions].find(
    (candidate) => candidate.id === legacy,
  );
  if (familiarItem) return familiarItem.label.replace(/^(A|An|The) /, '');
  if (item.kind === 'word') return item.id.replace(/^word-/, '');
  if (item.kind === 'numeral')
    return item.id === 'numeral-clock-time'
      ? '03:17'
      : item.id.replace(/^numeral-/, '');
  if (item.kind === 'color') return item.id.replace(/^color-/, '');
  if (item.kind === 'abstract_form') return item.id.replace(/^form-/, '').replaceAll('-', ' ');
  if (item.kind === 'texture_material')
    return item.id.replace(/^surface-/, '').replaceAll('-', ' ');
  if (item.kind === 'typographic_mark')
    return item.id.replace(/^mark-/, '').replaceAll('-', ' ');
  return item.accessible_label;
}

/** @param {Stimulus[]} items @param {number} seed @param {number} movement @param {'selector-v1' | 'selector-v2'} selectorVersion */
function presentationFor(items, seed, movement, selectorVersion) {
  const movementSeed = (seed + Math.imul(movement, 0x9e3779b9)) >>> 0;
  return createCalibrationPresentation(items, movementSeed, selectorVersion);
}

function draftFromCalibration(session, baseDraft) {
  const events = orderedCalibrationEvents(session) ?? [];
  const activeIds = new Set();
  const latestByMovement = new Map();
  for (const event of events) {
    if (event.kind === 'observation') {
      latestByMovement.set(event.value.movement, event.value);
      if (event.value.response.kind === 'choose')
        activeIds.add(event.value.observationId);
    } else if (event.value.action === 'retract') {
      activeIds.delete(event.value.targetObservationId);
    } else {
      activeIds.add(event.value.targetObservationId);
    }
  }
  const selectedAt = (movement) => {
    const observation = latestByMovement.get(movement);
    if (
      !observation ||
      observation.response.kind !== 'choose' ||
      !activeIds.has(observation.observationId)
    )
      return [];
    return observation.response.chosenIds
      .map(stimulusById)
      .filter(Boolean);
  };
  const primary = selectedAt(1)[0];
  const companion = selectedAt(2)[0];
  const variationObservation = latestByMovement.get(3);
  const variation = selectedAt(3)[0];
  const traces = selectedAt(4)
    .map((item) => item.legacy_ids?.find((id) => catalog.traces.includes(id)))
    .filter(Boolean);
  const objectId = primary?.legacy_ids?.find((id) =>
    catalog.objects.some((item) => item.id === id),
  );
  const companionId = companion?.legacy_ids?.find((id) =>
    catalog.companions.some((item) => item.id === id),
  );
  const language = session.setup?.language;
  const learningLanguage = Object.entries(languageTags).find(
    ([, tag]) => tag === language,
  )?.[0];
  const weekday = session.setup?.weekday;
  const weekdayId = catalog.days.find(
    (day) => day.label.toLowerCase() === weekday?.toLowerCase(),
  )?.id;
  return {
    ...baseDraft,
    calibrationId: session.calibrationId,
    presentationMode: session.presentationMode,
    firstStimulus: primary?.id ?? null,
    object: objectId ?? null,
    companion: companionId ?? null,
    variation:
      variationObservation?.relation?.kind === 'keep-original'
        ? 'keep-original'
        : variation?.id ?? null,
    traces,
    weekday: weekdayId ?? baseDraft.weekday,
    learningLanguage: learningLanguage ?? baseDraft.learningLanguage,
    reflection: null,
    step:
      session.status === 'in-progress'
        ? Math.max(0, session.currentMovement - 1)
        : 5,
    complete: session.status !== 'in-progress',
  };
}

/** @param {unknown} value */
function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value && typeof value === 'object')
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(',')}}`;
  return JSON.stringify(value);
}

/** @param {unknown} remote @param {unknown} local */
function isAppendOnlyCalibrationExtension(remote, local) {
  if (!validateCalibrationSession(remote) || !validateCalibrationSession(local))
    return false;
  const immutable = [
    'schemaVersion',
    'calibrationId',
    'scope',
    'bankVersion',
    'selectorVersion',
    'seed',
    'presentationMode',
    'createdAt',
  ];
  if (
    immutable.some((key) => stableJson(remote[key]) !== stableJson(local[key]))
  )
    return false;
  for (const key of ['observations', 'actions']) {
    if (
      remote[key].length > local[key].length ||
      remote[key].some(
        (event, index) => stableJson(event) !== stableJson(local[key][index]),
      )
    )
      return false;
  }
  if (
    remote.status !== 'in-progress' &&
    stableJson(remote) !== stableJson(local)
  )
    return false;
  return Date.parse(local.updatedAt) >= Date.parse(remote.updatedAt);
}

function Arrow({ back = false }) {
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d={back ? 'M19 12H5m6-6-6 6 6 6' : 'M5 12h14m-6-6 6 6-6 6'} />
    </svg>
  );
}
function Mark() {
  return (
    <span className="future-mark" aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </span>
  );
}

function ObjectChoice({ item, stimulus = null, index, selected, onChoose, mode }) {
  const label = stimulus?.accessible_label ?? item.label;
  return (
    <button
      className={`future-object ${selected ? 'is-chosen' : ''}`}
      onClick={() => onChoose(item.id)}
      aria-pressed={selected}
      aria-label={label}
    >
      <span className="future-object-index">
        {String(index + 1).padStart(2, '0')}
      </span>
      {stimulus ? (
        <StimulusArtwork item={stimulus} presentationMode={mode} />
      ) : (
        <Signifier kind={item.id} />
      )}
      <span className="future-object-label">
        {stimulus ? stimulusCaption(stimulus) : item.label}
      </span>
      <span className="future-object-check" aria-hidden="true">
        {selected ? '✓' : '+'}
      </span>
    </button>
  );
}

function ProfileField({ draft, update, editable = true, showSettings = false }) {
  const profile = seedProfile(draft);
  const allWords = seedProfile({ ...draft, excluded: [] }).associations;
  const firstStimulus =
    stimulusById(draft.firstStimulus) ?? stimulusByLegacyId(draft.object);
  const companionStimulus = stimulusByLegacyId(draft.companion);
  const variation =
    draft.variation === 'keep-original'
      ? null
      : draft.variation
        ? stimulusById(draft.variation)
        : null;
  return (
    <div className="future-field">
      <div className="future-field-objects" aria-hidden="true">
        {firstStimulus ? (
          <StimulusArtwork
            item={firstStimulus}
            presentationMode={draft.presentationMode}
          />
        ) : (
          <Mark />
        )}
        {companionStimulus && (
          <>
            <span>+</span>
            <StimulusArtwork
              item={companionStimulus}
              presentationMode={draft.presentationMode}
            />
          </>
        )}
        {variation && (
          <span
            className="future-swatch future-profile-swatch"
            style={{ backgroundColor: variation.swatch_hex }}
            aria-hidden="true"
          />
        )}
      </div>
      <p className="future-field-prose">{profile.prose}</p>
      <p className="future-eyebrow">Your first constellation</p>
      <div className="future-associations">
        {allWords.length ? (
          allWords.map((word) => (
            <button
              key={word}
              disabled={!editable}
              aria-pressed={!draft.excluded.includes(word)}
              className={draft.excluded.includes(word) ? 'is-muted' : ''}
              onClick={() =>
                update({
                  excluded: draft.excluded.includes(word)
                    ? draft.excluded.filter((item) => item !== word)
                    : [...draft.excluded, word],
                })
              }
            >
              {word}
              <span aria-hidden="true">
                {draft.excluded.includes(word) ? '+' : '×'}
              </span>
            </button>
          ))
        ) : (
          <p className="future-small">
            An open field. Your first associations can arrive later.
          </p>
        )}
      </div>
      {allWords.length > 0 && editable && (
        <p className="future-small">
          Tap any word to leave it behind. Tap again to bring it back.
        </p>
      )}
      <div className="future-profile-facts">
        <span>
          <b>{catalog.days.find((day) => day.id === draft.weekday).label}</b>{' '}
          difficulty
        </span>
        <span>Puzzle language · English</span>
        {draft.learningLanguage !== 'None for now' && (
          <span>{draft.learningLanguage} learning interest</span>
        )}
        <span>
          Writing model · {localModelLabels[draft.modelPreference || 'automatic']}
        </span>
      </div>
      {showSettings && editable && (
        <div className="future-profile-settings" aria-label="Personal crossword settings">
          <label>
            <span>Next crossword difficulty</span>
            <select
              aria-label="Next crossword difficulty"
              value={draft.weekday}
              onChange={(event) => update({ weekday: event.target.value })}
            >
              {catalog.days.map((day) => (
                <option key={day.id} value={day.id}>{day.label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Learning thread</span>
            <select
              aria-label="Learning thread"
              value={draft.learningLanguage}
              onChange={(event) => update({ learningLanguage: event.target.value })}
            >
              {catalog.languages.map((language) => (
                <option key={language}>{language}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Local writing model</span>
            <select
              aria-label="Saved local writing model"
              value={draft.modelPreference || 'automatic'}
              onChange={(event) => update({ modelPreference: event.target.value })}
            >
              {LOCAL_MODEL_CHOICES.map((choice) => (
                <option key={choice} value={choice}>
                  {localModelLabels[choice] || choice}
                </option>
              ))}
            </select>
          </label>
          <p className="future-small">
            These settings steer the next personal crossword; the open board in front of you stays unchanged.
          </p>
        </div>
      )}
    </div>
  );
}

export default function FutureApp() {
  const [draft, setDraft] = useState(readDraft);
  const [playing, setPlaying] = useState(() => draft.complete);
  const [hostProfileReady, setHostProfileReady] = useState(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [storageOkay, setStorageOkay] = useState(true);
  const [saveState, setSaveState] = useState('idle');
  const [profileLoadError, setProfileLoadError] = useState('');
  const [lifecycleState, setLifecycleState] = useState('idle');
  const [lifecycleError, setLifecycleError] = useState('');
  const [retentionState, setRetentionState] = useState('idle');
  const [retentionSummary, setRetentionSummary] = useState('');
  const [preferenceState, setPreferenceState] = useState('idle');
  const [epistemeRefresh, setEpistemeRefresh] = useState(0);
  const [hypothesisDeck, setHypothesisDeck] = useState(null);
  const [hypothesisResponses, setHypothesisResponses] = useState({});
  const [hypothesisState, setHypothesisState] = useState('idle');
  const [hypothesisError, setHypothesisError] = useState('');
  const [busyHypothesisId, setBusyHypothesisId] = useState(null);
  const [calibrationReady, setCalibrationReady] = useState(false);
  const [calibrationBusy, setCalibrationBusy] = useState(false);
  const [calibrationStatus, setCalibrationStatus] = useState('loading');
  const [calibrationError, setCalibrationError] = useState('');
  const [calibrationConflictAcknowledged, setCalibrationConflictAcknowledged] =
    useState(false);
  const heading = useRef(null);
  const dialog = useRef(null);
  const importInput = useRef(null);
  const request = useRef(null);
  const draftRef = useRef(draft);
  const hostProfileReadyRef = useRef(hostProfileReady);
  const profileConflictRef = useRef(false);
  const profileRetrying = useRef(false);
  const hypothesisRequest = useRef(null);
  const preferenceQueue = useRef(Promise.resolve());
  const saveRevision = useRef(0);
  const journalStore = useRef(null);
  const journalRecordRef = useRef(null);
  const journalSessionRef = useRef(null);
  const journalWriteQueue = useRef(Promise.resolve());
  const journalSyncQueue = useRef(Promise.resolve());
  const presentedAt = useRef(new Date().toISOString());
  const step = draft.step;
  draftRef.current = draft;
  hostProfileReadyRef.current = hostProfileReady;
  const selectedObject = catalog.objects.find(
    (item) => item.id === draft.object,
  );
  const hypothesisSourceAvailable = useMemo(
    () => hasActiveHypothesisSource(journalSessionRef.current),
    [calibrationReady, draft.calibrationId, step],
  );
const selectedDay = catalog.days.find((day) => day.id === draft.weekday);
  const activeJournalSession =
    journalSessionRef.current?.calibrationId === draft.calibrationId
      ? journalSessionRef.current
      : null;
  const selectorSeed =
    activeJournalSession?.seed ?? deriveCalibrationSeed(draft.calibrationId);
  const selectorVersion =
    activeJournalSession?.selectorVersion ?? CALIBRATION_SELECTOR_VERSION_V2;
  const presentation = useMemo(() => {
    let items = [];
    if (step === 0) items = encounterStimuli;
    if (step === 1) {
      const companionIds = selectedObject?.companions ?? catalog.companions.map((item) => item.id);
      items = companionIds.map(stimulusByLegacyId).filter(Boolean);
    }
    if (step === 2) {
      const original = stimulusById(draft.firstStimulus);
      items = [
        ...(original ? [original] : []),
        ...stimuli.filter((item) => item.kind === 'color'),
      ];
    }
    if (step === 3) {
      items = catalog.traces.map(stimulusByLegacyId).filter(Boolean);
    }
    return items.length
      ? presentationFor(items, selectorSeed, step + 1, selectorVersion)
      : null;
  }, [
    calibrationReady,
    draft.firstStimulus,
    selectedObject,
    selectorSeed,
    selectorVersion,
    step,
  ]);

  useEffect(() => {
    let active = true;
    setCalibrationReady(false);
    setCalibrationStatus('loading');
    setCalibrationError('');
    journalRecordRef.current = null;
    journalSessionRef.current = null;
    setCalibrationConflictAcknowledged(false);
    try {
      journalStore.current ??= createCalibrationJournalStore();
    } catch {
      journalStore.current = null;
    }
    const load = async () => {
      try {
        let saved = await journalStore.current?.load(draft.calibrationId);
        if (!saved && journalStore.current && navigator.onLine) {
          const response = await fetch(
            `/api/future/calibrations/${encodeURIComponent(draft.calibrationId)}`,
            { headers: { Accept: 'application/json' } },
          );
          if (response.ok) {
            const payload = await response.json();
            if (
              !payload?.calibration ||
              payload.calibration.scope?.kind !== 'profile' ||
              payload.calibration.scope.profileId !== draft.id
            ) {
              throw new Error('The saved calibration belongs to a different profile.');
            }
            const etag = response.headers?.get?.('ETag');
            const restored = await journalStore.current.restoreHost(
              payload.calibration,
              { etag, revision: payload.revision },
            );
            if (!active) return;
            saved = restored;
            const localDraft = draftFromCalibration(restored.session, draft);
            draftRef.current = localDraft;
            setDraft(localDraft);
          } else if (response.status !== 404) {
            throw new Error('The saved calibration could not be loaded.');
          }
        }
        if (!active) return;
        if (saved) {
          journalRecordRef.current = saved;
          journalSessionRef.current = saved.session;
          setCalibrationStatus(
            saved.syncStatus === 'saved'
              ? 'synced'
              : saved.syncStatus === 'conflict'
                ? 'conflict'
                : 'pending',
          );
          if (saved.syncStatus === 'pending') void scheduleJournalSync();
        } else {
          journalSessionRef.current = createInitialCalibrationSession({ draft });
          setCalibrationStatus('ready');
        }
      } catch {
        if (!active) return;
        journalSessionRef.current = createInitialCalibrationSession({ draft });
        setCalibrationStatus('local-error');
      } finally {
        if (active) setCalibrationReady(true);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [draft.calibrationId]);
  const update = (patch) => {
    const changesDraft = Object.entries(patch).some(
      ([key, value]) => draft[key] !== value,
    );
    if (playing && Array.isArray(patch.excluded)) {
      const before = new Set(draft.excluded);
      const after = new Set(patch.excluded);
      const changedWords = [...new Set([...before, ...after])].filter(
        (word) => before.has(word) !== after.has(word),
      );
      for (const word of changedWords) {
        const action = after.has(word) ? 'exclude' : 'seek';
        preferenceQueue.current = preferenceQueue.current
          .then(async () => {
            setPreferenceState('saving');
            await recordAssociationPreference(draft.id, word, action);
            setPreferenceState('saved');
          })
          .catch(() => setPreferenceState('offline'));
      }
    }
    if (
      typeof patch.presentationMode === 'string' &&
      !journalRecordRef.current?.session.observations.length &&
      !journalRecordRef.current?.session.actions.length &&
      journalSessionRef.current?.calibrationId === draft.calibrationId
    ) {
      journalSessionRef.current = {
        ...journalSessionRef.current,
        presentationMode: patch.presentationMode,
      };
    }
    setDraft((value) => ({ ...value, ...patch }));
    if (playing && changesDraft) {
      request.current?.abort();
      saveRevision.current++;
      setSaveState('idle');
    }
  };

  /** @returns {import('@crossword/domain').CalibrationSetupV1} */
  function setupFor(value = draftRef.current) {
    return /** @type {import('@crossword/domain').CalibrationSetupV1} */ ({
      weekday: catalog.days.find((day) => day.id === value.weekday).label,
      language: languageTags[value.learningLanguage] ?? 'en',
    });
  }
  function currentSession() {
    if (
      journalSessionRef.current?.calibrationId ===
      draftRef.current.calibrationId
    )
      return journalSessionRef.current;
    const created = createInitialCalibrationSession({ draft: draftRef.current });
    journalSessionRef.current = created;
    return created;
  }
  async function syncJournal() {
    const store = journalStore.current;
    if (!store || !navigator.onLine) {
      if (journalRecordRef.current?.syncStatus !== 'saved')
        setCalibrationStatus('pending');
      return;
    }
    try {
      let rebasedAfterConflict = false;
      for (let attempt = 0; attempt < 4; attempt += 1) {
        const record = await store.load(draftRef.current.calibrationId);
        if (!record || record.syncStatus === 'saved') {
          if (record) {
            journalRecordRef.current = record;
            setCalibrationStatus('synced');
          }
          return;
        }
        if (record.syncStatus === 'conflict') {
          setCalibrationStatus('conflict');
          return;
        }
        const headers = { 'Content-Type': 'application/json' };
        if (record.etag) headers['If-Match'] = record.etag;
        else headers['If-None-Match'] = '*';
        const response = await fetch(
          `/api/future/calibrations/${encodeURIComponent(record.session.calibrationId)}`,
          {
            method: 'PUT',
            headers,
            body: JSON.stringify(record.session),
          },
        );
        const nextEtag = response.headers?.get?.('ETag') ?? null;
        if (response.status === 409 || response.status === 422) {
          let remoteSession = null;
          let remoteEtag = nextEtag;
          let remoteRevision = 0;
          try {
            const remoteResponse = await fetch(
              `/api/future/calibrations/${encodeURIComponent(record.session.calibrationId)}`,
              { headers: { Accept: 'application/json' } },
            );
            if (remoteResponse.ok) {
              const remotePayload = await remoteResponse.json();
              remoteSession = remotePayload?.calibration;
              remoteRevision = remotePayload?.revision;
              remoteEtag = remoteResponse.headers?.get?.('ETag') ?? remoteEtag;
            }
          } catch {
            // Keep the local branch pending if even the recovery read is offline.
          }
          if (
            !rebasedAfterConflict &&
            remoteSession &&
            typeof remoteEtag === 'string' &&
            Number.isSafeInteger(remoteRevision) &&
            isAppendOnlyCalibrationExtension(remoteSession, record.session)
          ) {
            const rebased = await store.markHostSynced(
              record.session.calibrationId,
              {
                etag: remoteEtag,
                expectedEtag: record.etag,
                syncedRevision: remoteRevision,
              },
            );
            journalRecordRef.current = rebased;
            setCalibrationStatus(rebased.syncStatus);
            if (rebased.syncStatus === 'saved') return;
            rebasedAfterConflict = true;
            continue;
          }
          const conflict = await store.markHostConflict(record.session.calibrationId, {
            etag: remoteEtag,
            expectedEtag: record.etag,
          });
          journalRecordRef.current = conflict;
          setCalibrationStatus('conflict');
          setCalibrationError('This journal has a different saved branch. Your choices remain on this device; continue the crossword or begin a fresh opening before syncing again.');
          return;
        }
        if (!response.ok) throw new Error('The local calibration server is unavailable.');
        const acknowledged = await store.markHostSynced(record.session.calibrationId, {
          etag: nextEtag,
          expectedEtag: record.etag,
          syncedRevision: record.revision,
        });
        journalRecordRef.current = acknowledged;
        setCalibrationStatus(acknowledged.syncStatus === 'saved' ? 'synced' : 'pending');
        if (acknowledged.syncStatus === 'saved') return;
      }
      setCalibrationStatus('pending');
    } catch {
      setCalibrationStatus('pending');
      setCalibrationError('Your calibration is on this device and will retry when the local server is available.');
    }
  }
  function scheduleJournalSync() {
    journalSyncQueue.current = journalSyncQueue.current
      .catch(() => {})
      .then(() => syncJournal());
    return journalSyncQueue.current;
  }
  async function persistCalibration(session) {
    journalSessionRef.current = session;
    setCalibrationError('');
    const task = journalWriteQueue.current
      .catch(() => {})
      .then(async () => {
        const store = journalStore.current;
        if (!store) throw new Error('IndexedDB is unavailable.');
        let prior = journalRecordRef.current;
        if (!prior || prior.session.calibrationId !== session.calibrationId)
          prior = await store.load(session.calibrationId);
        const saved = await store.save(session, {
          expectedRevision: prior?.revision ?? 0,
        });
        journalRecordRef.current = saved;
        setCalibrationStatus('pending');
        void scheduleJournalSync();
        return saved;
      });
    journalWriteQueue.current = task.catch(() => {});
    try {
      await task;
      return true;
    } catch (error) {
      const current = /** @type {{session: import('@crossword/domain').CalibrationSessionV1, revision:number, hostRevision:number, etag:string|null, syncStatus:'pending'|'saved'|'conflict'}|undefined} */ (
        error instanceof CalibrationJournalStorageError
          ? error.current
          : undefined
      );
      if (current) {
        journalRecordRef.current = current;
        journalSessionRef.current = current.session;
        setCalibrationStatus('conflict');
      } else {
        setCalibrationStatus('local-error');
      }
      setCalibrationError(
        error instanceof Error
          ? error.message
          : 'The calibration could not be saved locally.',
      );
      return false;
    }
  }

  useEffect(() => {
    document.title = 'Crossword · A personal beginning';
    return () => {
      document.title = 'Crossword Puzzle';
    };
  }, []);
  useEffect(() => {
    setStorageOkay(writeDraft(draft));
  }, [draft]);
  useEffect(() => {
    if (calibrationReady) presentedAt.current = new Date().toISOString();
  }, [step, draft.calibrationId, calibrationReady]);
  useEffect(() => {
    if (!playing) heading.current?.focus({ preventScroll: true });
  }, [step, playing]);
  useEffect(
    () => () => {
      request.current?.abort();
      hypothesisRequest.current?.abort();
      void journalStore.current?.close();
    },
    [],
  );
  useEffect(() => {
    const retry = () => void scheduleJournalSync();
    window.addEventListener('online', retry);
    return () => window.removeEventListener('online', retry);
  }, [draft.calibrationId]);
  useEffect(() => {
    if (step !== 5 || !calibrationReady) return undefined;
    if (!hypothesisSourceAvailable) {
      // Skipping calibration leaves no reviewed choice to interpret. Treat
      // that as an ordinary empty state and avoid the host's not-ready path.
      setHypothesisDeck(null);
      setHypothesisResponses({});
      setHypothesisError('');
      setHypothesisState('idle');
      return undefined;
    }
    const controller = new AbortController();
    hypothesisRequest.current?.abort();
    hypothesisRequest.current = controller;
    setHypothesisState('loading');
    setHypothesisError('');
    loadCalibrationHypotheses({
      calibrationId: draft.calibrationId,
      signal: controller.signal,
    })
      .then((payload) => {
        if (controller.signal.aborted) return;
        setHypothesisDeck(payload?.deck ?? null);
        setHypothesisResponses(payload?.responses ?? {});
        setHypothesisState(payload?.deck ? 'ready' : 'idle');
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setHypothesisDeck(null);
        setHypothesisResponses({});
        setHypothesisState('idle');
      });
    return () => {
      controller.abort();
      if (hypothesisRequest.current === controller)
        hypothesisRequest.current = null;
    };
  }, [calibrationReady, draft.calibrationId, hypothesisSourceAvailable, step]);
  useEffect(() => {
    if (profileOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [profileOpen]);

  async function persist(value) {
    request.current?.abort();
    const revision = ++saveRevision.current;
    const controller = new AbortController();
    request.current = controller;
    setSaveState('saving');
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      const result = await saveProfile(value, controller.signal);
      profileConflictRef.current = false;
      if (revision === saveRevision.current) {
        if (typeof result.updatedAt === 'string') {
          setDraft((current) => ({
            ...current,
            profileUpdatedAt: result.updatedAt,
          }));
        }
        setSaveState('saved');
      }
      return true;
    } catch (error) {
      profileConflictRef.current =
        error instanceof Error && 'status' in error && error.status === 409;
      if (revision === saveRevision.current)
        setSaveState(profileConflictRef.current ? 'conflict' : 'offline');
      return false;
    } finally {
      window.clearTimeout(timeout);
    }
  }
  function trackHostProfileReady(readiness) {
    hostProfileReadyRef.current = readiness;
    setHostProfileReady(readiness);
  }
  useEffect(() => {
    if (playing && !hostProfileReady) {
      trackHostProfileReady(persist(draft));
    }
  }, [playing, draft.id, hostProfileReady]);
  useEffect(() => {
    if (!playing) return undefined;
    let active = true;
    const retryWhenOnline = () => {
      const previousReadiness = hostProfileReadyRef.current;
      if (!previousReadiness || profileRetrying.current) return;
      profileRetrying.current = true;
      Promise.resolve(previousReadiness)
        .then((saved) => {
          if (
            !active ||
            saved ||
            profileConflictRef.current ||
            !navigator.onLine ||
            hostProfileReadyRef.current !== previousReadiness
          )
            return;
          const retry = persist(draftRef.current);
          trackHostProfileReady(retry);
          return retry;
        })
        .catch(() => {})
        .finally(() => {
          profileRetrying.current = false;
        });
    };
    window.addEventListener('online', retryWhenOnline);
    return () => {
      active = false;
      window.removeEventListener('online', retryWhenOnline);
    };
  }, [playing]);
  async function reloadSavedProfile() {
    request.current?.abort();
    saveRevision.current++;
    setSaveState('loading');
    setProfileLoadError('');
    try {
      const saved = await loadSavedProfile(draft.id);
      profileConflictRef.current = false;
      setDraft(saved);
      trackHostProfileReady(Promise.resolve(true));
      setSaveState('saved');
    } catch {
      setProfileLoadError('The saved beginning could not be loaded. Try again.');
      setSaveState('conflict');
    }
  }

  async function exportProfile() {
    setLifecycleState('exporting');
    setLifecycleError('');
    try {
      const response = await fetch(
        `/api/future/profile/${encodeURIComponent(draftRef.current.id)}/export`,
        { headers: { Accept: 'application/json' } },
      );
      if (!response.ok) throw new Error('The profile archive could not be downloaded.');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `crossword-profile-${draftRef.current.id}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setLifecycleState('idle');
    } catch (error) {
      setLifecycleState('error');
      setLifecycleError(error instanceof Error ? error.message : 'The profile archive could not be downloaded.');
    }
  }

  async function importProfile(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || lifecycleState === 'importing') return;
    setLifecycleState('importing');
    setLifecycleError('');
    try {
      const archive = JSON.parse(await file.text());
      const profileId = archive?.profileId;
      const importedDraft = archive?.startingProfile?.draft;
      const updatedAt = archive?.startingProfile?.updatedAt;
      if (
        typeof profileId !== 'string' ||
        !validateDraft(importedDraft) ||
        importedDraft.id !== profileId ||
        typeof updatedAt !== 'string'
      ) {
        throw new Error('The profile archive is invalid or incomplete.');
      }
      const response = await fetch(
        `/api/future/profile/${encodeURIComponent(profileId)}/import`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(archive),
        },
      );
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof result.error === 'string'
            ? result.error
            : 'The profile archive could not be restored.',
        );
      }
      const restored = { ...importedDraft, profileUpdatedAt: updatedAt };
      writeDraft(restored);
      draftRef.current = restored;
      setDraft(restored);
      setPlaying(restored.complete);
      setHostProfileReady(Promise.resolve(true));
      setProfileOpen(false);
      setLifecycleState('idle');
    } catch (error) {
      setLifecycleState('error');
      setLifecycleError(
        error instanceof Error
          ? error.message
          : 'The profile archive could not be restored.',
      );
    }
  }

  async function deleteProfile() {
    if (lifecycleState === 'deleting') return;
    if (!window.confirm('Delete this local profile, its solve history, and its calibration? This cannot be undone.')) return;
    const profileId = draftRef.current.id;
    setLifecycleState('deleting');
    setLifecycleError('');
    try {
      const response = await fetch(`/api/future/profile/${encodeURIComponent(profileId)}`, {
        method: 'DELETE',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error('The local profile could not be deleted.');
      await Promise.allSettled([
        journalStore.current?.removeProfile?.(profileId),
        createFutureJournalStore().removeProfile(profileId),
      ]);
      window.localStorage.removeItem(STORAGE_KEY);
      window.localStorage.removeItem(`${PRIVATE_PUZZLE_STORAGE_PREFIX}${profileId}`);
      window.localStorage.removeItem(
        `${PRIVATE_PUZZLE_STORAGE_PREFIX}${profileId}${PRIVATE_PUZZLE_HISTORY_SUFFIX}`,
      );
      window.localStorage.removeItem(`crossword.future.clue-flags.v1:${profileId}`);
      const value = freshDraft();
      setDraft(value);
      setPlaying(false);
      setProfileOpen(false);
      setHostProfileReady(null);
      setLifecycleState('idle');
    } catch (error) {
      setLifecycleState('error');
      setLifecycleError(error instanceof Error ? error.message : 'The local profile could not be deleted.');
    }
  }

  async function retainProfile() {
    if (retentionState === 'running' || lifecycleState !== 'idle') return;
    const profileId = draftRef.current.id;
    setRetentionState('running');
    setRetentionSummary('');
    setLifecycleError('');
    try {
      const endpoint = `/api/future/profile/${encodeURIComponent(profileId)}/retention`;
      const previewResponse = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ dryRun: true }),
      });
      const preview = await previewResponse.json().catch(() => ({}));
      if (!previewResponse.ok) {
        throw new Error(typeof preview.error === 'string' ? preview.error : 'Retention preview failed.');
      }
      const selected = preview.selected ?? {};
      const selectedJobs = Number(selected.transientJobs ?? 0) + Number(selected.privateReadyJobs ?? 0);
      const selectedArtifacts = Number(selected.privateSelections ?? 0) + Number(selected.v2Candidates ?? 0);
      if (selectedJobs === 0 && selectedArtifacts === 0) {
        setRetentionSummary('Nothing old is ready to prune.');
        setRetentionState('idle');
        return;
      }
      const confirmed = window.confirm(
        `Prune ${selectedJobs} old generation job${selectedJobs === 1 ? '' : 's'} and ${selectedArtifacts} private artifact${selectedArtifacts === 1 ? '' : 's'}? Solve history and calibration stay untouched.`,
      );
      if (!confirmed) {
        setRetentionState('idle');
        return;
      }
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ dryRun: false }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof result.error === 'string' ? result.error : 'Retention cleanup failed.');
      }
      const deleted = result.deleted ?? {};
      setRetentionSummary(
        `Pruned ${deleted.jobs ?? 0} old job${deleted.jobs === 1 ? '' : 's'} and ${(deleted.privateSelections ?? 0) + (deleted.v2Candidates ?? 0)} private artifact${(deleted.privateSelections ?? 0) + (deleted.v2Candidates ?? 0) === 1 ? '' : 's'}.`,
      );
      setRetentionState('idle');
    } catch (error) {
      setRetentionState('error');
      setLifecycleError(error instanceof Error ? error.message : 'Retention cleanup failed.');
    }
  }
  function chooseFirstStimulus(item) {
    if (draftRef.current.firstStimulus === item.id) return;
    const primary = item.legacy_ids?.find((id) =>
      catalog.objects.some((object) => object.id === id),
    );
    update({
      firstStimulus: item.id,
      object: primary ?? null,
      companion: null,
      variation: null,
      traces: [],
      excluded: [],
      reflection: null,
    });
  }
  function chooseCompanion(item) {
    const companion = item.legacy_ids?.find((id) =>
      catalog.companions.some((candidate) => candidate.id === id),
    );
    if (companion) update({ companion, excluded: [], reflection: null });
  }
  function chooseVariation(item) {
    update({
      variation:
        item.id === draft.firstStimulus ? 'keep-original' : item.id,
      excluded: [],
      reflection: null,
    });
  }
  function toggleTrace(item) {
    const trace = item.legacy_ids?.find((value) =>
      catalog.traces.includes(value),
    );
    if (!trace) return;
    const traces = draft.traces.includes(trace)
      ? draft.traces.filter((value) => value !== trace)
      : draft.traces.length < 2
        ? [...draft.traces, trace]
        : draft.traces;
    update({ traces, excluded: [], reflection: null });
  }
  async function enter({ skipAll = false } = {}) {
    hypothesisRequest.current?.abort();
    hypothesisRequest.current = null;
    setHypothesisState(hypothesisDeck ? 'ready' : 'idle');
    setCalibrationBusy(true);
    try {
      let session = currentSession();
      const setup = setupFor();
      if (skipAll) {
        session = updateCalibrationCursor(
          session,
          /** @type {import('@crossword/domain').CalibrationMovementV1} */ (
            Math.min(5, step + 1)
          ),
        );
        session = skipCalibration(session, { reason: 'start-puzzle', setup });
      } else {
        session = completeCalibration(session, { setup });
      }
      await persistCalibration(session);
    } catch (error) {
      setCalibrationStatus('local-error');
      setCalibrationError(
        error instanceof Error
          ? error.message
          : 'This calibration could not be completed.',
      );
    }
    const value = { ...draftRef.current, complete: true, step: 5 };
    setDraft(value);
    trackHostProfileReady(persist(value));
    setPlaying(true);
    setCalibrationBusy(false);
  }
  async function openHypotheses() {
    if (hypothesisState === 'generating') return;
    setHypothesisState('generating');
    setHypothesisError('');
    const controller = new AbortController();
    hypothesisRequest.current?.abort();
    hypothesisRequest.current = controller;
    try {
      const value = draftRef.current;
      const savedProfile = await persist(value);
      trackHostProfileReady(Promise.resolve(savedProfile));
      if (!savedProfile) {
        throw new Error(
          'Save the starting profile to the local host before opening these paths.',
        );
      }
      await scheduleJournalSync();
      const storedJournal = await journalStore.current?.load(value.calibrationId);
      if (!storedJournal || storedJournal.syncStatus !== 'saved') {
        throw new Error(
          'The opening journal is still on this device. Reconnect to the local crossword host and try again.',
        );
      }
      journalRecordRef.current = storedJournal;
      journalSessionRef.current = storedJournal.session;
      const payload = await createCalibrationHypotheses({
        calibrationId: value.calibrationId,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setHypothesisDeck(payload?.deck ?? null);
      setHypothesisResponses(payload?.responses ?? {});
      setHypothesisState(payload?.deck ? 'ready' : 'idle');
      if (!payload?.deck) throw new Error('The local host returned no word paths.');
    } catch (error) {
      if (controller.signal.aborted) return;
      setHypothesisState('unavailable');
      setHypothesisError(
        error instanceof Error
          ? error.message
          : 'Local word paths are unavailable right now. The crossword is still ready.',
      );
    } finally {
      if (hypothesisRequest.current === controller)
        hypothesisRequest.current = null;
    }
  }

  async function respondToHypothesis(proposalId, response) {
    if (!hypothesisDeck) throw new Error('These word paths are not loaded.');
    setBusyHypothesisId(proposalId);
    try {
      const { result } = await respondToCalibrationHypothesis({
        calibrationId: draftRef.current.calibrationId,
        proposalId,
        deckId: hypothesisDeck.deckId,
        response,
      });
      setHypothesisDeck(result?.deck ?? hypothesisDeck);
      setHypothesisResponses(result?.responses ?? {});
      setHypothesisError('');
    } finally {
      setBusyHypothesisId(null);
    }
  }

  async function reviseHypothesis(proposalId, responseId, action) {
    setBusyHypothesisId(proposalId);
    try {
      const { result } = await reviseCalibrationHypothesisResponse({
        calibrationId: draftRef.current.calibrationId,
        proposalId,
        responseId,
        action,
      });
      setHypothesisDeck(result?.deck ?? hypothesisDeck);
      setHypothesisResponses(result?.responses ?? {});
      setHypothesisError('');
    } finally {
      setBusyHypothesisId(null);
    }
  }
  async function advance() {
    if (step === 5) {
      await enter();
      return;
    }
    if (!calibrationReady || calibrationBusy) return;
    setCalibrationBusy(true);
    try {
      let session = currentSession();
      if (step <= 3) {
        let chosenIds = [];
        /** @type {import('@crossword/domain').CalibrationRelationV1 | undefined} */
        let relation;
        if (step === 0 && draft.firstStimulus) {
          chosenIds = [draft.firstStimulus];
        } else if (step === 1 && draft.companion) {
          const companionStimulus = stimulusByLegacyId(draft.companion);
          if (companionStimulus) chosenIds = [companionStimulus.id];
          if (chosenIds.length && draft.firstStimulus) {
            relation = {
              kind: 'place-beside',
              fromStimulusId: draft.firstStimulus,
              toStimulusId: chosenIds[0],
            };
          }
        } else if (step === 2 && draft.variation) {
          const original = draft.firstStimulus;
          if (draft.variation === 'keep-original') {
            chosenIds = [original];
            relation = { kind: 'keep-original', stimulusId: original };
          } else {
            chosenIds = [draft.variation];
            if (original) {
              relation = {
                kind: 'contrast',
                fromStimulusId: original,
                toStimulusId: draft.variation,
              };
            }
          }
        } else if (step === 3 && draft.traces.length) {
          chosenIds = draft.traces
            .map((trace) => stimulusByLegacyId(trace)?.id)
            .filter(Boolean);
        }
        const response = /** @type {import('@crossword/domain').CalibrationResponseV1} */ (
          chosenIds.length
            ? { kind: 'choose', chosenIds }
            : { kind: 'pass' }
        );
        session = appendCalibrationObservation(
          session,
          {
            movement: step + 1,
            offered: presentation?.offered ?? [],
            response,
            ...(step === 0 ? { retractMovements: [2, 3, 4] } : {}),
            ...(response.kind === 'choose' && relation ? { relation } : {}),
            presentedAt: presentedAt.current,
            nextMovement: step + 2,
          },
        );
      } else if (step === 4) {
        session = updateCalibrationCursor(session, 5);
        session = { ...session, setup: setupFor() };
      }
      await persistCalibration(session);
      update({ step: step + 1 });
    } catch (error) {
      setCalibrationStatus('local-error');
      setCalibrationError(
        error instanceof Error
          ? error.message
          : 'This movement could not be recorded.',
      );
    } finally {
      setCalibrationBusy(false);
    }
  }
  async function skip() {
    if (step === 0) {
      await enter({ skipAll: true });
      return;
    }
    if (step < 1 || step > 3 || !calibrationReady || calibrationBusy) return;
    setCalibrationBusy(true);
    try {
      const session = appendCalibrationObservation(
        currentSession(),
        {
          movement: step + 1,
          offered: presentation?.offered ?? [],
          response: { kind: 'pass' },
          presentedAt: presentedAt.current,
          nextMovement: step + 2,
        },
      );
      await persistCalibration(session);
      const patch =
        step === 1
          ? { companion: null, reflection: null }
          : step === 2
            ? { variation: null, reflection: null }
            : { traces: [], reflection: null };
      update({ ...patch, step: step + 1 });
    } catch (error) {
      setCalibrationStatus('local-error');
      setCalibrationError(
        error instanceof Error
          ? error.message
          : 'This movement could not be recorded.',
      );
    } finally {
      setCalibrationBusy(false);
    }
  }
  async function goBack() {
    if (step <= 0 || !calibrationReady || calibrationBusy) return;
    setCalibrationBusy(true);
    try {
      const nextStep = step - 1;
      const session = updateCalibrationCursor(
        currentSession(),
        /** @type {import('@crossword/domain').CalibrationMovementV1} */ (
          nextStep + 1
        ),
      );
      await persistCalibration(session);
      update({ step: nextStep });
    } catch (error) {
      setCalibrationError(
        error instanceof Error ? error.message : 'This movement could not be reopened.',
      );
    } finally {
      setCalibrationBusy(false);
    }
  }

  function keepCalibrationLocal() {
    setCalibrationConflictAcknowledged(true);
    setCalibrationError('');
  }

  function startFreshCalibrationBranch() {
    const nextDraft = createCalibrationRecoveryDraft(draftRef.current);
    // The old record remains in IndexedDB under its original calibration id.
    // Only the active draft pointer changes; no raw response is rewritten.
    journalRecordRef.current = null;
    journalSessionRef.current = null;
    hypothesisRequest.current?.abort();
    setHypothesisDeck(null);
    setHypothesisResponses({});
    setHypothesisError('');
    setHypothesisState('idle');
    setCalibrationConflictAcknowledged(false);
    setCalibrationError('');
    setCalibrationReady(false);
    setCalibrationStatus('loading');
    draftRef.current = nextDraft;
    setDraft(nextDraft);
  }
  const canContinue =
    calibrationReady &&
    !calibrationBusy &&
    (step === 0
      ? Boolean(draft.firstStimulus)
      : step === 1
        ? Boolean(draft.companion)
        : step === 2
          ? Boolean(draft.variation)
          : step === 3
            ? draft.traces.length > 0
            : true);
  const hasCalibrationResponse = Boolean(
    journalRecordRef.current?.session.observations.length ||
      journalRecordRef.current?.session.actions.length,
  );
  const calibrationMessage =
    calibrationStatus === 'loading'
      ? 'Opening your private calibration journal…'
      : calibrationStatus === 'synced'
        ? 'Your choices are saved on this device and the local server.'
        : calibrationStatus === 'pending'
          ? 'Saved on this device · waiting for the local server.'
          : calibrationStatus === 'conflict'
            ? 'This calibration has another saved version and needs review.'
            : calibrationStatus === 'local-error'
              ? 'Local journal storage is unavailable; your crossword is still ready.'
              : 'A private journal will keep track of what was shown and chosen.';
  const calibrationRecovery = describeCalibrationConflict(
    journalRecordRef.current,
    calibrationStatus,
  );
  const saveMessage =
    saveState === 'saving'
      ? 'Saving your beginning…'
      : saveState === 'loading'
        ? 'Loading your saved beginning…'
      : saveState === 'saved'
        ? 'Saved on this device and your local server.'
        : saveState === 'conflict'
          ? 'This beginning changed on the local server. Load its latest version to continue saving.'
        : saveState === 'offline'
          ? 'Kept on this device. The local server is unavailable.'
          : 'Kept on this device. Save changes to keep a copy on your local server.';

  return (
    <div className={`future-root ${playing ? 'future-playing' : ''}`}>
      <header className="future-header">
        <a
          className="future-brand"
          href="/future"
          aria-label="Crossword future"
        >
          <Mark />
          <span>
            crossword<span className="future-brand-divider">/</span>
            <em>future</em>
          </span>
        </a>
        <span className="future-header-note">
          {playing
            ? 'A more personal beginning'
            : 'Every word begins somewhere'}
        </span>
        {playing ? (
          <button
            className="future-text-button"
            onClick={() => setProfileOpen(true)}
          >
            <span className="future-status-dot" />
            Your constellation <span aria-hidden="true">↗</span>
          </button>
        ) : (
          <a className="future-text-button" href="/">
            Daily crossword <span aria-hidden="true">↗</span>
          </a>
        )}
      </header>

      {playing ? (
        <>
          <div className="future-solver">
            <FutureSolver
              weekday={draft.weekday}
              profileId={draft.id}
              profileReady={hostProfileReady}
              onWeekdayChange={(weekday) => update({ weekday })}
              modelPreference={draft.modelPreference}
              onModelPreferenceChange={(modelPreference) => update({ modelPreference })}
            />
            <LearningReview profileId={draft.id} profileReady={hostProfileReady} />
          </div>
          <dialog
            className={`future-profile-dialog${hypothesisDeck ? ' has-hypotheses' : ''}`}
            ref={dialog}
            onCancel={() => setProfileOpen(false)}
            onClose={() => setProfileOpen(false)}
            aria-labelledby="future-profile-title"
          >
            <div className="future-dialog-top">
              <span className="future-eyebrow">The starting episteme</span>
              <button
                aria-label="Close constellation"
                className="future-close"
                onClick={() => setProfileOpen(false)}
              >
                ×
              </button>
            </div>
            <h2 id="future-profile-title">Room to become.</h2>
            <ProfileField draft={draft} update={update} showSettings />
            <EpistemeSnapshot
              profileId={draft.id}
              open={profileOpen}
              refreshKey={
                epistemeRefresh + (preferenceState === 'saved'
                  ? 1
                  : preferenceState === 'saving'
                    ? 2
                    : preferenceState === 'offline'
                      ? 3
                  : 0)
              }
              onChanged={() => {
                setPreferenceState('saved');
                setEpistemeRefresh((value) => value + 1);
              }}
            />
            <GameHistory profileId={draft.id} open={profileOpen} />
            <ProfileNarrativePanel
              profileId={draft.id}
              open={profileOpen}
              refreshKey={
                epistemeRefresh + (preferenceState === 'saved'
                  ? 1
                  : preferenceState === 'saving'
                    ? 2
                    : preferenceState === 'offline'
                      ? 3
                      : 0)
              }
              onAccepted={() => {
                setPreferenceState('saved');
                setEpistemeRefresh((value) => value + 1);
              }}
            />
            {hypothesisDeck ? (
              <CalibrationHypotheses
                deck={hypothesisDeck}
                responses={hypothesisResponses}
                busyProposalId={busyHypothesisId}
                loading={hypothesisState === 'loading'}
                error={hypothesisError}
                onRespond={respondToHypothesis}
                onAction={reviseHypothesis}
              />
            ) : (
              <div className="future-hypotheses-invitation">
                <div>
                  <p className="future-eyebrow">A small opening</p>
                  <p>
                    {hypothesisSourceAvailable
                      ? 'Invite the local model to follow a few tentative paths through the choices in your journal.'
                      : 'Choose at least one sign in the opening to trace a path. You can also leave the field open and enter the crossword.'}
                  </p>
                </div>
                <button
                  className="future-text-button"
                  disabled={
                    hypothesisState === 'generating' ||
                    hypothesisState === 'loading' ||
                    !calibrationReady ||
                    !hypothesisSourceAvailable
                  }
                  onClick={() => void openHypotheses()}
                >
                  {hypothesisState === 'generating'
                    ? 'Following a few threads…'
                    : hypothesisState === 'loading'
                      ? 'Checking for saved paths…'
                      : 'Trace possible paths'}
                  <span aria-hidden="true">✧</span>
                </button>
                {hypothesisError && (
                  <p className="future-hypotheses-error" role="alert">
                    {hypothesisError}
                  </p>
                )}
              </div>
            )}
            <p className="future-small" role="status" aria-live="polite">
              {preferenceState === 'saving'
                ? 'Saving that preference to your episteme…'
                : preferenceState === 'saved'
                  ? 'That preference is now part of your local episteme.'
                  : preferenceState === 'offline'
                    ? 'The choice stays on this device; the local episteme is unavailable.'
                    : 'Your selections and corrections shape a private, revisable word-field.'}
            </p>
            <p className="future-small">
              Your weekday sets the puzzle you play now. When you make a new
              personal crossword, Ollama and the local constructor build it
              from this calibration journal and your explicit word preferences.
              The daily feed remains at <a href="/">/</a>.
            </p>
            <p className="future-save-status" role="status">
              {saveMessage}
            </p>
            <div className="future-profile-data-actions" aria-label="Profile data">
              <input
                ref={importInput}
                className="future-visually-hidden"
                type="file"
                accept="application/json,.json"
                onChange={(event) => void importProfile(event)}
                aria-label="Choose a profile archive"
              />
              <button
                className="future-text-button"
                onClick={() => importInput.current?.click()}
                disabled={lifecycleState === 'exporting' || lifecycleState === 'importing' || lifecycleState === 'deleting'}
              >
                {lifecycleState === 'importing' ? 'Restoring archive…' : 'Restore profile archive'}
                <span aria-hidden="true">↑</span>
              </button>
              <button
                className="future-text-button"
                onClick={() => void exportProfile()}
                disabled={lifecycleState !== 'idle' || retentionState === 'running'}
              >
                {lifecycleState === 'exporting' ? 'Preparing archive…' : 'Download profile archive'}
                <span aria-hidden="true">↓</span>
              </button>
              <button
                className="future-text-button"
                onClick={() => void retainProfile()}
                disabled={lifecycleState !== 'idle' || retentionState === 'running'}
              >
                {retentionState === 'running' ? 'Checking old drafts…' : 'Prune old local drafts'}
              </button>
              <button
                className="future-text-button future-danger-button"
                onClick={() => void deleteProfile()}
                disabled={lifecycleState !== 'idle' || retentionState === 'running'}
              >
                {lifecycleState === 'deleting' ? 'Deleting profile…' : 'Delete local profile'}
              </button>
            </div>
            {retentionSummary && <p className="future-small" role="status">{retentionSummary}</p>}
            {lifecycleError && <p className="future-small" role="alert">{lifecycleError}</p>}
            {saveState === 'conflict' && (
              <div className="future-save-recovery" role="group" aria-label="Resolve profile save conflict">
                <p className="future-small">
                  Loading replaces these constellation settings with the saved
                  version. Your current crossword and its letters stay in
                  place.
                </p>
                {profileLoadError && (
                  <p className="future-small" role="alert">
                    {profileLoadError}
                  </p>
                )}
                <button
                  className="future-text-button"
                  onClick={() => void reloadSavedProfile()}
                >
                  Load latest saved beginning
                  <Arrow />
                </button>
              </div>
            )}
            <div className="future-dialog-actions">
              <button
                className="future-text-button"
                onClick={async () => {
                  if (
                    !window.confirm(
                      'Begin setup again? This will close the current puzzle and clear its unsaved letters. Your saved starting profile will be replaced when you finish setup.',
                    )
                  )
                    return;
                  try {
                    const active = journalSessionRef.current;
                    if (active?.status === 'in-progress') {
                      await persistCalibration(
                        skipCalibration(active, {
                          reason: 'skip-calibration',
                          setup: setupFor(),
                        }),
                      );
                    }
                  } catch {
                    // The prior immutable session remains available if local storage is offline.
                  }
                  const value = {
                    ...freshDraft(),
                    id: draft.id,
                    profileUpdatedAt: draft.profileUpdatedAt,
                    weekday: draft.weekday,
                    learningLanguage: draft.learningLanguage,
                    modelPreference: draft.modelPreference,
                  };
                  setDraft(value);
                  setProfileOpen(false);
                  setPlaying(false);
                  setSaveState('idle');
                }}
              >
                Begin again
              </button>
              <button
                className="future-primary"
                onClick={() => trackHostProfileReady(persist(draft))}
                disabled={saveState === 'saving' || saveState === 'loading'}
              >
                {saveState === 'saving'
                  ? 'Saving…'
                  : saveState === 'loading'
                    ? 'Loading…'
                    : 'Save changes'}
                <Arrow />
              </button>
            </div>
          </dialog>
        </>
      ) : (
        <>
          <div className="future-stage-layout">
            <aside className="future-left-rail" aria-label="Setup progress">
              <p className="future-eyebrow">A personal crossword</p>
              <ol className="future-chapters">
                {chapters.map((chapter, index) => (
                  <li
                    key={chapter}
                    className={
                      index === step
                        ? 'is-current'
                        : index < step
                          ? 'is-past'
                          : ''
                    }
                    aria-current={index === step ? 'step' : undefined}
                  >
                    <span>0{index + 1}</span>
                    {chapter}
                    {index < step && <i aria-hidden="true">·</i>}
                  </li>
                ))}
              </ol>
              <div className="future-rail-word" aria-hidden="true">
                ACROSS
              </div>
              <p className="future-rail-foot">
                A few small choices.
                <br />
                An opening, all your own.
              </p>
            </aside>
            <main className="future-main">
              <div className="future-step-label">
                <span className="future-eyebrow">
                  0{step + 1} / 06 <span>—</span> {chapters[step]}
                </span>
                <span className="future-step-dots" aria-hidden="true">
                  {chapters.map((chapter, index) => (
                    <i
                      key={chapter}
                      className={index <= step ? 'is-lit' : ''}
                    />
                  ))}
                </span>
              </div>
              <section
                key={step}
                className={`future-scene future-scene-${step}`}
                aria-labelledby="future-heading"
              >
                <h1 id="future-heading" ref={heading} tabIndex={-1}>
                  {titles[step]}
                  {titleEnds[step] && (
                    <>
                      <br />
                      <em>{titleEnds[step]}</em>
                    </>
                  )}
                </h1>
                <p className="future-introduction">{descriptions[step]}</p>
                {step === 0 && (
                  <>
                    <div
                      className="future-mode-switch"
                      role="group"
                      aria-label="How the signs appear"
                    >
                      {[
                        ['visual', 'Color & form'],
                        ['monochrome', 'Monochrome'],
                        ['text-equivalent', 'Words only'],
                      ].map(([mode, label]) => (
                        <button
                          key={mode}
                          type="button"
                          className={`future-mode-option ${draft.presentationMode === mode ? 'is-selected' : ''}`}
                          aria-pressed={draft.presentationMode === mode}
                          disabled={hasCalibrationResponse}
                          onClick={() => update({ presentationMode: mode })}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <div className="future-object-grid future-encounter-grid">
                      {(presentation?.shownItems ?? []).map((stimulus, index) => {
                        const primary = catalog.objects.find((item) =>
                          stimulus.legacy_ids?.includes(item.id),
                        );
                        return (
                          <ObjectChoice
                            key={stimulus.id}
                            item={
                              primary ?? {
                                id: stimulus.id,
                                label: stimulus.accessible_label,
                              }
                            }
                            stimulus={stimulus}
                            mode={draft.presentationMode}
                            index={index}
                            selected={draft.firstStimulus === stimulus.id}
                            onChoose={() => chooseFirstStimulus(stimulus)}
                          />
                        );
                      })}
                    </div>
                    <p className="future-stimulus-note">
                      A choice is only a trace here, not an explanation. We
                      remember which signs appeared and what you kept.
                    </p>
                  </>
                )}
                {step === 1 && (
                  <div className="future-company">
                    <div className="future-held-object">
                      <span className="future-eyebrow">You brought</span>
                      {draft.firstStimulus && (
                        <StimulusArtwork
                          item={stimulusById(draft.firstStimulus)}
                          presentationMode={draft.presentationMode}
                        />
                      )}
                      <span>
                        {stimulusById(draft.firstStimulus)?.accessible_label ??
                          selectedObject?.label}
                      </span>
                      <span
                        className="future-company-line"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="future-companion-grid">
                      {(presentation?.shownItems ?? []).map(
                        (stimulus, index) => {
                          const companion = catalog.companions.find((item) =>
                            stimulus.legacy_ids?.includes(item.id),
                          );
                          return (
                            <ObjectChoice
                              key={stimulus.id}
                              item={companion ?? { id: stimulus.id, label: stimulus.accessible_label }}
                              stimulus={stimulus}
                              mode={draft.presentationMode}
                              index={index}
                              selected={Boolean(companion && draft.companion === companion.id)}
                              onChoose={() => chooseCompanion(stimulus)}
                            />
                          );
                        },
                      )}
                    </div>
                  </div>
                )}
                {step === 2 && (
                  <div
                    className="future-variation-grid"
                    role="group"
                    aria-label="Keep the original color or choose a variation"
                  >
                    {(presentation?.shownItems ?? []).map((item) => {
                      const original = item.id === draft.firstStimulus;
                      const selected = original
                        ? draft.variation === 'keep-original'
                        : draft.variation === item.id;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          className={`future-variation-choice ${selected ? 'is-selected' : ''}`}
                          aria-pressed={selected}
                          onClick={() => chooseVariation(item)}
                        >
                          <StimulusArtwork
                            item={item}
                            presentationMode={draft.presentationMode}
                          />
                          <span className="future-variation-label">
                            {original
                              ? 'Keep the original'
                              : stimulusCaption(item)}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
                {step === 3 && (
                  <div className="future-rhythm">
                    <div
                      className="future-traces future-mixed-traces"
                      role="group"
                      aria-label="Keep up to two word, number, or symbol traces"
                    >
                      {(presentation?.shownItems ?? []).map((item, index) => {
                        const trace = item.legacy_ids?.find((value) =>
                          catalog.traces.includes(value),
                        );
                        if (!trace) return null;
                        const selected = draft.traces.includes(trace);
                        return (
                          <button
                            key={item.id}
                            type="button"
                            className={`future-trace future-trace-stimulus trace-${index} ${selected ? 'is-chosen' : ''}`}
                            aria-label={item.accessible_label}
                            aria-pressed={selected}
                            disabled={draft.traces.length >= 2 && !selected}
                            onClick={() => toggleTrace(item)}
                          >
                            <StimulusArtwork
                              item={item}
                              presentationMode={draft.presentationMode}
                            />
                            <span className="future-trace-label">{trace}</span>
                            <span aria-hidden="true">
                              {selected ? '·' : ''}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    <p className="future-choice-count" role="status">
                      {draft.traces.length} of 2 kept <span>·</span> No need to
                      explain.
                    </p>
                  </div>
                )}
                {step === 4 && (
                  <>
                  <div className="future-rhythm">
                      <div
                        className="future-days"
                        role="group"
                        aria-label="Crossword difficulty"
                      >
                        {catalog.days.map((day) => (
                          <button
                            key={day.id}
                            className={draft.weekday === day.id ? 'is-chosen' : ''}
                            aria-pressed={draft.weekday === day.id}
                            aria-label={day.label}
                            onClick={() => update({ weekday: day.id })}
                          >
                            <span>{day.short}</span>
                            <span className="future-day-bars" aria-hidden="true">
                              {Array.from({ length: 6 }, (_, index) => (
                                <i
                                  key={index}
                                  className={index < day.level ? 'is-lit' : ''}
                                />
                              ))}
                            </span>
                          </button>
                        ))}
                      </div>
                      <div className="future-day-story" aria-live="polite">
                        <span className="future-day-monogram" aria-hidden="true">
                          {selectedDay.short[0]}
                        </span>
                        <div>
                          <p className="future-eyebrow">{selectedDay.label}</p>
                          <h2>{selectedDay.title}</h2>
                          <p>{selectedDay.description}</p>
                        </div>
                      </div>
                      <p className="future-small">
                        A difficulty, not a date. Every day is available every day.
                      </p>
                      <div className="future-language">
                        <div>
                          <label htmlFor="future-learning">
                            Leave a little room for another language?
                          </label>
                          <p>Optional. An interest to carry into future puzzles.</p>
                        </div>
                        <select
                          id="future-learning"
                          value={draft.learningLanguage}
                          onChange={(event) =>
                            update({ learningLanguage: event.target.value })
                          }
                        >
                          {catalog.languages.map((language) => (
                            <option key={language}>{language}</option>
                          ))}
                        </select>
                      </div>
                      <details className="future-conventions">
                        <summary>
                          A few signs along the way <span aria-hidden="true">+</span>
                        </summary>
                        <p>
                          Clues and answers agree in tense and number. Quotation
                          marks often ask for something you could say. Square
                          brackets can describe a sound or a gesture. A question
                          mark often hints at wordplay. Thursday may ask you to
                          discover a new rule.
                        </p>
                      </details>
                    </div>
                  </>
                )}
                {step === 5 && (
                  <>
                    <ProfileField draft={draft} update={update} />
                    {hypothesisDeck ? (
                      <CalibrationHypotheses
                        deck={hypothesisDeck}
                        responses={hypothesisResponses}
                        busyProposalId={busyHypothesisId}
                        loading={hypothesisState === 'loading'}
                        error={hypothesisError}
                        onRespond={respondToHypothesis}
                        onAction={reviseHypothesis}
                      />
                    ) : (
                      <div className="future-hypotheses-invitation">
                        <div>
                          <p className="future-eyebrow">A small opening</p>
                          <p>
                            {hypothesisSourceAvailable
                              ? 'If you like, let the local model follow a few possible paths from what you chose. It may be suggestive, mistaken, or simply not yours.'
                              : 'Choose at least one sign in the opening to trace a path. You can also leave the field open and enter the crossword.'}
                          </p>
                        </div>
                        <button
                          className="future-text-button"
                          disabled={
                            hypothesisState === 'generating' ||
                            hypothesisState === 'loading' ||
                            !calibrationReady ||
                            !hypothesisSourceAvailable
                          }
                          onClick={() => void openHypotheses()}
                        >
                          {hypothesisState === 'generating'
                            ? 'Following a few threads…'
                            : hypothesisState === 'loading'
                              ? 'Checking for saved paths…'
                              : 'Trace possible paths'}
                          <span aria-hidden="true">✧</span>
                        </button>
                        {hypothesisError && (
                          <p className="future-hypotheses-error" role="alert">
                            {hypothesisError}
                          </p>
                        )}
                      </div>
                    )}
                    <p className="future-honest-note">
                      Your weekday is ready. These first choices remain
                      separate from knowledge and preference. Any path the
                      model offers stays provisional until you respond.
                    </p>
                  </>
                )}
              </section>
              <footer className="future-navigation">
                <div>
                  {step > 0 && (
                    <button
                      className="future-text-button"
                      onClick={() => void goBack()}
                      disabled={calibrationBusy || !calibrationReady}
                    >
                      <Arrow back />
                      Back
                    </button>
                  )}
                </div>
                <div className="future-forward">
                  {step < 4 && (
                    <button
                      className="future-text-button future-skip"
                      onClick={() => void skip()}
                      disabled={calibrationBusy || !calibrationReady}
                    >
                      {step === 0
                        ? 'Go straight to a puzzle'
                        : 'Let this one pass'}
                    </button>
                  )}
                  <button
                    className="future-primary"
                    disabled={!canContinue}
                    onClick={() => void advance()}
                  >
                    {step === 5
                      ? calibrationBusy
                        ? 'Preparing…'
                        : 'Enter crossword'
                      : step === 4
                        ? 'See your beginning'
                        : 'Continue'}
                    <Arrow />
                  </button>
                </div>
              </footer>
              <p
                className="future-calibration-status"
                data-state={
                  calibrationStatus === 'synced'
                    ? 'synced'
                    : calibrationStatus === 'conflict' || calibrationStatus === 'local-error'
                      ? 'error'
                      : calibrationStatus === 'pending'
                        ? 'pending'
                        : 'ready'
                }
                role="status"
                aria-live="polite"
              >
                {calibrationMessage}
              </p>
              {calibrationRecovery && (
                <section
                  className="future-calibration-recovery"
                  aria-labelledby="future-calibration-recovery-title"
                >
                  <p
                    className="future-eyebrow"
                    id="future-calibration-recovery-title"
                  >
                    {calibrationRecovery.title}
                  </p>
                  <p>{calibrationRecovery.message}</p>
                  <div className="future-calibration-recovery-actions">
                    <button
                      className="future-text-button"
                      onClick={keepCalibrationLocal}
                    >
                      {calibrationRecovery.actions[0].label}
                    </button>
                    <button
                      className="future-text-button"
                      onClick={startFreshCalibrationBranch}
                    >
                      {calibrationRecovery.actions[1].label}
                    </button>
                  </div>
                  {calibrationConflictAcknowledged && (
                    <p className="future-small" role="status">
                      This opening stays on this device. Its saved branch remains
                      separate until you start a fresh opening.
                    </p>
                  )}
                </section>
              )}
              {calibrationError && (
                <p className="future-small" role="alert">
                  {calibrationError}
                </p>
              )}
              {!storageOkay && (
                <p className="future-storage-warning" role="alert">
                  This browser cannot keep your progress. You can still
                  continue; keep this tab open until your profile is saved to
                  the local server.
                </p>
              )}
            </main>
            <aside className="future-right-rail">
              <div className="future-rail-word" aria-hidden="true">
                DOWN
              </div>
              <div className="future-marginalia">
                <span className="future-tiny-cross" aria-hidden="true">
                  +
                </span>
                <p>
                  {step === 0
                    ? 'Before a word has meaning, something draws us toward it.'
                    : step === 1
                      ? 'Meaning begins in the space between things.'
                      : step === 2
                        ? 'Some words feel familiar before we know why.'
                    : step === 3
                      ? 'A word, a number, a mark: let the small remnants stay.'
                      : step === 4
                        ? 'A weekday can be a mood rather than a date.'
                        : 'The next word might take you somewhere new.'}
                </p>
                <span className="future-eyebrow">
                  {step === 5
                    ? 'Always unfinished'
                    : 'There is no right answer'}
                </span>
              </div>
            </aside>
          </div>
          <footer className="future-page-footer">
            <span>Made of words. Shaped by you.</span>
            <span>No account. No right answers. Just a beginning.</span>
          </footer>
        </>
      )}
    </div>
  );
}
