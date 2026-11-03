import {test, expect} from '@playwright/test';
import {randomUUID} from 'node:crypto';

test('sample workflow, trace, evidence, export, and saved replay', async ({page}) => {
  const errors: string[] = [], agentRequests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {if (request.url().includes('/api/copilotkit') && request.method() === 'POST') agentRequests.push(request.url());});
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'Try a sample'})).toBeEnabled();
  await page.getByRole('button', {name: 'Try a sample'}).click();
  await expect(page).toHaveURL(/\?run=/);
  await expect(page.getByRole('status').filter({hasText: 'Search complete'})).toBeVisible();
  await expect(page.getByRole('tab', {name: 'Matches 4', exact: true})).toBeVisible();
  await expect(page.getByRole('tab', {name: 'Needs review 1', exact: true})).toBeVisible();
  await expect(page.locator('.trace-panel')).toHaveCount(0);
  await expect(page.getByRole('link', {name: /^Apply for/})).toHaveCount(0);
  await page.getByRole('button', {name: /^Activity/}).click();
  await expect(page.getByText('Fictional sample · no API calls', {exact: true})).toBeVisible();
  await expect(page.locator('.trace-stage')).toHaveCount(6);
  if (process.env.PROOF_TEST_TRANSPORT === 'sse') {
    expect(agentRequests).toHaveLength(0);
    await expect(page.locator('.trace-footer')).toContainText('Native SSE');
  } else expect(agentRequests.length).toBeGreaterThan(0);
  await page.getByRole('button', {name: 'Inspect evidence', exact: true}).first().click();
  await expect(page.getByText('Built Python integrations', {exact: true})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Inspect evidence', exact: true}).first()).toBeFocused();
  await page.getByRole('button', {name: 'Inspect evidence', exact: true}).first().click();
  await page.getByRole('button', {name: 'Follow this opening in the activity trace'}).click();
  const openCall = page.locator('.trace-call[open]').filter({hasText: 'Northstar Data'});
  await expect(openCall).toHaveCount(1);
  await expect(openCall.getByText('Supporting quotations and explicit requirements passed the local checks.')).toBeVisible();
  await page.getByRole('tab', {name: 'Needs review 1', exact: true}).click();
  await expect(page.getByText('Latticework AI', {exact: true})).toBeVisible();
  await expect(page.locator('.review-reason')).toContainText('Needs confirmation');
  const exportPath = await page.getByRole('link', {name: 'Export', exact: true}).getAttribute('href');
  const exported = await page.request.get(exportPath!);
  expect(await exported.text()).toContain('Résumé quote:');
  expect(await exported.text()).toContain('Needs review');
  const tracePath = await page.getByRole('link', {name: 'Download recorded trace'}).getAttribute('href');
  const trace = await (await page.request.get(tracePath!)).json();
  expect(trace.events.some((event: {type: string}) => event.type === 'research_completed')).toBe(true);
  await page.reload();
  await expect(page.getByRole('tab', {name: 'Matches 4', exact: true})).toBeVisible();
  await page.getByRole('button', {name: /^Activity/}).click();
  await expect(page.locator('.trace-stage')).toHaveCount(6);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.getByRole('button', {name: 'New search', exact: true}).click();
  await expect(page.getByLabel('What are you looking for?', {exact: false})).toHaveValue('');
  await expect(page.getByLabel('Saved résumé', {exact: true})).toHaveValue('');
  await expect(page.locator('.trace-panel')).toHaveCount(0);
  await page.reload();
  await expect(page).not.toHaveURL(/\?run=/);
  await expect(page.locator('.job-card')).toHaveCount(0);
});

test('trace reconnect reuses a saved search and deduplicates its events', async ({page}) => {
  test.skip(process.env.PROOF_TEST_TRANSPORT === 'sse', 'CopilotKit-specific interruption; native EventSource reconnect is separate.');
  const sample = await (await page.request.post('/api/backend/demo')).json();
  let observers = 0, creations = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/backend\/(searches|demo)$/.test(request.url())) creations++;
  });
  await page.route('**/api/copilotkit/agent/proof/run', route => ++observers === 1 ? route.abort('connectionreset') : route.continue());
  await page.goto('/?run=' + sample.id);
  await expect(page.getByRole('alert').filter({hasText: 'The connection was interrupted.'})).toBeVisible();
  await page.getByRole('button', {name: /^Activity/}).click();
  await expect(page.locator('.trace-stage')).toHaveCount(6, {timeout: 15000});
  await expect(page.getByRole('alert').filter({hasText: 'The connection was interrupted.'})).toHaveCount(0);
  expect(observers).toBeGreaterThan(1);
  expect(creations).toBe(0);
  const recorded = await (await page.request.get(`/api/backend/searches/${sample.id}/trace`)).json();
  await expect(page.locator('.trace-event-count')).toHaveText(String(recorded.events.length));
});

test('upload errors are actionable and do not create a run', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Upload résumé', {exact: true}).setInputFiles({name: 'bad.txt', mimeType: 'text/plain', buffer: Buffer.from('short')});
  await expect(page.getByRole('alert').filter({hasText: /résumé|resume|text/i})).toBeVisible();
  await expect(page).not.toHaveURL(/\?run=/);
  await expect(page.getByRole('button', {name: 'Try a sample'})).toBeEnabled();
});

test('Apply uses the captured application link and supports older saved roles', async ({page}) => {
  test.skip(!process.env.PROOF_TEST_DB, 'Requires an isolated test database.');
  const {DatabaseSync} = await import('node:sqlite');
  const sample = await (await page.request.post('/api/backend/demo')).json();
  await expect.poll(async () => (await (await page.request.get(`/api/backend/searches/${sample.id}`)).json()).status).toBe('complete');
  const run = await (await page.request.get(`/api/backend/searches/${sample.id}`)).json();
  const db = new DatabaseSync(process.env.PROOF_TEST_DB!);
  expect(db.prepare('SELECT id FROM runs WHERE id=?').get(sample.id)).toBeTruthy();
  const id = randomUUID().replaceAll('-', '');
  const result = {...run.result, mode: 'live'};
  result.jobs[0].application_url = 'https://careers.example.com/jobs/123/apply?source=listing#application';
  result.jobs[0].application_link_source = 'listing_link';
  delete result.jobs[1].application_url;
  delete result.jobs[1].application_link_source;
  try {
    db.prepare('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)').run(id, run.created, run.resume_id, 'Application link fixture', 5, 'complete', JSON.stringify(result), null);
    await page.goto('/?run=' + id);
    const apply = page.getByRole('link', {name: 'Apply for ' + result.jobs[0].title + ' at ' + result.jobs[0].company, exact: true});
    await expect(apply).toHaveAttribute('href', result.jobs[0].application_url);
    await expect(apply).toHaveAttribute('target', '_blank');
    await expect(apply).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(page.getByRole('link', {name: 'Apply for ' + result.jobs[1].title + ' at ' + result.jobs[1].company, exact: true})).toHaveAttribute('href', result.jobs[1].url);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  } finally {db.close();}
});

test('incremental results retain open evidence and a failed run stays failed', async ({page}) => {
  test.skip(!process.env.PROOF_TEST_DB, 'Set PROOF_TEST_DB to the isolated test server database, never a personal database.');
  const {DatabaseSync} = await import('node:sqlite');
  const sample = await (await page.request.post('/api/backend/demo')).json();
  await expect.poll(async () => (await (await page.request.get(`/api/backend/searches/${sample.id}`)).json()).status).toBe('complete');
  const trace = await (await page.request.get(`/api/backend/searches/${sample.id}/trace`)).json();
  const db = new DatabaseSync(process.env.PROOF_TEST_DB!);
  // Refuse a mismatched fixture path: the HTTP sample must exist in this database.
  expect(db.prepare('SELECT id FROM runs WHERE id=?').get(sample.id)).toBeTruthy();
  const id = randomUUID().replaceAll('-', '');
  const boundary = trace.events.findIndex((event: {type: string}) => event.type === 'job_matched');
  const firstJob = trace.events[boundary].data.job;
  const emit = (events: unknown[]) => {for (const event of events) {
    const {seq, ...payload} = event as Record<string, unknown>;
    db.prepare('INSERT INTO events(run_id,payload) VALUES(?,?)').run(id, JSON.stringify(payload));
  }};
  try {
    db.prepare('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)').run(id, trace.run.created, trace.run.resume_id, trace.run.query, trace.run.count, 'running', null, null);
    await page.goto('/?run=' + id);
    await expect(page.getByRole('button', {name: 'Stop', exact: true})).toBeVisible();
    await expect(page.locator('.trace-panel')).toHaveCount(0);
    await expect(page.getByRole('tablist')).toHaveCount(0);
    const searching = trace.events.findIndex((event: {type: string; step: string}) => event.type === 'tool_started' && event.step === 'search') + 1;
    emit(trace.events.slice(0, searching));
    await page.getByRole('button', {name: /^Activity/}).click();
    await expect(page.locator('.trace-stage')).toHaveCount(2);
    await expect(page.locator('.trace-metrics')).toHaveCount(0);
    await expect(page.locator('.job-card')).toHaveCount(0);
    emit(trace.events.slice(searching, boundary + 1));
    const card = page.locator(`[data-job-id="${firstJob.id}"]`);
    await card.getByRole('button', {name: 'Inspect evidence', exact: true}).click();
    await expect(card.locator('.job-evidence')).toBeVisible();
    await expect(page.getByRole('status').filter({hasText: 'Search complete'})).toHaveCount(0);
    emit(trace.events.slice(boundary + 1));
    db.prepare('UPDATE runs SET status=?,result=? WHERE id=?').run('complete', JSON.stringify(trace.run.result), id);
    await expect(page.getByRole('tab', {name: 'Matches 4', exact: true})).toBeVisible();
    await expect(page.getByRole('status').filter({hasText: 'Search complete'})).toBeVisible();
    await expect(card.locator('.job-evidence')).toBeVisible();
    const failedId = randomUUID().replaceAll('-', '');
    db.prepare('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)').run(failedId, trace.run.created, trace.run.resume_id, 'Failure fixture', 5, 'failed', null, 'Fixture: provider could not return a result.');
    await page.goto('/?run=' + failedId);
    await expect(page.getByRole('status').filter({hasText: 'Search stopped'})).toBeVisible();
    await page.getByRole('button', {name: /^Activity/}).click();
    await expect(page.getByText('No activity was recorded for this search.', {exact: true})).toBeVisible();
    await expect(page.getByRole('alert').filter({hasText: 'Fixture: provider could not return a result.'})).toBeVisible();
    await expect(page.getByRole('status').filter({hasText: 'Search complete'})).toHaveCount(0);
  } finally {db.close();}
});
