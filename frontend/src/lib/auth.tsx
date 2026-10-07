import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  apiRequest,
  logoutBody,
  onSessionLost,
  readStoredAccessToken,
  refreshAccessToken,
  setAccessToken as setApiAccessToken,
  setRefreshToken,
} from './api';

export type UserRole = 'CUSTOMER' | 'BTP_COMPANY' | 'FIELD_AGENT' | 'PROJECT_MANAGER' | 'ADMIN' | 'SUPER_ADMIN';

export interface KemtaUser {
  id: number;
  phone: string;
  phone_verified: boolean;
  first_name: string;
  last_name: string;
  email: string | null;
  role: UserRole;
}

interface AuthContextValue {
  user: KemtaUser | null;
  accessToken: string | null;
  isReady: boolean;
  isAuthenticated: boolean;
  establishSession: (access: string, nextUser: KemtaUser, refresh?: string | null) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<KemtaUser | null>(null);
  const [accessToken, setAccessTokenState] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);
  // Toute session établie après le démarrage (connexion, autre onglet) prime sur la restauration en cours.
  const sessionEpoch = useRef(0);

  const establishSession = useCallback((access: string, nextUser: KemtaUser, refresh: string | null = null) => {
    sessionEpoch.current += 1;
    setRefreshToken(refresh ?? null);
    setApiAccessToken(access);
    setAccessTokenState(access);
    setUser(nextUser);
    setIsReady(true);
  }, []);

  const clearSession = useCallback(() => {
    sessionEpoch.current += 1;
    setApiAccessToken(null);
    setRefreshToken(null);
    setAccessTokenState(null);
    setUser(null);
  }, []);

  useEffect(() => {
    let active = true;
    const epoch = sessionEpoch.current;

    async function restoreSession(): Promise<void> {
      const isCurrent = () => active && sessionEpoch.current === epoch;

      // 1. Jeton conservé dans l'onglet : il est validé auprès de l'API (et renouvelé si besoin).
      const stored = readStoredAccessToken();
      if (stored) {
        setApiAccessToken(stored);
        setAccessTokenState(stored);
        try {
          const currentUser = await apiRequest<KemtaUser>('/auth/me/');
          if (isCurrent()) setUser(currentUser);
          return;
        } catch {
          if (!isCurrent()) return;
          setApiAccessToken(null);
          setAccessTokenState(null);
        }
      }

      // 2. Sinon, session restaurée par le cookie HttpOnly détenu par le serveur.
      const access = await refreshAccessToken();
      if (!isCurrent()) return;
      if (access) {
        setAccessTokenState(access);
        try {
          const currentUser = await apiRequest<KemtaUser>('/auth/me/');
          if (isCurrent()) setUser(currentUser);
        } catch {
          if (isCurrent()) clearSession();
        }
      }
    }

    void restoreSession().finally(() => {
      if (active) setIsReady(true);
    });

    return () => {
      active = false;
    };
  }, [clearSession]);

  useEffect(() => onSessionLost(clearSession), [clearSession]);

  const signOut = useCallback(async () => {
    try {
      await apiRequest<{ detail: string }>('/auth/logout/', { method: 'POST', body: logoutBody() });
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    accessToken,
    isReady,
    isAuthenticated: user !== null,
    establishSession,
    signOut,
  }), [user, accessToken, isReady, establishSession, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider.');
  return context;
}
