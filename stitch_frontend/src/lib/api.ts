const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export const AUTH_SESSION_KEY = 'binom_auth_session';

export function saveSessionTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('refresh_token', refreshToken);
  localStorage.setItem(AUTH_SESSION_KEY, crypto.randomUUID());
}

export function clearSessionTokens(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem(AUTH_SESSION_KEY);
}

class APIError extends Error {
  status: number;
  data: unknown;
  requestId?: string;
  constructor(message: string, status: number, data: unknown, requestId?: string) {
    super(message);
    this.status = status;
    this.data = data;
    this.requestId = requestId;
  }
}

interface APIErrorPayload {
  error?: { message?: string; details?: Array<{ msg?: string }> };
  detail?: string | Array<{ msg?: string }>;
  meta?: { request_id?: string };
}

function responseRequestId(response: Response, data: APIErrorPayload | null): string | undefined {
  return response.headers.get('X-Request-ID') ?? data?.meta?.request_id;
}

function sessionId(): string | null {
  return typeof window !== 'undefined' ? localStorage.getItem(AUTH_SESSION_KEY) : null;
}

function clearSessionAndRedirect(expectedRefreshToken: string | null, expectedSessionId: string | null) {
  if (typeof window === 'undefined') return;
  // A request from an older session must not sign out a newly logged-in user.
  if (localStorage.getItem('refresh_token') !== expectedRefreshToken || sessionId() !== expectedSessionId) return;
  clearSessionTokens();
  const loginUrl = new URL('/login', window.location.origin);
  if (window.location.href !== loginUrl.href) window.location.assign(loginUrl);
}

function storedToken(key: 'access_token' | 'refresh_token'): string | null {
  return typeof window !== 'undefined' ? localStorage.getItem(key) : null;
}

function defaultErrorMessage(status: number): string {
  if (status === 401) return 'Сессия истекла. Войдите снова.';
  if (status === 403) return 'У вас нет доступа к этому действию.';
  if (status === 404) return 'Запрошенные данные не найдены.';
  if (status === 413) return 'Файл слишком большой. Выберите файл меньшего размера.';
  if (status === 422) return 'Проверьте заполненные поля.';
  if (status === 429) return 'Слишком много запросов. Подождите немного и повторите попытку.';
  if (status >= 500) return 'Сервер временно недоступен. Повторите попытку немного позже.';
  return 'Не удалось выполнить запрос. Повторите попытку.';
}

async function responseError(response: Response): Promise<APIError> {
  let data: APIErrorPayload | null = null;
  try {
    data = await response.json();
  } catch {
    // A proxy may return HTML or an empty body instead of the API error format.
  }
  const details = Array.isArray(data?.detail) ? data.detail : data?.error?.details;
  const validationMessage = details?.map((item) => item.msg).filter(Boolean).slice(0, 3).join('; ');
  const serverMessage = typeof data?.error?.message === 'string' ? data.error.message : null;
  const message = serverMessage === 'Request validation failed.'
    ? `Проверьте заполненные поля.${validationMessage ? ` ${validationMessage}` : ''}`
    : serverMessage || (typeof data?.detail === 'string' ? data.detail : null) || validationMessage || defaultErrorMessage(response.status);
  return new APIError(message, response.status, data, responseRequestId(response, data));
}

let refreshInFlight: { token: string; session: string | null; promise: Promise<string | null> } | null = null;

async function refreshAccessToken(refreshToken: string, session: string | null): Promise<string | null> {
  if (refreshInFlight?.token === refreshToken && refreshInFlight.session === session) return refreshInFlight.promise;

  const previousAccessToken = storedToken('access_token');
  const promise = (async () => {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (sessionId() !== session) return null;
    if (storedToken('refresh_token') !== refreshToken) {
      const concurrentToken = storedToken('access_token');
      return concurrentToken !== previousAccessToken ? concurrentToken : null;
    }
    if (!response.ok) {
      // Network failures, rate limits and server errors do not invalidate a session.
      if (response.status === 401 || response.status === 403) clearSessionAndRedirect(refreshToken, session);
      throw await responseError(response);
    }
    const data: { access_token?: string; refresh_token?: string } = await response.json();
    if (!data.access_token) {
      throw new APIError('Не удалось обновить сессию. Повторите попытку.', 502, null);
    }
    // Logout or a new login may have happened while the refresh was in flight.
    if (sessionId() !== session || storedToken('refresh_token') !== refreshToken) return null;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', data.access_token);
      if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    }
    return data.access_token;
  })();
  refreshInFlight = { token: refreshToken, session, promise };
  try {
    return await promise;
  } finally {
    if (refreshInFlight?.promise === promise) refreshInFlight = null;
  }
}

const PUBLIC_AUTH_ENDPOINTS = new Set(['/auth/login', '/auth/register', '/auth/forgot-password', '/auth/reset-password']);

async function authenticatedResponse(url: string, options: RequestInit = {}): Promise<{
  response: Response;
  ensureCurrentSession: () => void;
}> {
  const requiresAuth = !PUBLIC_AUTH_ENDPOINTS.has(url.split('?')[0]);
  const token = requiresAuth ? storedToken('access_token') : null;
  const session = sessionId();
  const ensureCurrentSession = () => {
    if (token && (sessionId() !== session || !storedToken('access_token'))) {
      throw new DOMException('Сессия изменилась.', 'AbortError');
    }
  };
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  let response = await fetch(`${BASE_URL}${url}`, config);
  ensureCurrentSession();

  if (response.status === 401 && token && requiresAuth) {
    options.signal?.throwIfAborted();
    const refreshToken = storedToken('refresh_token');
    const currentToken = storedToken('access_token');
    // Another request may already have refreshed this expired access token.
    const nextToken = currentToken && currentToken !== token
      ? currentToken
      : refreshToken ? await refreshAccessToken(refreshToken, session) : null;
    options.signal?.throwIfAborted();
    ensureCurrentSession();
    if (nextToken) {
      headers.set('Authorization', `Bearer ${nextToken}`);
      response = await fetch(`${BASE_URL}${url}`, config);
      ensureCurrentSession();
      if (response.status === 401 && storedToken('access_token') === nextToken) {
        clearSessionAndRedirect(storedToken('refresh_token'), session);
      }
    } else if (!refreshToken) {
      clearSessionAndRedirect(null, session);
    }
  }

  if (!response.ok) throw await responseError(response);
  return { response, ensureCurrentSession };
}

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const { response, ensureCurrentSession } = await authenticatedResponse(url, options);
  // Handle empty responses
  const text = await response.text();
  ensureCurrentSession();
  return text ? JSON.parse(text) : null;
}

export const api = {
  get: (url: string, options?: RequestInit) => fetchWithAuth(url, { ...options, method: 'GET' }),
  post: (url: string, body: unknown, options?: RequestInit) => {
    const isFormData = body instanceof FormData;
    return fetchWithAuth(url, {
      ...options,
      method: 'POST',
      body: isFormData ? body : JSON.stringify(body),
    });
  },
  put: (url: string, body: unknown, options?: RequestInit) => fetchWithAuth(url, {
    ...options,
    method: 'PUT',
    body: JSON.stringify(body),
  }),
  patch: (url: string, body: unknown, options?: RequestInit) => fetchWithAuth(url, {
    ...options,
    method: 'PATCH',
    body: JSON.stringify(body),
  }),
  delete: (url: string, options?: RequestInit) => fetchWithAuth(url, { ...options, method: 'DELETE' }),
};

/** Fetch a binary endpoint (GET or POST) and save the response as a file. */
export async function downloadFile(
  url: string,
  filename: string,
  init: { method?: string; body?: unknown } = {}
): Promise<void> {
  const { response, ensureCurrentSession } = await authenticatedResponse(url, {
    method: init.method ?? 'GET',
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  const blob = await response.blob();
  ensureCurrentSession();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);
}

/** Download a binary response as a file (e.g. exported ZIP/PDF). */
export function downloadBlob(url: string, filename: string): Promise<void> {
  return downloadFile(url, filename, { method: 'GET' });
}

/** POST a JSON body and save the binary response as a file (e.g. single-doc export). */
export function downloadBlobPost(url: string, body: unknown, filename: string): Promise<void> {
  return downloadFile(url, filename, { method: 'POST', body });
}

export interface ApiErrorShape {
  message?: string;
  status?: number;
  data?: APIErrorPayload;
}

export function asError(err: unknown): ApiErrorShape {
  return (err ?? {}) as ApiErrorShape;
}

export function errorMessage(err: unknown, fallback = 'Произошла ошибка'): string {
  if (err instanceof TypeError && /fetch|network|load failed/i.test(err.message)) {
    return 'Не удалось соединиться с сервером. Проверьте подключение к интернету и повторите попытку.';
  }
  if (err instanceof APIError) {
    const message = err.message || fallback;
    return err.status >= 500 && err.requestId
      ? `${message} Код обращения: ${err.requestId}.`
      : message;
  }
  const e = asError(err);
  const detail = e.data?.detail;
  return (typeof detail === 'string' && detail) || e.message || fallback;
}
