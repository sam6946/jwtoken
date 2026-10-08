/** Composants, garde et requête partagés par les trois écrans d'onboarding. */
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, Navigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, ShieldCheck } from 'lucide-react';
import { SiteFooter } from '../../../components/SiteFooter';
import { SiteHeader } from '../../../components/SiteHeader';
import { ApiError, apiRequest } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import {
  onboardingSteps,
  type CompanyVerificationSnapshot,
  type OnboardingStepKey,
} from '../companyVerification';

export function SetupProgress({ current }: { current: OnboardingStepKey }) {
  const currentIndex = onboardingSteps.findIndex((step) => step.key === current);
  return <ol className="setup-progress" aria-label="Étapes de la vérification d’entreprise">
    {onboardingSteps.map((step, index) => {
      const state = index < currentIndex ? 'is-done' : index === currentIndex ? 'is-current' : '';
      return <li className={`setup-progress-step ${state}`} key={step.key} aria-current={index === currentIndex ? 'step' : undefined}>
        <span className="setup-progress-index">{index < currentIndex ? <Check size={14} /> : index + 1}</span>
        <span className="setup-progress-label">{step.label}</span>
      </li>;
    })}
  </ol>;
}

export function CompanySpaceGate({ children }: { children: ReactNode }) {
  const { user, isReady } = useAuth();
  if (!isReady) return <div className="app-loading"><span className="loading-mark" /><p>Chargement…</p></div>;
  if (!user) return <Navigate to="/connexion?next=%2Fentreprise%2Fverification" replace />;
  if (user.role !== 'BTP_COMPANY') {
    return <><SiteHeader /><main className="company-setup-page"><div className="page-container public-company-error"><ShieldCheck size={26} /><h1>Espace réservé aux entreprises</h1><p>Ce parcours de vérification concerne les comptes KEMTA BTP.</p><Link className="button button-primary" to="/inscription?role=BTP_COMPANY">Créer un compte entreprise <ArrowRight size={16} /></Link></div></main><SiteFooter /></>;
  }
  return <>{children}</>;
}

export interface SetupLayoutProps {
  step: OnboardingStepKey;
  kicker: string;
  title: string;
  lede: string;
  children: ReactNode;
}

export function SetupLayout({ step, kicker, title, lede, children }: SetupLayoutProps) {
  return <><SiteHeader /><main className="company-setup-page"><div className="page-container company-setup-container">
    <Link to="/dashboard" className="back-to-home"><ArrowLeft size={15} /> Retour à mon espace</Link>
    <div className="company-edit-heading"><span className="section-kicker">{kicker}</span><h1>{title}</h1><p>{lede}</p></div>
    <SetupProgress current={step} />
    {children}
  </div></main><SiteFooter /></>;
}

export function useVerificationSnapshot() {
  return useQuery({
    queryKey: ['company-verification'],
    queryFn: () => apiRequest<CompanyVerificationSnapshot>('/companies/me/verification/'),
    retry: (failureCount, caught) => !(caught instanceof ApiError && caught.status === 404) && failureCount < 2,
  });
}

export function SnapshotGate({ query, children }: {
  query: ReturnType<typeof useVerificationSnapshot>;
  children: (snapshot: CompanyVerificationSnapshot) => ReactNode;
}) {
  if (query.isLoading) return <div className="company-form-loading"><span /> Chargement du dossier…</div>;
  if (query.isError) {
    const missingProfile = query.error instanceof ApiError && query.error.status === 404;
    return <div className="form-error" role="alert">
      {missingProfile ? 'Votre profil entreprise doit d’abord être créé.' : 'Impossible de charger votre dossier de vérification.'}
      {' '}
      {missingProfile
        ? <Link to="/entreprise/profil">Compléter mon profil entreprise</Link>
        : <button type="button" onClick={() => void query.refetch()}>Réessayer</button>}
    </div>;
  }
  if (!query.data) return null;
  return <>{children(query.data)}</>;
}

export function apiMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}
