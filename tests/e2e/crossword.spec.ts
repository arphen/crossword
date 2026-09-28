import { test, expect } from './fixtures';

async function readFutureSolveJournal(page) {
  return page.evaluate(async () => {
    const database = await new Promise((resolve, reject) => {
      const open = indexedDB.open('crossword');
      open.onsuccess = () => resolve(open.result);
      open.onerror = () => reject(open.error);
    });
    const rows = await new Promise((resolve, reject) => {
      const transaction = database.transaction('solve-events', 'readonly');
      const read = transaction.objectStore('solve-events').getAll();
      read.onsuccess = () => resolve(read.result);
      read.onerror = () => reject(read.error);
    });
    database.close();
    return rows.find((row) => row.kind === 'future-session-journal-v1');
  });
}

async function enterAndMakePersonalPuzzle(page) {
  const profileSaved = page.waitForResponse(response =>
    /\/api\/future\/profile\/[^/]+$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Go straight to a puzzle' }).click();
  expect((await profileSaved).status()).toBe(200);
  await expect(page.getByRole('button', { name: 'Make a new personal crossword' })).toBeEnabled();

  const sessionStarted = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/future/sessions'
      && response.request().method() === 'POST');
  const puzzleJobCreated = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/future/private-puzzle-jobs'
      && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Make a new personal crossword' }).click();
  expect((await puzzleJobCreated).status()).toBe(202);
  expect((await sessionStarted).status()).toBe(201);
  await expect(page.locator('.future-local-ollama-badge')).toBeVisible();
}

test('future calibrates five movements and persists the exact private opening journal', async ({ page, request }) => {
  const calibrationWrites: Array<Record<string, unknown>> = [];
  page.on('request', browserRequest => {
    const path = new URL(browserRequest.url()).pathname;
    if (browserRequest.method() === 'PUT' && /\/api\/future\/calibrations\/[^/]+$/.test(path)) {
      calibrationWrites.push(browserRequest.postDataJSON() as Record<string, unknown>);
    }
  });
  await page.goto('/future');
  await expect(page.locator('.future-root')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Before the words/ })).toBeVisible();
  await expect(page.locator('.future-object-grid .future-object')).toHaveCount(12);
  await expect(page.getByRole('button', { name: 'Go straight to a puzzle' })).toBeVisible();

  await page.getByRole('button', { name: 'A red thread crossing itself in a loose curve.', exact: true }).click();
  const firstMovementSaved = page.waitForResponse(response =>
    /\/api\/future\/calibrations\/[^/]+$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Continue' }).click();
  const firstSave = await firstMovementSaved;
  expect(firstSave.status()).toBe(201);
  const sessionUrl = new URL(firstSave.url());
  const createdSession = (await request.get(sessionUrl.pathname)).json();
  const firstSession = await createdSession;
  expect(firstSession.calibration).toMatchObject({
    status: 'in-progress',
    currentMovement: 2,
    observations: [{
      movement: 1,
      response: { kind: 'choose', chosenIds: ['thread-knot'] },
    }],
  });
  expect(firstSession.calibration.observations[0].offered).toHaveLength(12);
  expect(firstSession.calibration.observations[0].offered.map((item: { position: number }) => item.position)).toEqual([...Array(12).keys()]);
  await expect(page.getByRole('heading', { name: /What belongs beside it/ })).toBeVisible();

  await page.getByRole('button', { name: 'A steel tuning fork with two parallel prongs.', exact: true }).click();
  const secondMovementSaved = page.waitForResponse(response =>
    /\/api\/future\/calibrations\/[^/]+$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Continue' }).click();
  expect((await secondMovementSaved).status()).toBe(200);
  await page.getByRole('button', { name: 'Keep the original' }).click();
  const thirdMovementSaved = page.waitForResponse(response =>
    /\/api\/future\/calibrations\/[^/]+$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Continue' }).click();
  expect((await thirdMovementSaved).status()).toBe(200);
  await page.getByRole('button', { name: 'The English word echo.', exact: true }).click();
  await page.getByRole('button', { name: 'The English word moss.', exact: true }).click();
  await expect(page.getByRole('button', { name: 'The English word salt.', exact: true })).toBeDisabled();
  const fourthMovementSaved = page.waitForResponse(response =>
    /\/api\/future\/calibrations\/[^/]+$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Continue' }).click();
  expect((await fourthMovementSaved).status()).toBe(200);
  await page.getByRole('button', { name: 'Thursday', exact: true }).click();
  await page.locator('#future-learning').selectOption({ label: 'French' });
  await page.getByRole('button', { name: 'See your beginning' }).click();
  await expect(page.getByRole('heading', { name: /A beginning/ })).toBeVisible();

  const completedSave = page.waitForResponse(response =>
    /\/api\/future\/calibrations\/[^/]+$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'PUT'
      && response.request().postDataJSON().status === 'completed');
  await page.getByRole('button', { name: 'Enter crossword' }).click();
  expect((await completedSave).status()).toBe(200);
  await expect(page.locator('.future-solver')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Make a new personal crossword' })).toBeEnabled();
  await expect(page.getByLabel('Personal crossword difficulty')).toHaveValue('thursday');
  expect(calibrationWrites.at(-1)).toMatchObject({
    status: 'completed',
    setup: { weekday: 'Thursday', language: 'fr' },
  });
  expect(calibrationWrites.at(-1)?.observations).toHaveLength(4);
});

test('future carries a finished solve through a saved, revisable reflection', async ({ page, request }) => {
  const startupRequests: string[] = [];
  const dailyPuzzleRequests: string[] = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/random_crossword/')) dailyPuzzleRequests.push(path);
    if (request.method() === 'PUT' && /\/api\/future\/calibrations\/[^/]+$/.test(path)) {
      startupRequests.push('calibration-save');
    } else if (request.method() === 'PUT' && /\/api\/future\/profile\/[^/]+$/.test(path)) {
      startupRequests.push('profile-save');
    } else if (request.method() === 'POST' && path === '/api/future/sessions') {
      startupRequests.push('session-start');
    }
  });
  const futureRequests: string[] = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/api/future/private-puzzle-jobs')) futureRequests.push(path);
  });
  await page.goto('/future');
  await enterAndMakePersonalPuzzle(page);
  expect(dailyPuzzleRequests).toEqual([]);
  expect(futureRequests[0]).toBe('/api/future/private-puzzle-jobs');
  expect(futureRequests.some((path) => /\/api\/future\/private-puzzle-jobs\/[^/]+$/.test(path))).toBeTruthy();
  expect(startupRequests).toEqual(expect.arrayContaining(['calibration-save', 'profile-save', 'session-start']));
  await expect(page.locator('.future-solver #check-all')).toBeVisible();
  await expect(page.locator('.grid input')).toHaveCount(9);

  const rows = ['CAT', 'ARE', 'TEN'];
  for (let row = 0; row < rows.length; row++) {
    for (let col = 0; col < rows[row].length; col++) {
      await page.getByLabel(`grid cell ${row}-${col}`, { exact: true }).fill(rows[row][col]);
    }
  }
  await page.locator('.future-solver #check-all').click();
  await expect(page.locator('.future-reflections')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('.future-reflection-card')).toHaveCount(3);
  await expect(
    page.getByRole('button', {
      name: 'Make one more personal crossword',
      exact: true,
    }),
  ).toBeVisible();

  const firstCard = page.locator('.future-reflection-card').first();
  await firstCard.getByRole('button', { name: 'Keep this impression' }).click();
  await expect(firstCard).toContainText('Saved to this local episteme.');
  await firstCard.getByRole('button', { name: 'Undo this signal' }).click();
  await expect(firstCard).toContainText('no longer steering your profile');

  await page.reload();
  await expect(page.locator('.future-reflections')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('.future-reflection-card').first()).toContainText('no longer steering your profile');

  const profileId = await page.evaluate(() => {
    const draft = JSON.parse(localStorage.getItem('crossword.future.v1') || 'null');
    return draft?.id;
  });
  expect(profileId).toMatch(/^[0-9a-f-]{36}$/);
  const episteme = await request.get(`/api/future/profile/${profileId}/episteme`);
  expect(episteme.ok()).toBeTruthy();
  const profile = await episteme.json();
  expect(profile.profile.evidence).toEqual(expect.arrayContaining([
    expect.objectContaining({
      type: 'session-analysis',
      taskLinks: expect.arrayContaining([
        expect.objectContaining({
          tasks: expect.arrayContaining([
            expect.objectContaining({
              taskId: expect.stringMatching(/^private-answer-form:/),
              contentReview: 'unreviewed',
            }),
          ]),
        }),
      ]),
    }),
  ]));
});

test('future restores partial host-backed cells, then records checked and revealed analysis', async ({ page, request }) => {
  const eventReplies: Array<Promise<Record<string, unknown>>> = [];
  page.on('response', response => {
    const path = new URL(response.url()).pathname;
    if (response.request().method() === 'POST' && /\/api\/future\/sessions\/[^/]+\/events$/.test(path)) {
      eventReplies.push(response.json());
    }
  });

  await page.goto('/future');
  await enterAndMakePersonalPuzzle(page);
  await expect(page.locator('.future-solver .grid input')).toHaveCount(9);
  await expect(page.locator('.future-journal-status')).toHaveAttribute('data-state', 'saved');

  await page.getByLabel('grid cell 0-0', { exact: true }).fill('C');
  await page.getByLabel('grid cell 0-1', { exact: true }).fill('A');
  await expect(page.locator('.future-journal-status')).toHaveAttribute('data-state', 'saved', { timeout: 15_000 });
  const beforeReload = await readFutureSolveJournal(page);
  expect(beforeReload).toMatchObject({
    status: 'active',
    acknowledgedSeq: beforeReload.events.length,
  });
  expect(beforeReload.sessionId).toMatch(/^[0-9a-f-]{36}$/);
  expect(beforeReload.puzzleHash).toMatch(/^[a-f0-9]{64}$/);
  expect(beforeReload.events.filter(event => event.type === 'cell-written').map(event => event.afterToken)).toEqual(expect.arrayContaining(['C', 'A']));

  // Re-creating an identical session is idempotent and proves that its frozen
  // puzzle manifest and session identity are already registered on the host.
  const hostSession = await request.post('/api/future/sessions', {
    data: {
      sessionId: beforeReload.sessionId,
      profileId: beforeReload.profileId,
      puzzleHash: beforeReload.puzzleHash,
      initialGrid: beforeReload.initialGrid,
      writerToken: beforeReload.writerToken,
    },
  });
  expect(hostSession.status()).toBe(200);
  expect(await hostSession.json()).toMatchObject({
    sessionId: beforeReload.sessionId,
    acceptedSeq: beforeReload.acknowledgedSeq,
    status: 'active',
    cellCount: 9,
  });

  await page.reload();
  await expect(page.locator('.future-solver .grid input')).toHaveCount(9);
  await expect(page.getByLabel('grid cell 0-0', { exact: true })).toHaveValue('C');
  await expect(page.getByLabel('grid cell 0-1', { exact: true })).toHaveValue('A');
  await expect(page.locator('.future-journal-status')).toHaveAttribute('data-state', 'saved', { timeout: 15_000 });
  const afterReload = await readFutureSolveJournal(page);
  expect(afterReload.sessionId).toBe(beforeReload.sessionId);
  expect(afterReload.initialGrid).toEqual(beforeReload.initialGrid);
  expect(afterReload.events.some(event => event.type === 'session-resumed' && event.reason === 'reload')).toBe(true);
  expect(afterReload.acknowledgedSeq).toBe(afterReload.events.length);

  const checkResponse = page.waitForResponse(response =>
    /\/api\/future\/sessions\/[^/]+\/events$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'POST');
  await page.locator('.future-solver #check-all').click();
  expect((await checkResponse).status()).toBe(200);
  await expect(page.locator('.future-journal-status')).toHaveAttribute('data-state', 'saved', { timeout: 15_000 });

  const revealConfirmation = page.waitForEvent('dialog').then(async dialog => {
    const type = dialog.type();
    await dialog.accept();
    return type;
  });
  await page.locator('.future-solver #reveal-all').click();
  expect(await revealConfirmation).toBe('confirm');
  await expect(page.locator('.future-journal-status')).toHaveAttribute('data-state', 'finished', { timeout: 15_000 });

  const finishedJournal = await readFutureSolveJournal(page);
  expect(finishedJournal.status).toBe('finished');
  expect(finishedJournal.acknowledgedSeq).toBe(finishedJournal.events.length);
  expect(finishedJournal.events.map(event => event.seq)).toEqual(finishedJournal.events.map((_, index) => index + 1));
  expect(finishedJournal.events.some(event => event.type === 'check-result-shown')).toBe(true);
  expect(finishedJournal.events.some(event => event.type === 'answer-revealed' && event.scope === 'puzzle')).toBe(true);
  expect(finishedJournal.events.at(-1)).toMatchObject({ type: 'session-finished', reason: 'complete' });

  // Replay the exact immutable prefix. The host must recognize every event as
  // a duplicate with the same payload digest and retain the finished status.
  const eventReplay = await request.post(`/api/future/sessions/${finishedJournal.sessionId}/events`, {
    data: {
      expectedSeq: 0,
      writerToken: finishedJournal.writerToken,
      events: finishedJournal.events,
    },
  });
  expect(eventReplay.status()).toBe(200);
  const replayPayload = await eventReplay.json();
  expect(replayPayload.status).toBe('finished');
  expect(replayPayload.acceptedSeq).toBe(finishedJournal.events.length);
  expect(replayPayload.duplicateEventIds).toHaveLength(finishedJournal.events.length);
  expect(replayPayload.acceptedEventIds).toEqual([]);

  const epistemeResponse = await request.get(`/api/future/profile/${finishedJournal.profileId}/episteme`);
  expect(epistemeResponse.status()).toBe(200);
  const episteme = await epistemeResponse.json();
  const analysisEvidence = episteme.profile.evidence.find(item =>
    item.type === 'session-analysis' && item.evidenceId === `session-analysis:${finishedJournal.sessionId}:v1`);
  expect(analysisEvidence.analysis).toMatchObject({
    analysisVersion: 'knowledge-reducer-v1',
    sessionId: finishedJournal.sessionId,
    puzzleHash: finishedJournal.puzzleHash,
  });
  expect(analysisEvidence.analysis.observations).toHaveLength(6);
  expect(analysisEvidence.analysis.observations.every(item => item.finalState === 'correct' && item.revealedCellIds.length > 0)).toBe(true);
  expect(eventReplies.length).toBeGreaterThan(0);
  expect(await eventReplies.at(-1)).toMatchObject({ status: 'finished', acceptedSeq: finishedJournal.events.length });
});

test('desktop keyboard, clue highlighting, checks and completion persist through the real API', async ({ page, request }) => {
  await page.goto('/');
  await expect(page.locator('#react-root #app')).toBeVisible();
  await expect(page.getByLabel('grid cell 0-0', { exact: true })).toBeVisible();
  await expect(page.locator('.grid input')).toHaveCount(9);
  await expect(page.locator('.puzzle-authors')).toHaveText('CI fixture author');
  await expect(page.locator('#across li')).toHaveCount(3);
  await expect(page.locator('#down li')).toHaveCount(3);

  await page.locator('#across .clue-text').first().click();
  await expect(page.locator('#across li').first()).toHaveClass(/highlighted-clue/);
  const first = page.getByLabel('grid cell 0-0', { exact: true });
  await expect(first).toBeFocused();
  await page.keyboard.type('x');
  await expect(first).toHaveValue('X');
  await expect(page.getByLabel('grid cell 0-1', { exact: true })).toBeFocused();
  await page.locator('#check-all').click();
  await expect(first).toHaveClass(/red/);
  await expect(page.locator('.stat-item').filter({ has: page.getByText('Checks', { exact: true }) }).locator('.stat-value')).toHaveText('1');

  // Correct the mistake through the keyboard, then fill the original square.
  await first.click();
  await page.keyboard.type('c');
  await expect(first).toHaveValue('C');
  await expect(first).not.toHaveClass(/red/);
  const rows = ['CAT', 'ARE', 'TEN'];
  for (let row = 0; row < rows.length; row++) {
    for (let col = 0; col < rows[row].length; col++) {
      await page.getByLabel(`grid cell ${row}-${col}`, { exact: true }).fill(rows[row][col]);
    }
  }
  const saved = page.waitForResponse(response => response.url().endsWith('/api/completed_puzzles') && response.request().method() === 'POST');
  await page.locator('#check-all').click();
  expect((await saved).status()).toBe(201);
  await expect(page.locator('.stat-item').first().locator('.stat-value')).toHaveText('6 / 6');
  const completion = await request.get('/api/completed_puzzles/240101');
  expect(await completion.json()).toMatchObject({ completed: true, data: {
    puzzle_date: '240101', title: 'Synthetic CI word square', authors: ['CI fixture author'], weekday: 'monday',
  } });

  // Clear browser storage so the overview must come from the backend database.
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByLabel('grid cell 0-0', { exact: true })).toHaveValue('');
  await page.locator('#overview-button').click();
  await expect(page.getByRole('heading', { name: 'Solved Puzzles' })).toBeVisible();
  await expect(page.locator('.modal-content')).toContainText('Synthetic CI word square');
  await expect(page.locator('.modal-content')).toContainText('CI fixture author');
});

test('nested mobile routes mount React and join the existing room', async ({ page, request }) => {
  const created = await request.post('/api/multiplayer/create', { data: { date: '240101' } });
  expect(created.ok()).toBeTruthy();
  const { room_id } = await created.json();
  for (const role of ['across', 'down']) {
    await page.goto(`/mobile/${room_id}/${role}`);
    await expect(page.locator('#react-root .clue-item')).toHaveCount(3);
    await expect(page).toHaveTitle('Crossword Mobile');
    await page.reload();
    await expect(page.locator('#react-root .clue-item')).toHaveCount(3);
  }
});

test('completion API validates, deduplicates, persists and deletes through Flask', async ({ request, playwright, baseURL }) => {
  const invalid = await request.post('/api/completed_puzzles', { data: {} });
  expect(invalid.status()).toBe(400);
  expect(await invalid.json()).toEqual({ error: 'puzzle_date is required' });
  const payload = { puzzle_date: '240209', title: 'Original API fixture', authors: ['CI author'], weekday: 'friday', time_taken: 17, score: 90 };
  const created = await request.post('/api/completed_puzzles', { data: payload });
  expect(created.status()).toBe(201);
  const record = (await created.json()).data;
  expect(record).toMatchObject(payload);

  // A completely separate HTTP client proves persistence is server-side.
  const second = await playwright.request.newContext({ baseURL });
  try {
    expect(await (await second.get('/api/completed_puzzles/240209')).json()).toEqual({ completed: true, data: record });
    const duplicate = await second.post('/api/completed_puzzles', { data: { ...payload, score: 1 } });
    expect(duplicate.status()).toBe(200);
    expect((await duplicate.json()).data).toEqual(record);
    expect(await (await second.get('/api/completed_puzzles')).json()).toEqual([record]);
    expect((await second.delete('/api/completed_puzzles/240209')).status()).toBe(200);
    expect(await (await request.get('/api/completed_puzzles/240209')).json()).toEqual({ completed: false });
    expect((await second.delete('/api/completed_puzzles/240209')).status()).toBe(404);
  } finally {
    await second.dispose();
  }
});
