import React, { useEffect, useRef, useState } from 'react';
import { catalog, LOCAL_MODEL_CHOICES } from './episteme';
import {
  listPrivatePuzzles,
  restorePrivatePuzzle,
  savePrivatePuzzle,
} from './privatePuzzleStore';
import {
  adaptFutureTokenPuzzle,
  produceFutureTokenPuzzle,
} from './tokenManifest';

const LOCAL_OLLAMA_SOURCE = 'local-ollama-xfill';
const PENDING_JOB_STORAGE_PREFIX = 'crossword.future.private-job.v1:';
const WEEKDAYS = new Set([
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
]);

const LOCAL_MODEL_LABELS = {
  automatic: 'Automatic (recommended)',
  'gemma4:26b': 'Gemma 4 · 26B',
  'qwen3.8:27b': 'Qwen 3.8 · 27B',
  'gemma4:31b': 'Gemma 4 · 31B',
  'gemma3:27b': 'Gemma 3 · 27B',
};

const JOB_STAGE_COPY = {
  queued: 'Queued for the local maker…',
  reconnecting: 'Reconnecting to the local maker…',
  'theme-proposal': 'Finding a thread in your word field…',
  'native-xfill': 'Fitting the crossings around it…',
  'clue-generation': 'Writing and checking the clues…',
  'clue-challenge': 'Giving the clue surfaces a second local pass…',
  finalizing: 'Freezing the finished board…',
  generating: 'Building your theme, grid, and clues locally…',
  filling: 'Fitting the crossings locally…',
};

const JOB_POLL_RETRY_DELAYS_MS = [100, 250, 500];

const WEEKDAY_RECIPE_COPY = {
  monday:
    'Monday aims for clear clues and approachable theme entries, with several early footholds shaped by your saved word history.',
  wednesday:
    'Wednesday aims for a satisfying middle-distance solve: varied clues, fair misdirection, and dependable crossings shaped by your saved word history.',
  thursday:
    'Thursday can reward spotting a checked shared prefix or suffix across theme entries, with layered clues on a standard letter grid shaped by your saved word history.',
  sunday:
    'Sunday gives the theme room to breathe in a 21×21 grid while keeping the clue voice around a satisfying midweek level.',
};

const PLAY_CALIBRATION_COPY = {
  'more-footholds': 'Difficulty calibration only: more footholds.',
  balanced: 'Difficulty calibration only: balanced.',
  'gentle-stretch': 'Difficulty calibration only: gentle stretch.',
};

function pendingJobStorageKey(profileId) {
  return `${PENDING_JOB_STORAGE_PREFIX}${profileId}`;
}

function validPendingJob(value, profileId) {
  return Boolean(
    value &&
      typeof value === 'object' &&
      value.profileId === profileId &&
      typeof value.jobId === 'string' &&
      value.jobId.length > 0 &&
      value.jobId.length <= 160 &&
      Number.isSafeInteger(value.seed) &&
      value.seed >= 0 &&
      value.seed <= 2_147_483_647 &&
      typeof value.weekday === 'string' &&
      WEEKDAYS.has(value.weekday),
  );
}

export function loadPendingPrivateJob(
  profileId,
  storage = globalThis.localStorage,
) {
  if (
    typeof profileId !== 'string' ||
    !profileId ||
    typeof storage?.getItem !== 'function'
  ) {
    return null;
  }
  try {
    const raw = storage.getItem(pendingJobStorageKey(profileId));
    if (!raw) return null;
    const value = JSON.parse(raw);
    return validPendingJob(value, profileId) ? value : null;
  } catch {
    return null;
  }
}

export function savePendingPrivateJob(
  profileId,
  value,
  storage = globalThis.localStorage,
) {
  if (
    !validPendingJob(value, profileId) ||
    typeof storage?.setItem !== 'function'
  ) {
    return false;
  }
  try {
    storage.setItem(pendingJobStorageKey(profileId), JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function clearPendingPrivateJob(
  profileId,
  jobId = null,
  storage = globalThis.localStorage,
) {
  if (typeof storage?.getItem !== 'function' || typeof storage?.removeItem !== 'function') {
    return false;
  }
  try {
    const current = loadPendingPrivateJob(profileId, storage);
    if (jobId && current?.jobId !== jobId) return false;
    storage.removeItem(pendingJobStorageKey(profileId));
    return true;
  } catch {
    return false;
  }
}

export function describeJobStage(stage) {
  return JOB_STAGE_COPY[stage] || JOB_STAGE_COPY.generating;
}

export function describeStageElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds < 1) return '';
  const rounded = Math.floor(seconds);
  return `${rounded} second${rounded === 1 ? '' : 's'} in this step`;
}

export function describeWeekdayRecipe(weekday) {
  return (
    WEEKDAY_RECIPE_COPY[weekday] ||
    `A fresh ${weekday || 'weekday'} crossword shaped by your saved word history.`
  );
}

export function describePlayCalibration(playCalibration) {
  const recommendation = playCalibration?.recommendation;
  return PLAY_CALIBRATION_COPY[recommendation] || '';
}

export function describeThemeThread(provenance) {
  const answers = Array.isArray(provenance?.themeAnswers)
    ? provenance.themeAnswers.filter(
        (answer) =>
          typeof answer === 'string' && /^[A-Z]{3,15}$/.test(answer),
      )
    : [];
  return answers.length > 0
    ? `Personal thread: ${answers.slice(0, 6).join(' · ')}`
    : '';
}

export function describeLanguageTokenThread(provenance) {
  const tokenHints =
    provenance?.languageLearning?.tokenHints ||
    provenance?.tokenConstruction?.hints;
  if (!Array.isArray(tokenHints) || tokenHints.length === 0) return '';
  const source = provenance?.languageLearning?.tokenHintSource;
  return source === 'reviewed-admitted'
    ? 'Language spelling: an admitted display form is active. ◇ marks the declared token; checking uses its canonical fill.'
    : 'Language spelling: an experimental local display form is active. ◇ marks the declared token; checking uses its canonical fill.';
}

export function describeLanguageRecurrence(provenance) {
  const learning = provenance?.languageLearning;
  const details = Array.isArray(learning?.dueDetails)
    ? learning.dueDetails.filter((item) => item && typeof item === 'object')
    : [];
  if (details.length === 0) return '';
  const language = typeof learning.language === 'string' && learning.language.trim()
    ? learning.language
    : 'language';
  const overdue = details.filter((item) => Number(item.overdueHours) >= 1).length;
  const stages = details
    .map((item) => item.reviewStage)
    .filter((stage) => Number.isInteger(stage) && stage > 0);
  const stageNote = stages.length > 0
    ? ` · review ${Math.max(...stages)}`
    : '';
  const overdueNote = overdue > 0 ? ` · ${overdue} overdue` : '';
  return `${details.length} ${language} recall thread${details.length === 1 ? '' : 's'} scheduled for this board${stageNote}${overdueNote}. This is recurrence, not a mastery claim.`;
}

export function describeLanguageTaskSources(provenance) {
  const learning = provenance?.languageLearning;
  const sources = Array.isArray(learning?.taskPairSources)
    ? learning.taskPairSources.filter((item) => item && typeof item === 'object')
    : [];
  if (sources.length === 0) return '';
  const language =
    typeof learning.language === 'string' && learning.language.trim()
      ? learning.language
      : 'language';
  const reviewed = sources.filter(
    (item) => item.reviewStatus === 'reviewed-admitted',
  ).length;
  const status = reviewed === sources.length ? 'admitted task pairs' : 'local task pairs';
  return `${sources.length} ${language} clue${sources.length === 1 ? '' : 's'} anchored to ${status}. This is source provenance, not a mastery claim.`;
}

export function describePersonalizationReceipt(provenance) {
  const receipt = provenance?.personalizationReceipt;
  if (
    receipt?.version !== 'private-personalization-receipt-v1' ||
    !Number.isInteger(receipt.epistemeRevision) ||
    !/^[a-f0-9]{64}$/i.test(String(receipt.epistemeDigest || ''))
  )
    return '';
  const inputs = receipt.inputs || {};
  const lanes = [];
  if (inputs.claimCount > 0) lanes.push('saved signals');
  if (inputs.associationCount > 0) lanes.push('open threads');
  if (inputs.recentExposureCount > 0) lanes.push('recent word history');
  if (inputs.languageThread) lanes.push('language thread');
  if (inputs.difficultyRecommendation) lanes.push('difficulty calibration');
  const source = lanes.length ? lanes.join(' · ') : 'your opening';
  return `Personalized from ${source} · episteme revision ${receipt.epistemeRevision}`;
}

export function personalizationReceiptFacts(provenance) {
  const receipt = provenance?.personalizationReceipt;
  if (
    receipt?.version !== 'private-personalization-receipt-v1' ||
    !Number.isInteger(receipt.epistemeRevision) ||
    !/^[a-f0-9]{64}$/i.test(String(receipt.epistemeDigest || ''))
  ) {
    return [];
  }
  const inputs = receipt.inputs || {};
  const steering = receipt.associationSteering || {};
  const recipe = provenance?.weekdayRecipe || {};
  const facts = [];
  if (Number.isInteger(inputs.claimCount) && inputs.claimCount > 0) {
    facts.push(`${inputs.claimCount} saved signal${inputs.claimCount === 1 ? '' : 's'}`);
  }
  if (Number.isInteger(inputs.associationCount) && inputs.associationCount > 0) {
    facts.push(`${inputs.associationCount} open thread${inputs.associationCount === 1 ? '' : 's'}`);
  }
  if (Number.isInteger(inputs.recentExposureCount) && inputs.recentExposureCount > 0) {
    facts.push(`${inputs.recentExposureCount} recent exposure${inputs.recentExposureCount === 1 ? '' : 's'}`);
  }
  if (inputs.languageThread) facts.push('language thread');
  if (inputs.difficultyRecommendation) facts.push('difficulty trace');
  if (Number.isInteger(recipe.themeLocksUsed) && recipe.themeLocksUsed > 0) {
    facts.push(`${recipe.themeLocksUsed} theme invitation${recipe.themeLocksUsed === 1 ? '' : 's'}`);
    if (Number.isInteger(recipe.themeEntriesUsed) && recipe.themeEntriesUsed === 0) {
      facts.push('theme released by fill quality');
    } else if (Number.isInteger(recipe.themeEntriesUsed) && recipe.themeEntriesUsed > 0) {
      facts.push(`${recipe.themeEntriesUsed} theme entr${recipe.themeEntriesUsed === 1 ? 'y' : 'ies'} anchored`);
    }
  }
  if (Number.isInteger(steering.eligibleCount) && steering.eligibleCount > 0) {
    facts.push(`${steering.eligibleCount} active association${steering.eligibleCount === 1 ? '' : 's'}`);
  }
  if (steering.diversity?.status === 'varied') facts.push('varied association paths');
  return facts;
}

export function random31BitSeed(cryptoApi = globalThis.crypto) {
  if (cryptoApi?.getRandomValues) {
    const value = new Uint32Array(1);
    cryptoApi.getRandomValues(value);
    return value[0] & 0x7fffffff;
  }
  return Math.floor(Math.random() * 0x80000000);
}

function hasProgress(app) {
  return (app.grid || []).some((row) =>
    row.some((cell) => cell !== null && cell !== ''),
  );
}

export function idempotencyKey(cryptoApi = globalThis.crypto) {
  if (typeof cryptoApi?.randomUUID === 'function') return cryptoApi.randomUUID();
  const bytes = new Uint8Array(16);
  if (typeof cryptoApi?.getRandomValues === 'function') {
    cryptoApi.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  // Flask's job contract is a canonical UUID even on local hosts where
  // randomUUID is missing (for example, an older secure-context boundary).
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function abortOperation(operation) {
  if (typeof operation?.abort === 'function') operation.abort();
  else if (typeof operation?.abort?.abort === 'function') operation.abort.abort();
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    throw new Error('The local puzzle service returned an unreadable response.');
  }
}

async function readPrivateJobWithRetry(profileId, jobId, signal, onRetry) {
  let lastError;
  for (let attempt = 0; attempt <= JOB_POLL_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const response = await fetch(
        `/api/future/private-puzzle-jobs/${jobId}?profileId=${encodeURIComponent(profileId)}`,
        { headers: { Accept: 'application/json' }, signal },
      );
      const payload = await readResponse(response);
      const retryableStatus = response.status >= 500 && response.status <= 599;
      if (!response.ok && retryableStatus && attempt < JOB_POLL_RETRY_DELAYS_MS.length) {
        onRetry?.();
        await wait(JOB_POLL_RETRY_DELAYS_MS[attempt]);
        continue;
      }
      return { response, payload };
    } catch (error) {
      if (signal?.aborted) throw error;
      lastError = error;
      if (attempt >= JOB_POLL_RETRY_DELAYS_MS.length) throw error;
      onRetry?.();
      await wait(JOB_POLL_RETRY_DELAYS_MS[attempt]);
    }
  }
  throw lastError || new Error('The local puzzle job could not be read.');
}

async function createPrivateJobWithRetry(request, signal, onRetry) {
  let lastError;
  for (let attempt = 0; attempt <= JOB_POLL_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const response = await fetch('/api/future/private-puzzle-jobs', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
      });
      if (response.status === 404 || response.status === 405) {
        return { response, payload: null };
      }
      const payload = await readResponse(response);
      const retryableStatus = response.status >= 500 && response.status <= 599;
      if (!response.ok && retryableStatus && attempt < JOB_POLL_RETRY_DELAYS_MS.length) {
        onRetry?.();
        await wait(JOB_POLL_RETRY_DELAYS_MS[attempt]);
        continue;
      }
      return { response, payload };
    } catch (error) {
      if (signal?.aborted) throw error;
      lastError = error;
      if (attempt >= JOB_POLL_RETRY_DELAYS_MS.length) throw error;
      onRetry?.();
      await wait(JOB_POLL_RETRY_DELAYS_MS[attempt]);
    }
  }
  throw lastError || new Error('A personal crossword could not be made right now.');
}

export default function PrivatePuzzleControls({
  app,
  profileId,
  profileReady,
  weekday: savedWeekday,
  onWeekdayChange,
  modelPreference = 'automatic',
  onModelPreferenceChange,
  onPuzzleRestored,
}) {
  const [requestState, setRequestState] = useState('idle');
  const [error, setError] = useState('');
  const [targetWeekday, setTargetWeekday] = useState(savedWeekday || app.selectedWeekday);
  const [modelChoice, setModelChoice] = useState(modelPreference || 'automatic');
  const [profileSaved, setProfileSaved] = useState(profileReady === true);
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const [jobStage, setJobStage] = useState('');
  const [jobStageElapsed, setJobStageElapsed] = useState(null);
  const [recentPuzzles, setRecentPuzzles] = useState([]);
  const [restoreError, setRestoreError] = useState('');
  const requestRef = useRef(null);

  useEffect(
    () => () => {
      abortOperation(requestRef.current);
    },
  []);
  useEffect(() => {
    let active = true;
    Promise.resolve(profileReady).then(
      (saved) => {
        if (active) setProfileSaved(saved === true);
      },
      () => {
        if (active) setProfileSaved(false);
      },
    );
    return () => {
      active = false;
    };
  }, [profileReady]);
  useEffect(() => {
    setTargetWeekday(savedWeekday || app.selectedWeekday);
  }, [savedWeekday, profileId, app]);
  useEffect(() => {
    setModelChoice(modelPreference || 'automatic');
  }, [modelPreference, profileId]);
  useEffect(() => {
    setRecentPuzzles(listPrivatePuzzles(profileId));
    setRestoreError('');
  }, [profileId]);

  function rememberPendingJob(jobId, seed, weekday) {
    savePendingPrivateJob(profileId, {
      profileId,
      jobId,
      seed,
      weekday,
      savedAt: new Date().toISOString(),
    });
  }

  async function applyPuzzlePayload(rawPayload, targetWeekday, seed, operation) {
    const normalizedPayload = rawPayload?.puzzle
      ? {
          ...rawPayload.puzzle,
          puzzleManifest: rawPayload.puzzleManifest,
          provenance: rawPayload.provenance,
        }
      : rawPayload;
    const puzzlePayload = normalizedPayload?.puzzle || normalizedPayload;
    let solverPuzzle;
    try {
      const languageLearning = puzzlePayload?.provenance?.languageLearning;
      const tokenConstruction = puzzlePayload?.provenance?.tokenConstruction;
      const tokenHints = languageLearning?.tokenHints || tokenConstruction?.hints;
      const tokenLanguage =
        languageLearning?.code ||
        tokenConstruction?.language ||
        puzzlePayload?.provenance?.languageInterest;
      solverPuzzle =
        Array.isArray(tokenHints) && tokenHints.length > 0 && tokenLanguage
          ? await produceFutureTokenPuzzle(puzzlePayload, {
              language: tokenLanguage,
              tokenHints,
            })
          : adaptFutureTokenPuzzle(puzzlePayload);
    } catch (cause) {
      throw new Error(
        cause instanceof Error
          ? cause.message
          : 'The local service returned an invalid token-aware puzzle.',
      );
    }
    const validPuzzle =
      solverPuzzle &&
      solverPuzzle.metadata &&
      Array.isArray(solverPuzzle.metadata.authors) &&
      solverPuzzle.provenance?.source === LOCAL_OLLAMA_SOURCE &&
      typeof app.isValidPuzzle === 'function' &&
      app.isValidPuzzle(solverPuzzle);
    if (!validPuzzle) {
      throw new Error('The local service returned a puzzle in an unsupported format.');
    }
    if (operation?.abort?.signal.aborted) return;
    if (
      hasProgress(app) &&
      !window.confirm(
        'Your crossword changed while the new one was being made. Replace it now?',
      )
    ) {
      clearPendingPrivateJob(profileId, operation?.jobId);
      setRequestState('idle');
      setJobStage('ready');
      setJobStageElapsed(null);
      return;
    }
    setStorageUnavailable(!savePrivatePuzzle(profileId, solverPuzzle));
    setRecentPuzzles(listPrivatePuzzles(profileId));
    app.selectedWeekday = targetWeekday;
    app.currentPuzzleMetadata = solverPuzzle.metadata;
    app.currentPuzzleManifest = solverPuzzle.puzzleManifest ?? null;
    app.currentPuzzleTokenManifest = solverPuzzle.tokenManifest ?? null;
    app.currentPuzzleProvenance = solverPuzzle.provenance;
    app.currentPuzzleRequestSeed = seed;
    app.crossword = solverPuzzle.entries;
    app.lastLoadedWeekday = targetWeekday;
    app.init();
    setRequestState('ready');
    setJobStage('ready');
    clearPendingPrivateJob(profileId, operation?.jobId);
  }

  async function pollDurableJob(initialPayload, operation, targetWeekday, seed) {
    let payload = initialPayload;
    operation.jobId = payload.id;
    rememberPendingJob(payload.id, seed, targetWeekday);
    setJobStage(payload.stage || payload.state);
    setJobStageElapsed(payload.stageElapsedSeconds);
    while (payload.state === 'queued' || payload.state === 'running') {
      await wait(750);
      const polled = await readPrivateJobWithRetry(
        profileId,
        payload.id,
        operation.abort.signal,
        () => setJobStage('reconnecting'),
      );
      payload = polled.payload;
      if (!polled.response.ok) {
        throw new Error(
          typeof payload?.error === 'string'
            ? payload.error
            : 'The local puzzle job could not be read.',
        );
      }
      setJobStage(payload.stage || payload.state);
      setJobStageElapsed(payload.stageElapsedSeconds);
    }
    if (payload.state === 'failed' || payload.state === 'cancelled') {
      clearPendingPrivateJob(profileId, operation.jobId);
      throw new Error(
        typeof payload.error === 'string'
          ? payload.error
          : 'The local puzzle maker stopped before it finished.',
      );
    }
    if (payload.state === 'ready') {
      await applyPuzzlePayload(payload.result, targetWeekday, seed, operation);
    }
  }

  const weekday = String(targetWeekday || '').toLowerCase();
  const locallyMade =
    app.currentPuzzleProvenance?.source === LOCAL_OLLAMA_SOURCE;
  const playCalibrationNote = describePlayCalibration(
    app.currentPuzzleProvenance?.playCalibration,
  );
  const themeThreadNote = describeThemeThread(app.currentPuzzleProvenance);
  const languageTokenNote = describeLanguageTokenThread(app.currentPuzzleProvenance);
  const languageRecurrenceNote = describeLanguageRecurrence(app.currentPuzzleProvenance);
  const languageTaskSourceNote = describeLanguageTaskSources(
    app.currentPuzzleProvenance,
  );
  const personalizationReceiptNote = describePersonalizationReceipt(
    app.currentPuzzleProvenance,
  );
  const personalizationFacts = personalizationReceiptFacts(
    app.currentPuzzleProvenance,
  );
  const canCreate =
    Boolean(profileId) && profileSaved && requestState !== 'loading';

  async function makePuzzle() {
    if (
      requestRef.current ||
      !canCreate ||
      !catalog.days.some((day) => day.id === weekday)
    )
      return;
    if (
      hasProgress(app) &&
      !window.confirm(
        'Making a new personal crossword will erase your current progress. Continue?',
      )
    ) {
      return;
    }

    const abort = new AbortController();
    const operation = { abort, jobId: null };
    requestRef.current = operation;
    setRequestState('loading');
    setJobStage('queued');
    setJobStageElapsed(null);
    setError('');
    try {
      const request = {
        profileId,
        seed: random31BitSeed(),
        weekday,
      };
      if (modelChoice !== 'automatic') request.model = modelChoice;
      const jobRequest = {
        ...request,
        idempotencyKey: idempotencyKey(),
      };
      const durable = await createPrivateJobWithRetry(
        jobRequest,
        abort.signal,
        () => setJobStage('reconnecting'),
      );
      let response = durable.response;
      let payload = durable.payload;
      // Older local hosts and the synthetic browser fixture expose the
      // synchronous compatibility route. Prefer the durable worker when it
      // exists, but keep that compatibility path so an app upgrade never
      // strands a playable private puzzle. Check the status before decoding:
      // Flask's default 404/405 response is HTML, not JSON.
      if (response.status === 404 || response.status === 405) {
        response = await fetch('/api/future/private-puzzles', {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
          signal: abort.signal,
        });
        payload = await readResponse(response);
      } else {
        payload = await readResponse(response);
      }
      if (response.ok && payload?.id && payload?.state) {
        await pollDurableJob(payload, operation, weekday, request.seed);
      }
      if (!response.ok && !payload?.metadata && !payload?.puzzle) {
        throw new Error(
          typeof payload?.error === 'string'
            ? payload.error
            : 'A personal crossword could not be made right now.',
        );
      }
      if (!(response.ok && payload?.id && payload?.state)) {
        await applyPuzzlePayload(payload, weekday, request.seed, operation);
      }
    } catch (cause) {
      if (!abort.signal.aborted) {
        setRequestState('error');
        setJobStage('failed');
        setError(
          cause instanceof Error
            ? cause.message
            : 'A personal crossword could not be made right now.',
        );
      }
    } finally {
      if (requestRef.current === operation) requestRef.current = null;
    }
  }

  useEffect(() => {
    if (!profileId || profileSaved !== true || requestRef.current) return undefined;
    const pending = loadPendingPrivateJob(profileId);
    if (!pending) return undefined;
    const operation = { abort: new AbortController(), jobId: pending.jobId };
    requestRef.current = operation;
    setRequestState('loading');
    setJobStage('queued');
    setJobStageElapsed(null);
    Promise.resolve()
      .then(async () => {
        const polled = await readPrivateJobWithRetry(
          profileId,
          pending.jobId,
          operation.abort.signal,
          () => setJobStage('reconnecting'),
        );
        const payload = polled.payload;
        if (!polled.response.ok) {
          clearPendingPrivateJob(profileId, pending.jobId);
          throw new Error(
            typeof payload?.error === 'string'
              ? payload.error
              : 'The unfinished local puzzle job could not be recovered.',
          );
        }
        await pollDurableJob(payload, operation, pending.weekday, pending.seed);
      })
      .catch((cause) => {
        if (!operation.abort.signal.aborted) {
          setRequestState('error');
          setJobStage('failed');
          setError(
            cause instanceof Error
              ? cause.message
              : 'The unfinished local puzzle job could not be recovered.',
          );
        }
      })
      .finally(() => {
        if (requestRef.current === operation) requestRef.current = null;
      });
    return () => {
      operation.abort.abort();
      if (requestRef.current === operation) requestRef.current = null;
    };
  }, [profileId, profileSaved]);

  function restoreRecentPuzzle(record) {
    if (!record || requestState === 'loading') return;
    if (
      hasProgress(app) &&
      !window.confirm(
        'Restoring another personal crossword will replace your current letters. Continue?',
      )
    ) return;
    setRestoreError('');
    let restored = false;
    try {
      restored = restorePrivatePuzzle(app, profileId, globalThis.localStorage, record);
    } catch {
      restored = false;
    }
    if (!restored) {
      setRestoreError('That saved personal crossword could not be opened.');
      return;
    }
    setTargetWeekday(record.weekday);
    onWeekdayChange?.(record.weekday);
    onPuzzleRestored?.();
  }

  async function cancelRequest() {
    const operation = requestRef.current;
    if (!operation) return;
    if (operation.jobId) {
      try {
        await fetch(`/api/future/private-puzzle-jobs/${operation.jobId}/cancel`, {
          method: 'POST',
          headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
          body: JSON.stringify({ profileId }),
        });
      } catch {
        // The local request is still aborted below; a later worker poll will
        // discard the result if the cancellation request was lost.
      }
    }
    abortOperation(operation);
    clearPendingPrivateJob(profileId, operation.jobId);
    requestRef.current = null;
    setRequestState('idle');
    setJobStage('cancelled');
    setJobStageElapsed(null);
    setError('Generation stopped; the current crossword was kept.');
  }

  return (
    <section
      className="future-private-puzzle-controls"
      aria-label="Personal crossword"
      aria-busy={requestState === 'loading'}
    >
      <div className="future-private-puzzle-copy">
        <span className="future-eyebrow">A crossword from your episteme</span>
        <p>{describeWeekdayRecipe(weekday)}</p>
      </div>
      <label className="future-private-puzzle-difficulty">
        <span>Difficulty</span>
        <select
          aria-label="Personal crossword difficulty"
          value={weekday}
          onChange={(event) => {
            const next = event.target.value;
            setTargetWeekday(next);
            onWeekdayChange?.(next);
          }}
        >
          {catalog.days.map((day) => (
            <option key={day.id} value={day.id}>
              {day.label}
            </option>
          ))}
        </select>
      </label>
      <label className="future-private-puzzle-model">
        <span>Local writing model</span>
        <select
          aria-label="Local writing model"
          value={modelChoice}
          onChange={(event) => {
            const next = event.target.value;
            setModelChoice(next);
            onModelPreferenceChange?.(next);
          }}
          disabled={requestState === 'loading'}
        >
          {LOCAL_MODEL_CHOICES.map((choice) => (
            <option key={choice} value={choice}>
              {LOCAL_MODEL_LABELS[choice] || choice}
            </option>
          ))}
        </select>
      </label>
      <p className="future-private-puzzle-note" aria-label="Local model selection note">
        Automatic follows the installed local model. A named choice is checked on this device before the board is made.
      </p>
      <button
        type="button"
        className="future-private-puzzle-button"
        onClick={makePuzzle}
        disabled={!canCreate}
      >
        <span aria-hidden="true">✳</span>
        {requestState === 'loading'
          ? 'Making your crossword…'
          : 'Make a new personal crossword'}
      </button>
      {locallyMade && (
        <span className="future-local-ollama-badge">
          <span aria-hidden="true" /> Locally made with Ollama
        </span>
      )}
      {themeThreadNote && (
        <p
          className="future-private-puzzle-note"
          role="status"
          aria-label="Personal theme thread"
        >
          {themeThreadNote}
        </p>
      )}
      {languageTokenNote && (
        <p
          className="future-private-puzzle-note"
          role="status"
          aria-label="Language display spelling"
        >
          {languageTokenNote}
        </p>
      )}
      {languageRecurrenceNote && (
        <p
          className="future-private-puzzle-note"
          role="status"
          aria-label="Language recurrence schedule"
        >
          {languageRecurrenceNote}
        </p>
      )}
      {languageTaskSourceNote && (
        <p
          className="future-private-puzzle-note"
          role="status"
          aria-label="Language task source"
        >
          {languageTaskSourceNote}
        </p>
      )}
      {playCalibrationNote && (
        <p
          className="future-private-puzzle-note"
          role="status"
          aria-label="Difficulty calibration recommendation"
        >
          {playCalibrationNote}
        </p>
      )}
      {personalizationReceiptNote && (
        <details className="future-private-puzzle-personalization">
          <summary aria-label="Personalization receipt">
            {personalizationReceiptNote}
          </summary>
          <p className="future-private-puzzle-note">
            This board used bounded profile lanes. The counts describe inputs,
            not a personality verdict, knowledge score, or mastery claim.
          </p>
          {personalizationFacts.length > 0 && (
            <ul>
              {personalizationFacts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          )}
        </details>
      )}
      {recentPuzzles.length > 1 && (
        <details className="future-private-puzzle-history">
          <summary>Recent personal crosswords ({recentPuzzles.length})</summary>
          <div className="future-private-puzzle-history-list">
            {recentPuzzles.slice(1).map((record) => (
              <button
                type="button"
                className="future-private-puzzle-history-item"
                key={record.puzzle.puzzleManifest.id || record.puzzle.puzzleManifest.integrity.value}
                onClick={() => restoreRecentPuzzle(record)}
              >
                <span>{record.puzzle.metadata.title || `Personal ${record.weekday}`}</span>
                <small>{record.weekday} · {record.puzzle.provenance?.model || 'local model'} · seed {record.seed}</small>
              </button>
            ))}
          </div>
        </details>
      )}
      {restoreError && <p className="future-private-puzzle-error" role="alert">{restoreError}</p>}
      {!profileSaved && (
        <p className="future-private-puzzle-note">
          Save your constellation before making a personal crossword.
        </p>
      )}
      {requestState === 'loading' && (
        <div className="future-private-puzzle-progress" role="status" aria-live="polite">
          <p className="future-private-puzzle-note">
            {describeJobStage(jobStage)}
          </p>
          {describeStageElapsed(jobStageElapsed) && (
            <small className="future-private-puzzle-stage-elapsed">
              {describeStageElapsed(jobStageElapsed)}
            </small>
          )}
          <button type="button" className="future-private-puzzle-cancel" onClick={cancelRequest}>
            Stop waiting
          </button>
        </div>
      )}
      {storageUnavailable && (
        <p className="future-private-puzzle-note" role="status">
          This puzzle is playable, but browser storage could not keep it for a reload.
        </p>
      )}
      {requestState === 'error' && (
        <p className="future-private-puzzle-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
