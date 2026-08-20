const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class APIError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  
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

  if (response.status === 401 && token) {
    // Try to refresh token
    const refreshToken = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
    if (refreshToken) {
      try {
        const refreshResponse = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        
        if (refreshResponse.ok) {
          const data = await refreshResponse.json();
          if (typeof window !== 'undefined') {
            localStorage.setItem('access_token', data.access_token);
            if (data.refresh_token) {
              localStorage.setItem('refresh_token', data.refresh_token);
            }
          }
          
          // Retry original request
          headers.set('Authorization', `Bearer ${data.access_token}`);
          config.headers = headers;
          response = await fetch(`${BASE_URL}${url}`, config);
        } else {
          // Refresh failed
          if (typeof window !== 'undefined') {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
          }
        }
      } catch {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    } else {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }
    }
  }

  if (!response.ok) {
    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    const message =
      (typeof data?.error?.message === 'string' ? data.error.message : null) ??
      data?.detail ??
      'An error occurred';
    throw new APIError(message, response.status, data);
  }

  // Handle empty responses
  const text = await response.text();
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
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body !== undefined) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${BASE_URL}${url}`, {
    method: init.method ?? 'GET',
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  if (!response.ok) {
    let data: { error?: { message?: string }; detail?: unknown } | null = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    const message =
      (typeof data?.error?.message === 'string' ? data.error.message : null) ??
      (typeof data?.detail === 'string' ? data.detail : null) ??
      'Ошибка скачивания';
    throw new APIError(message, response.status, data);
  }

  const blob = await response.blob();
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
  data?: { detail?: string | Array<{ msg?: string }> };
}

export function asError(err: unknown): ApiErrorShape {
  return (err ?? {}) as ApiErrorShape;
}

export function errorMessage(err: unknown, fallback = 'Произошла ошибка'): string {
  if (err instanceof TypeError && err.message === 'Failed to fetch') {
    return 'Не удалось соединиться с сервером. Проверьте, что backend запущен (http://localhost:8000), и обновите страницу.';
  }
  if (err instanceof APIError) return err.message || fallback;
  const e = asError(err);
  const detail = e.data?.detail;
  return (typeof detail === 'string' && detail) || e.message || fallback;
}
