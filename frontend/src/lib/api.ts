export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

const API_ROOT = '/api/v1';
// En-tête de repli : certains proxys d'aperçu retirent l'en-tête Authorization en transit,
// jamais les en-têtes personnalisés. Les deux portent strictement le même jeton.
const AUTH_FALLBACK_HEADER = 'X-Kemta-Auth';
const ACCESS_TOKEN_KEY = 'kemta.session.access';
const REFRESH_TOKEN_KEY = 'kemta.session.refresh';
// Identifie l'instance de page dans les journaux de l'API (diagnostic, jamais un secret).
const CLIENT_ID = Math.random().toString(36).slice(2, 10);
// Chemins qui établissent ou renouvellent eux-mêmes la session : pas de restauration préalable.
const SESSION_BOOTSTRAP_PATHS: readonly string[] = ['/auth/login/', '/auth/token/refresh/', '/auth/register/', '/auth/otp/', '/auth/password-reset/'];
let accessToken: string | null = null;
// Repli de développement : jeton de rafraîchissement pour les contextes sans cookies tiers.
let refreshToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
// Évite de redemander une session inexistante à chaque appel public.
let sessionProbe: 'unknown' | 'empty' = 'unknown';
const sessionLostListeners = new Set<() => void>();

function browserStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    // Navigation privée ou stockage partitionné indisponible : la session reste en mémoire.
    return null;
  }
}

/** Prévient l'application que la session serveur n'est plus valide (refresh impossible). */
export function onSessionLost(listener: () => void): () => void {
  sessionLostListeners.add(listener);
  return () => sessionLostListeners.delete(listener);
}

function notifySessionLost(): void {
  for (const listener of sessionLostListeners) listener();
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  if (token) sessionProbe = 'unknown';
  const storage = browserStorage();
  if (!storage) return;
  try {
    if (token) storage.setItem(ACCESS_TOKEN_KEY, token);
    else storage.removeItem(ACCESS_TOKEN_KEY);
  } catch {
    // Le quota ou la politique du navigateur peut refuser l'écriture : la mémoire suffit.
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Jeton conservé pour l'onglet courant : permet de retrouver la session après un rechargement. */
export function readStoredAccessToken(): string | null {
  const storage = browserStorage();
  if (!storage) return null;
  try {
    return storage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Retient (ou oublie) le jeton de rafraîchissement renvoyé par l'API en développement. */
export function setRefreshToken(token: string | null): void {
  refreshToken = token;
  const storage = browserStorage();
  if (!storage) return;
  try {
    if (token) storage.setItem(REFRESH_TOKEN_KEY, token);
    else storage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // Stockage indisponible : le cookie HttpOnly reste la voie normale.
  }
}

function readStoredRefreshToken(): string | null {
  if (refreshToken) return refreshToken;
  const storage = browserStorage();
  if (!storage) return null;
  try {
    refreshToken = storage.getItem(REFRESH_TOKEN_KEY);
    return refreshToken;
  } catch {
    return null;
  }
}

function storageAvailable(): boolean {
  try {
    const storage = browserStorage();
    if (!storage) return false;
    storage.setItem('kemta.probe', '1');
    storage.removeItem('kemta.probe');
    return true;
  } catch {
    return false;
  }
}

function applyAuthHeaders(headers: Headers): void {
  if (!accessToken) return;
  headers.set('Authorization', `Bearer ${accessToken}`);
  headers.set(AUTH_FALLBACK_HEADER, `Bearer ${accessToken}`);
}

/** Envoie un état technique (jamais un secret) pour diagnostiquer les sessions perdues en développement. */
function reportDiagnostic(flow: string, path: string, status: number): void {
  if (!import.meta.env.DEV) return;
  const payload = JSON.stringify({
    client: CLIENT_ID,
    path,
    status,
    hadToken: accessToken !== null,
    authHeaders: accessToken ? 'Authorization+X-Kemta-Auth' : '-',
    tokenLength: accessToken?.length ?? 0,
    storage: storageAvailable() ? 'oui' : 'non',
    inIframe: window.top !== window.self ? 'oui' : 'non',
    cookiesEnabled: navigator.cookieEnabled ? 'oui' : 'non',
    topReferrer: document.referrer || '-',
    pageUrl: window.location.href,
    visibility: document.visibilityState,
    flow,
  });
  void fetch(`${API_ROOT}/diagnostics/client/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload,
    keepalive: true,
  }).catch(() => undefined);
}

function messageFromPayload(payload: unknown): string {
  if (typeof payload === 'string') return payload;
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    const candidate = record.detail ?? record.message ?? record.non_field_errors;
    if (typeof candidate === 'string') return candidate;
    if (Array.isArray(candidate) && candidate.length > 0) return String(candidate[0]);
    const firstValue = Object.values(record).find((value) => Array.isArray(value) && value.length > 0);
    if (Array.isArray(firstValue)) return String(firstValue[0]);
  }
  return 'Une erreur est survenue. Réessayez dans un instant.';
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  const payload: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new ApiError(messageFromPayload(payload), response.status, payload);
  }
  return payload as T;
}

/**
 * Renouvelle le jeton d'accès à partir du cookie de session (HttpOnly).
 * Une réponse obsolète ne peut jamais remplacer une session plus récente :
 * si un jeton a été établi entre-temps (connexion, autre onglet), il est conservé.
 */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const tokenAtStart = accessToken;
  const bodyToken = readStoredRefreshToken();
  refreshInFlight = fetch(`${API_ROOT}/auth/token/refresh/`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bodyToken ? { refresh: bodyToken } : {}),
  })
    .then(async (response) => {
      if (!response.ok) {
        if (accessToken !== tokenAtStart) return accessToken;
        setAccessToken(null);
        if (tokenAtStart) notifySessionLost();
        return null;
      }
      const payload = (await response.json()) as { access: string; refresh?: string };
      if (payload.refresh) setRefreshToken(payload.refresh);
      // A login/logout may have completed while the cookie refresh was in flight.
      // Never let that older response replace the newer in-memory session.
      if (accessToken !== tokenAtStart) return accessToken;
      setAccessToken(payload.access);
      return payload.access;
    })
    .catch(() => {
      if (accessToken === tokenAtStart) {
        setAccessToken(null);
        if (tokenAtStart) notifySessionLost();
        return null;
      }
      return accessToken;
    })
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

async function ensureSession(isSessionBootstrap: boolean, path: string): Promise<void> {
  if (!accessToken) {
    // 1. Reprendre le jeton conservé par l'onglet (autre copie du module, instance réinitialisée).
    const stored = readStoredAccessToken();
    if (stored) {
      accessToken = stored;
      sessionProbe = 'unknown';
    }
  }

  if (!isSessionBootstrap && sessionProbe === 'empty' && !accessToken) {
    // 2. Session déjà reconnue comme inexistante : ne pas émettre une requête vouée au 401.
    reportDiagnostic('no-session', path, 401);
    throw new ApiError('Votre session a expiré. Reconnectez-vous pour continuer.', 401, null);
  }

  if (!accessToken && !isSessionBootstrap && sessionProbe === 'unknown') {
    // 3. Restauration par le cookie HttpOnly ou par le jeton conservé dans l'onglet.
    const restored = await refreshAccessToken();
    if (!restored) sessionProbe = 'empty';
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  retryAfterRefresh = true,
): Promise<T> {
  const isSessionBootstrap = SESSION_BOOTSTRAP_PATHS.some((prefix) => path.includes(prefix));
  await ensureSession(isSessionBootstrap, path);

  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('Authorization')) applyAuthHeaders(headers);
  headers.set('X-Kemta-Client', CLIENT_ID);

  let response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });

  const mayRefresh = retryAfterRefresh
    && response.status === 401
    && !path.includes('/auth/token/refresh/')
    && !path.includes('/auth/login/')
    && !path.includes('/auth/register/');

  if (mayRefresh) reportDiagnostic('401-protected', path, response.status);

  if (mayRefresh && await refreshAccessToken()) {
    const retryHeaders = new Headers(init.headers);
    if (!(init.body instanceof FormData) && init.body !== undefined && !retryHeaders.has('Content-Type')) {
      retryHeaders.set('Content-Type', 'application/json');
    }
    applyAuthHeaders(retryHeaders);
    retryHeaders.set('X-Kemta-Client', CLIENT_ID);
    response = await fetch(`${API_ROOT}${path}`, {
      ...init,
      headers: retryHeaders,
      credentials: 'include',
    });
    if (response.status === 401) {
      reportDiagnostic('401-final', path, response.status);
      setAccessToken(null);
      notifySessionLost();
    }
  }

  return parseResponse<T>(response);
}

/** Télécharge un document protégé (reçu, rapport) avec le même en-tête d'authentification. */
export async function apiBlob(path: string): Promise<Blob> {
  const isSessionBootstrap = SESSION_BOOTSTRAP_PATHS.some((prefix) => path.includes(prefix));
  await ensureSession(isSessionBootstrap, path);

  const send = async (): Promise<Response> => {
    const headers = new Headers();
    applyAuthHeaders(headers);
    headers.set('X-Kemta-Client', CLIENT_ID);
    return fetch(`${API_ROOT}${path}`, { headers, credentials: 'include' });
  };

  let response = await send();
  if (response.status === 401 && await refreshAccessToken()) {
    response = await send();
  }
  if (!response.ok) {
    throw new ApiError(
      response.status === 404
        ? 'Ce document n’est pas disponible.'
        : 'Le document n’a pas pu être téléchargé. Réessayez dans un instant.',
      response.status,
      null,
    );
  }
  return response.blob();
}

/**
 * Ouvre un document protégé dans un nouvel onglet en conservant l'authentification :
 * le fichier est récupéré avec le jeton puis présenté depuis une URL locale du navigateur.
 */
export async function openAuthenticatedFile(path: string): Promise<void> {
  const blob = await apiBlob(path);
  const objectUrl = URL.createObjectURL(blob);
  const opened = typeof window !== 'undefined' && typeof window.open === 'function'
    ? window.open(objectUrl, '_blank', 'noopener,noreferrer')
    : null;
  if (!opened) {
    // Navigateur bloqueur de fenêtres : on propose un téléchargement direct.
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = 'justificatif';
    anchor.click();
  }
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

/** Corps de déconnexion : inclut le jeton de repli s'il est utilisé. */
export function logoutBody(): string {
  const token = readStoredRefreshToken();
  return JSON.stringify(token ? { refresh: token } : {});
}
