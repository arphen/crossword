import { test, expect } from './fixtures';

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
