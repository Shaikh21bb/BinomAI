import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, test } from 'node:test';
import ts from 'typescript';

// Compile the real client with the installed compiler; no extra test runtime is needed.
const { outputText } = ts.transpileModule(readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { api, AUTH_SESSION_KEY, downloadFile, errorMessage, saveSessionTokens } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const originalStorage = globalThis.localStorage;
const originalDocument = globalThis.document;
let redirects;

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  const values = new Map([['access_token', 'expired-access'], ['refresh_token', 'old-refresh'], [AUTH_SESSION_KEY, 'old-session']]);
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
  redirects = [];
  globalThis.window = { location: { origin: 'https://binom.example', href: 'https://binom.example/dashboard', assign: (url) => redirects.push(String(url)) } };
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalWindow === undefined) delete globalThis.window;
  else globalThis.window = originalWindow;
  if (originalStorage === undefined) delete globalThis.localStorage;
  else globalThis.localStorage = originalStorage;
  if (originalDocument === undefined) delete globalThis.document;
  else globalThis.document = originalDocument;
});

test('parallel expired requests share one refresh and persist the rotated refresh token', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  let refreshes = 0;
  let retries = 0;
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      assert.equal(JSON.parse(init.body).refresh_token, 'old-refresh');
      refreshStarted.resolve();
      await releaseRefresh.promise;
      return json({ access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    if (new Headers(init.headers).get('Authorization') === 'Bearer expired-access') return json({}, 401);
    retries += 1;
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer new-access');
    return json({ ok: true });
  };
  const requests = [api.get('/projects/'), api.get('/auth/me'), api.get('/quick-check/reports')];
  await refreshStarted.promise;
  releaseRefresh.resolve();
  assert.deepEqual(await Promise.all(requests), [{ ok: true }, { ok: true }, { ok: true }]);
  assert.equal(refreshes, 1);
  assert.equal(retries, 3);
  assert.equal(localStorage.getItem('refresh_token'), 'new-refresh');
  assert.deepEqual(redirects, []);
});

test('a late 401 reuses the access token already refreshed by another request', async () => {
  const releaseLate = deferred();
  let refreshes = 0;
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      return json({ access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    if (new Headers(init.headers).get('Authorization') === 'Bearer expired-access') {
      if (url.endsWith('/slow')) await releaseLate.promise;
      return json({}, 401);
    }
    return json({ ok: true });
  };
  const late = api.get('/slow');
  await api.get('/fast');
  releaseLate.resolve();
  await late;
  assert.equal(refreshes, 1);
});

test('a token refreshed in another tab retries within the same session', async () => {
  const requestStarted = deferred();
  const releaseRequest = deferred();
  let requests = 0;
  globalThis.fetch = async (url, init) => {
    requests += 1;
    if (new Headers(init.headers).get('Authorization') === 'Bearer expired-access') {
      requestStarted.resolve();
      await releaseRequest.promise;
      return json({}, 401);
    }
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer other-tab-access');
    return json({ ok: true });
  };
  const result = api.get('/projects/');
  await requestStarted.promise;
  // Rotation updates tokens, but unlike login it preserves AUTH_SESSION_KEY.
  localStorage.setItem('access_token', 'other-tab-access');
  localStorage.setItem('refresh_token', 'other-tab-refresh');
  releaseRequest.resolve();
  assert.deepEqual(await result, { ok: true });
  assert.equal(requests, 2);
  assert.deepEqual(redirects, []);
});

test('a rejected refresh can use tokens already rotated in another tab', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshStarted.resolve();
      await releaseRefresh.promise;
      return json({}, 401);
    }
    return new Headers(init.headers).get('Authorization') === 'Bearer expired-access'
      ? json({}, 401) : json({ ok: true });
  };
  const result = api.get('/projects/');
  await refreshStarted.promise;
  localStorage.setItem('access_token', 'other-tab-access');
  localStorage.setItem('refresh_token', 'other-tab-refresh');
  releaseRefresh.resolve();
  assert.deepEqual(await result, { ok: true });
  assert.equal(localStorage.getItem('access_token'), 'other-tab-access');
  assert.deepEqual(redirects, []);
});

for (const kind of ['network', '503', '429']) {
  test(`a temporary ${kind} refresh failure preserves the session`, async () => {
    globalThis.fetch = async (url) => {
      if (!url.endsWith('/auth/refresh')) return json({}, 401);
      if (kind === 'network') throw new TypeError('Failed to fetch');
      return new Response('<html>unavailable</html>', { status: Number(kind) });
    };
    await assert.rejects(api.get('/projects/'), (error) => {
      assert.ok(errorMessage(error).length > 0);
      assert.doesNotMatch(errorMessage(error), /localhost|An error occurred/);
      return true;
    });
    assert.equal(localStorage.getItem('access_token'), 'expired-access');
    assert.equal(localStorage.getItem('refresh_token'), 'old-refresh');
    assert.deepEqual(redirects, []);
  });
}

test('an invalid refresh token clears the session and redirects to login', async () => {
  globalThis.fetch = async (url) => json({ detail: url.endsWith('/auth/refresh') ? 'Недействительный refresh токен' : 'expired' }, 401);
  await assert.rejects(api.get('/projects/'));
  assert.equal(localStorage.getItem('access_token'), null);
  assert.equal(localStorage.getItem('refresh_token'), null);
  assert.deepEqual(redirects, ['https://binom.example/login']);
});

test('a failed login reports the original error without refreshing an old session', async () => {
  let requests = 0;
  globalThis.fetch = async (url, init) => {
    requests += 1;
    assert.ok(url.endsWith('/auth/login'));
    assert.equal(new Headers(init.headers).get('Authorization'), null);
    return json({ error: { message: 'Неверный email или пароль' } }, 401);
  };
  await assert.rejects(api.post('/auth/login', { email: 'test@example.com', password: 'invalid' }), { message: 'Неверный email или пароль' });
  assert.equal(requests, 1);
  assert.equal(localStorage.getItem('access_token'), 'expired-access');
  assert.deepEqual(redirects, []);
});

test('a refresh completing after logout cannot restore the session', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  let requests = 0;
  globalThis.fetch = async (url) => {
    requests += 1;
    if (!url.endsWith('/auth/refresh')) return json({}, 401);
    refreshStarted.resolve();
    await releaseRefresh.promise;
    return json({ access_token: 'new-access', refresh_token: 'new-refresh' });
  };
  const result = assert.rejects(api.get('/projects/'));
  await refreshStarted.promise;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  releaseRefresh.resolve();
  await result;
  assert.equal(requests, 2);
  assert.equal(localStorage.getItem('access_token'), null);
  assert.equal(localStorage.getItem('refresh_token'), null);
});

test('a rejected refresh from the previous session cannot sign out a new login', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  globalThis.fetch = async (url) => {
    if (!url.endsWith('/auth/refresh')) return json({}, 401);
    refreshStarted.resolve();
    await releaseRefresh.promise;
    return json({}, 401);
  };
  const result = assert.rejects(api.get('/projects/'));
  await refreshStarted.promise;
  saveSessionTokens('other-access', 'other-refresh');
  releaseRefresh.resolve();
  await result;
  assert.equal(localStorage.getItem('access_token'), 'other-access');
  assert.deepEqual(redirects, []);
});

test('a successful refresh from the previous session cannot retry under a new login', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  let requests = 0;
  globalThis.fetch = async (url) => {
    requests += 1;
    if (!url.endsWith('/auth/refresh')) return json({}, 401);
    refreshStarted.resolve();
    await releaseRefresh.promise;
    return json({ access_token: 'new-access', refresh_token: 'new-refresh' });
  };
  const result = assert.rejects(api.post('/projects/', { name: 'Old session project' }));
  await refreshStarted.promise;
  saveSessionTokens('other-access', 'other-refresh');
  releaseRefresh.resolve();
  await result;
  assert.equal(requests, 2);
  assert.equal(localStorage.getItem('access_token'), 'other-access');
  assert.equal(localStorage.getItem('refresh_token'), 'other-refresh');
  assert.deepEqual(redirects, []);
});

test('a late 401 cannot replay a mutation under a different login', async () => {
  const requestStarted = deferred();
  const releaseRequest = deferred();
  let requests = 0;
  globalThis.fetch = async () => {
    requests += 1;
    requestStarted.resolve();
    await releaseRequest.promise;
    return json({}, 401);
  };
  const result = assert.rejects(api.post('/projects/', { name: 'Old session project' }));
  await requestStarted.promise;
  saveSessionTokens('other-access', 'other-refresh');
  releaseRequest.resolve();
  await result;
  assert.equal(requests, 1);
  assert.equal(localStorage.getItem('access_token'), 'other-access');
  assert.deepEqual(redirects, []);
});

test('a successful response from the previous session is discarded after a new login', async () => {
  const requestStarted = deferred();
  const releaseRequest = deferred();
  globalThis.fetch = async () => {
    requestStarted.resolve();
    await releaseRequest.promise;
    return json({ company: 'Previous company' });
  };
  const result = assert.rejects(api.get('/projects/'), { name: 'AbortError' });
  await requestStarted.promise;
  saveSessionTokens('other-access', 'other-refresh');
  releaseRequest.resolve();
  await result;
  assert.deepEqual(redirects, []);
});

test('an export finishing after logout does not start a download', async () => {
  const requestStarted = deferred();
  const releaseRequest = deferred();
  let clicked = false;
  globalThis.document = {
    createElement: () => ({ click: () => { clicked = true; } }),
    body: { appendChild() {}, removeChild() {} },
  };
  globalThis.fetch = async () => {
    requestStarted.resolve();
    await releaseRequest.promise;
    return new Response(new Blob(['Private company report']));
  };
  const result = assert.rejects(downloadFile('/projects/1/export', 'report.pdf'), { name: 'AbortError' });
  await requestStarted.promise;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem(AUTH_SESSION_KEY);
  releaseRequest.resolve();
  await result;
  assert.equal(clicked, false);
});

test('logout during export body streaming prevents the download', async () => {
  const bodyReadStarted = deferred();
  const releaseBody = deferred();
  let clicked = false;
  globalThis.document = {
    createElement: () => ({ click: () => { clicked = true; } }),
    body: { appendChild() {}, removeChild() {} },
  };
  globalThis.fetch = async () => new Response(new ReadableStream({
    async pull(controller) {
      bodyReadStarted.resolve();
      await releaseBody.promise;
      controller.enqueue(new TextEncoder().encode('Private company report'));
      controller.close();
    },
  }, { highWaterMark: 0 }));
  const result = assert.rejects(downloadFile('/projects/1/export', 'report.pdf'), { name: 'AbortError' });
  await bodyReadStarted.promise;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem(AUTH_SESSION_KEY);
  releaseBody.resolve();
  await result;
  assert.equal(clicked, false);
});

test('aborting a request while refresh is pending prevents the retry', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  const controller = new AbortController();
  let requests = 0;
  globalThis.fetch = async (url) => {
    requests += 1;
    if (!url.endsWith('/auth/refresh')) return json({}, 401);
    refreshStarted.resolve();
    await releaseRefresh.promise;
    return json({ access_token: 'new-access', refresh_token: 'new-refresh' });
  };
  const result = assert.rejects(api.get('/projects/', { signal: controller.signal }), { name: 'AbortError' });
  await refreshStarted.promise;
  controller.abort();
  releaseRefresh.resolve();
  await result;
  assert.equal(requests, 2);
  assert.deepEqual(redirects, []);
});

test('binary exports refresh an expired session and download the retried response', async () => {
  let refreshes = 0;
  let clicked = false;
  const anchor = { click: () => { clicked = true; } };
  globalThis.document = { createElement: () => anchor, body: { appendChild() {}, removeChild() {} } };
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes += 1;
      return json({ access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    if (new Headers(init.headers).get('Authorization') === 'Bearer expired-access') return json({}, 401);
    assert.equal(init.method, 'POST');
    assert.deepEqual(JSON.parse(init.body), { format: 'pdf' });
    return new Response(new Blob(['report']));
  };
  await downloadFile('/projects/1/export', 'report.pdf', { method: 'POST', body: { format: 'pdf' } });
  assert.equal(refreshes, 1);
  assert.equal(clicked, true);
  assert.equal(anchor.download, 'report.pdf');
});

test('validation details and server request IDs remain visible in errors', async () => {
  globalThis.fetch = async () => json({ error: { message: 'Request validation failed.', details: [{ msg: 'Некорректный email' }] } }, 422);
  await assert.rejects(api.post('/auth/login', {}), (error) => {
    assert.match(errorMessage(error), /Проверьте заполненные поля.*Некорректный email/);
    return true;
  });
  globalThis.fetch = async () => new Response('', { status: 503, headers: { 'X-Request-ID': 'trace-123' } });
  await assert.rejects(api.get('/projects/'), (error) => {
    assert.match(errorMessage(error), /Код обращения: trace-123/);
    return true;
  });
});
