import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, BadgeCheck, Building2, Check, CheckCircle2, CircleDashed,
  Clock3, Eye, FileUp, Info, Loader2, Lock, RefreshCw, ShieldAlert, ShieldCheck, XCircle,
} from 'lucide-react';
import { SiteFooter } from '../../components/SiteFooter';
import { SiteHeader } from '../../components/SiteHeader';
import { ApiError, apiRequest, jsonBody, openAuthenticatedFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import {
  acceptedDocumentTypes, companyTypeOptions, countryOptions, documentHints, documentStateLabels,
  documentStateTones, maxDocumentSize, onboardingSteps, verificationTones,
  type CompanyVerificationSnapshot, type OnboardingStepKey, type VerificationDocumentState,
} from './companyVerification';

/* ------------------------------------------------------------------ */
/* Briques communes du parcours (progression, garde d'accès, gabarit)  */
/* ------------------------------------------------------------------ */

function SetupProgress({ current }: { current: OnboardingStepKey }) {
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

function CompanySpaceGate({ children }: { children: ReactNode }) {
  const { user, isReady } = useAuth();
  if (!isReady) return <div className="app-loading"><span className="loading-mark" /><p>Chargement…</p></div>;
  if (!user) return <Navigate to="/connexion?next=%2Fentreprise%2Fverification" replace />;
  if (user.role !== 'BTP_COMPANY') {
    return <><SiteHeader /><main className="company-setup-page"><div className="page-container public-company-error"><ShieldCheck size={26} /><h1>Espace réservé aux entreprises</h1><p>Ce parcours de vérification concerne les comptes KEMTA BTP.</p><Link className="button button-primary" to="/inscription?role=BTP_COMPANY">Créer un compte entreprise <ArrowRight size={16} /></Link></div></main><SiteFooter /></>;
  }
  return <>{children}</>;
}

interface SetupLayoutProps {
  step: OnboardingStepKey;
  kicker: string;
  title: string;
  lede: string;
  children: ReactNode;
}

function SetupLayout({ step, kicker, title, lede, children }: SetupLayoutProps) {
  return <><SiteHeader /><main className="company-setup-page"><div className="page-container company-setup-container">
    <Link to="/dashboard" className="back-to-home"><ArrowLeft size={15} /> Retour à mon espace</Link>
    <div className="company-edit-heading"><span className="section-kicker">{kicker}</span><h1>{title}</h1><p>{lede}</p></div>
    <SetupProgress current={step} />
    {children}
  </div></main><SiteFooter /></>;
}

function useVerificationSnapshot() {
  return useQuery({
    queryKey: ['company-verification'],
    queryFn: () => apiRequest<CompanyVerificationSnapshot>('/companies/me/verification/'),
    retry: (failureCount, caught) => !(caught instanceof ApiError && caught.status === 404) && failureCount < 2,
  });
}

function SnapshotGate({ query, children }: {
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

function apiMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/* ------------------------------------------------------------------ */
/* Écran 2 — Informations sur l'entreprise                             */
/* ------------------------------------------------------------------ */

interface CompanyFormState {
  name: string;
  legal_name: string;
  company_type: string;
  sector: string;
  country: string;
  city: string;
  address: string;
  phone: string;
  email: string;
  website: string;
}

const emptyCompanyForm: CompanyFormState = {
  name: '', legal_name: '', company_type: '', sector: '', country: 'Cameroun',
  city: '', address: '', phone: '', email: '', website: '',
};

const requiredFields: Array<[keyof CompanyFormState, string]> = [
  ['name', 'Nom commercial'], ['legal_name', 'Nom légal'], ['company_type', 'Type d’entreprise'],
  ['sector', 'Secteur d’activité'], ['city', 'Ville'], ['address', 'Adresse'],
];

export function CompanyProfileSetupPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const snapshot = useVerificationSnapshot();
  const [form, setForm] = useState<CompanyFormState>(emptyCompanyForm);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const isNewProfile = snapshot.error instanceof ApiError && snapshot.error.status === 404;

  useEffect(() => {
    const profile = snapshot.data?.profile;
    if (!profile) return;
    setForm({
      name: profile.name ?? '',
      legal_name: profile.legal_name ?? '',
      company_type: profile.company_type ?? '',
      sector: profile.sector ?? '',
      country: profile.country || 'Cameroun',
      city: profile.city ?? '',
      address: profile.address ?? '',
      phone: profile.phone ?? '',
      email: profile.email ?? '',
      website: profile.website ?? '',
    });
  }, [snapshot.data]);

  const saveMutation = useMutation({
    mutationFn: (_goTo: 'documents' | 'later') => {
      const payload = { ...form, country: form.country.trim() || 'Cameroun' };
      // PATCH : enregistrement partiel, « continuer plus tard » reste possible.
      return apiRequest(`/companies/me/`, isNewProfile
        ? { method: 'PUT', body: jsonBody(payload) }
        : { method: 'PATCH', body: jsonBody(payload) });
    },
    onSuccess: async (_data, goTo) => {
      await queryClient.invalidateQueries({ queryKey: ['company-verification'] });
      await queryClient.invalidateQueries({ queryKey: ['company-profile'] });
      navigate(goTo === 'later' ? '/dashboard' : '/entreprise/documents');
    },
    onError: (caught) => setError(apiMessage(caught, 'Les informations n’ont pas pu être enregistrées.')),
  });

  function update(key: keyof CompanyFormState, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
    setNotice('');
  }

  function save(goTo: 'documents' | 'later'): void {
    setError('');
    // L'enregistrement anticipé exige au minimum le nom commercial (clé du profil).
    if (!form.name.trim()) { setError('Renseignez au moins le nom commercial de l’entreprise.'); return; }
    if (goTo === 'documents') {
      const missing = requiredFields.filter(([key]) => !String(form[key] ?? '').trim()).map(([, label]) => label);
      if (missing.length) { setError(`Complétez ces informations pour continuer : ${missing.join(', ')}.`); return; }
    }
    // Le champ `name` est obligatoire pour créer le profil : le reste peut être enregistré plus tard.
    saveMutation.mutate(goTo);
  }

  return <CompanySpaceGate><SetupLayout
    step="profile"
    kicker="KEMTA BTP · Étape 2 sur 4"
    title="Informations sur votre entreprise"
    lede="Ces informations légales restent privées. Elles servent uniquement à vérifier votre entreprise."
  >
    <SnapshotGate query={snapshot}>{(data) => <>
      {data.status === 'VERIFIED' && <p className="form-notice" role="status"><BadgeCheck size={15} /> Entreprise vérifiée : vos informations sont à jour.</p>}
      {isNewProfile && <p className="form-notice" role="status"><Info size={15} /> Aucun profil n’existe encore : le formulaire en crée un à l’enregistrement.</p>}
      {data.missing_profile_fields.length > 0 && <p className="setup-note"><Info size={15} /> Encore à compléter pour la soumission : <strong>{data.missing_profile_fields.join(', ')}</strong>.</p>}
      <form className="company-form" onSubmit={(event) => { event.preventDefault(); save('documents'); }}>
        <div className="company-form-section">
          <div className="company-form-section-title"><span>01</span><div><h2>Identité de l’entreprise</h2><p>Les informations figurant sur vos documents officiels.</p></div></div>
          <div className="form-grid form-grid-two">
            <label className="field"><span>Nom commercial <b>*</b></span><input value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="Ex. Bâtir & Rénover" maxLength={140} /></label>
            <label className="field"><span>Nom légal <b>*</b></span><input value={form.legal_name} onChange={(event) => update('legal_name', event.target.value)} placeholder="Ex. BÂTIR ET RÉNOVER SARL" maxLength={160} /></label>
            <label className="field"><span>Type d’entreprise <b>*</b></span><select value={form.company_type} onChange={(event) => update('company_type', event.target.value)}><option value="">Sélectionner…</option>{companyTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="field"><span>Secteur d’activité <b>*</b></span><input value={form.sector} onChange={(event) => update('sector', event.target.value)} placeholder="Ex. Bâtiment et travaux publics" maxLength={80} /></label>
          </div>
        </div>
        <div className="company-form-section">
          <div className="company-form-section-title"><span>02</span><div><h2>Localisation & contact</h2><p>Où intervient votre entreprise et comment vous joindre.</p></div></div>
          <div className="form-grid form-grid-two">
            <label className="field"><span>Pays</span><select value={form.country} onChange={(event) => update('country', event.target.value)}>{countryOptions.map((country) => <option key={country} value={country}>{country}</option>)}</select></label>
            <label className="field"><span>Ville <b>*</b></span><input value={form.city} onChange={(event) => update('city', event.target.value)} placeholder="Ex. Douala" maxLength={100} /></label>
            <label className="field field-full"><span>Adresse <b>*</b></span><input value={form.address} onChange={(event) => update('address', event.target.value)} placeholder="Ex. Rue Njo-Njo, Bonapriso" maxLength={200} /></label>
            <label className="field"><span>Téléphone professionnel</span><input autoComplete="tel" value={form.phone} onChange={(event) => update('phone', event.target.value)} placeholder="+237 6 XX XX XX XX" maxLength={32} /></label>
            <label className="field"><span>Email professionnel</span><input type="email" autoComplete="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder="contact@entreprise.cm" /></label>
            <label className="field field-full"><span>Site web <small>(facultatif)</small></span><input type="url" value={form.website} onChange={(event) => update('website', event.target.value)} placeholder="https://www.entreprise.cm" maxLength={300} /></label>
          </div>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="form-notice" role="status">{notice}</p>}
        <div className="company-form-actions company-setup-actions">
          <button className="button button-outline" type="button" disabled={saveMutation.isPending} onClick={() => save('later')}>{saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer et continuer plus tard'}</button>
          <button className="button button-primary" type="submit" disabled={saveMutation.isPending}>{saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer et continuer'} <ArrowRight size={16} /></button>
        </div>
        <p className="setup-legal-note"><Lock size={14} /> Vos informations légales et vos pièces justificatives ne sont jamais publiées : seule l’équipe KEMTA y a accès.</p>
      </form>
    </>}</SnapshotGate>
  </SetupLayout></CompanySpaceGate>;
}

/* ------------------------------------------------------------------ */
/* Écran 3 — Vérification de votre entreprise (documents)              */
/* ------------------------------------------------------------------ */

function DocumentRow({ document, companyName, busy, onSelect }: {
  document: VerificationDocumentState;
  companyName: string;
  busy: boolean;
  onSelect: (documentType: string, file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const added = document.state !== 'MISSING';
  const stateLabel = added ? documentStateLabels[document.state] : 'À ajouter';
  return <article className={`document-check-row ${added ? 'is-added' : ''}`}>
    <div className="document-check-main">
      <span className="document-check-icon">{added ? <CheckCircle2 size={17} /> : <CircleDashed size={17} />}</span>
      <div>
        <h3>{document.label} {document.required ? <em className="document-required">obligatoire</em> : <em className="document-optional">optionnel</em>}</h3>
        {added
          ? <p className="document-check-file"><Check size={14} /> {document.label} ajouté · <span>{document.file_name}</span></p>
          : <p className="document-check-hint">{documentHints[document.document_type] ?? 'Document justificatif.'}</p>}
        {document.state === 'REJECTED' && document.rejection_reason && <p className="document-check-reason" role="alert"><ShieldAlert size={14} /> À corriger : {document.rejection_reason}</p>}
      </div>
    </div>
    <span className={`status-badge status-${documentStateTones[document.state]}`}>{stateLabel}</span>
    <div className="document-actions">
      {document.document_id !== null && <button type="button" className="subtle-button" onClick={() => void openAuthenticatedFile(`/companies/me/documents/${document.document_id}/file/`)}><Eye size={15} /> Consulter</button>}
      <button type="button" className="button button-outline button-small" disabled={busy} onClick={() => inputRef.current?.click()}>
        {busy ? <Loader2 size={15} className="spin" /> : <FileUp size={15} />} {added ? 'Remplacer' : 'Ajouter'}
      </button>
      <input ref={inputRef} type="file" accept={acceptedDocumentTypes} className="sr-only" aria-label={`Fichier ${document.label} pour ${companyName}`} onChange={(event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (file) onSelect(document.document_type, file);
      }} />
    </div>
  </article>;
}

export function CompanyDocumentsPage() {
  const queryClient = useQueryClient();
  const snapshot = useVerificationSnapshot();
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyType, setBusyType] = useState('');
  const uploadMutation = useMutation({
    mutationFn: ({ documentType, file }: { documentType: string; file: File }) => {
      const body = new FormData();
      body.append('document_type', documentType);
      body.append('file', file);
      return apiRequest('/companies/me/documents/', { method: 'POST', body });
    },
    onMutate: ({ documentType }) => { setBusyType(documentType); setError(''); setNotice(''); },
    onSuccess: async () => {
      setNotice('Document ajouté. Il sera vérifié par l’équipe KEMTA.');
      await queryClient.invalidateQueries({ queryKey: ['company-verification'] });
    },
    onError: (caught) => setError(apiMessage(caught, 'Le document n’a pas pu être ajouté.')),
    onSettled: () => setBusyType(''),
  });

  const submitMutation = useMutation({
    mutationFn: () => apiRequest<CompanyVerificationSnapshot>('/companies/me/verification/submit/', { method: 'POST' }),
    onSuccess: async () => {
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['company-verification'] });
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (caught) => setError(apiMessage(caught, 'Le dossier n’a pas pu être envoyé.')),
  });

  function handleFile(documentType: string, file: File): void {
    if (file.size <= 0 || file.size > maxDocumentSize) { setError('Chaque document doit peser moins de 8 Mo.'); return; }
    uploadMutation.mutate({ documentType, file });
  }

  return <CompanySpaceGate><SetupLayout
    step="documents"
    kicker="KEMTA BTP · Étape 3 sur 4"
    title="Vérification de votre entreprise"
    lede="Ajoutez vos pièces justificatives. Elles restent privées et ne sont visibles que par l’équipe KEMTA."
  >
    <SnapshotGate query={snapshot}>{(data) => {
      const requiredMissing = data.missing_documents;
      const inReview = data.ready_for_review;
      return <>
        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="form-notice" role="status">{notice}</p>}
        <div className="document-checklist">
          {data.documents.map((document) => <DocumentRow key={document.document_type} document={document} companyName={data.company_name} busy={busyType === document.document_type} onSelect={handleFile} />)}
        </div>
        <div className="document-summary">
          <div>
            <span className="section-kicker">Dossier</span>
            <h2>{requiredMissing.length === 0 ? 'Toutes les pièces obligatoires sont réunies.' : `${requiredMissing.length} pièce${requiredMissing.length > 1 ? 's' : ''} obligatoire${requiredMissing.length > 1 ? 's' : ''} manquante${requiredMissing.length > 1 ? 's' : ''}`}</h2>
            {requiredMissing.length > 0 && <p>À ajouter : {requiredMissing.join(', ')}.</p>}
            {data.missing_profile_fields.length > 0 && <p><Info size={14} /> Profil à compléter : {data.missing_profile_fields.join(', ')}. <Link to="/entreprise/profil">Compléter</Link></p>}
          </div>
          {inReview
            ? <Link className="button button-primary" to="/entreprise/verification">Suivre ma vérification <ArrowRight size={16} /></Link>
            : <button className="button button-primary" type="button" disabled={!data.can_submit || submitMutation.isPending} onClick={() => submitMutation.mutate()}>
              {submitMutation.isPending ? 'Envoi du dossier…' : 'Soumettre mon dossier'} <ArrowRight size={16} />
            </button>}
        </div>
        {!inReview && !data.can_submit && <p className="setup-note"><Info size={15} /> Le bouton de soumission s’active dès que le profil et les trois pièces obligatoires sont complets.</p>}
        <p className="setup-legal-note"><Lock size={14} /> Formats acceptés : PDF, JPG, PNG et WebP, jusqu’à 8 Mo par document. Vous pouvez remplacer une pièce à tout moment.</p>
      </>;
    }}</SnapshotGate>
  </SetupLayout></CompanySpaceGate>;
}

/* ------------------------------------------------------------------ */
/* Écran 4 — Suivi de la vérification                                  */
/* ------------------------------------------------------------------ */

function StepStateIcon({ state }: { state: string }) {
  if (state === 'DONE') return <CheckCircle2 size={17} />;
  if (state === 'IN_REVIEW') return <Clock3 size={17} />;
  if (state === 'REJECTED') return <XCircle size={17} />;
  return <CircleDashed size={17} />;
}

function VerificationTimeline({ snapshot }: { snapshot: CompanyVerificationSnapshot }) {
  return <ul className="verification-timeline" aria-label="Progression de la vérification">
    {snapshot.checklist.map((step) => <li className={`verification-step is-${step.state.toLowerCase()}`} key={step.key}>
      <span className="verification-step-icon"><StepStateIcon state={step.state} /></span>
      <span className="verification-step-label">{step.label}</span>
      <span className="verification-step-state">{step.state === 'DONE' ? 'Terminé' : step.state === 'IN_REVIEW' ? 'En cours' : step.state === 'REJECTED' ? 'À corriger' : 'À venir'}</span>
    </li>)}
  </ul>;
}

export function CompanyVerificationStatusPage() {
  const queryClient = useQueryClient();
  const snapshot = useVerificationSnapshot();
  const [error, setError] = useState('');
  const submitMutation = useMutation({
    mutationFn: () => apiRequest<CompanyVerificationSnapshot>('/companies/me/verification/submit/', { method: 'POST' }),
    onSuccess: async () => {
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['company-verification'] });
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (caught) => setError(apiMessage(caught, 'Le dossier n’a pas pu être envoyé.')),
  });

  return <CompanySpaceGate><SetupLayout
    step="review"
    kicker="KEMTA BTP · Étape 4 sur 4"
    title="Suivi de votre vérification"
    lede="Vous serez notifié dès que l’équipe KEMTA rend sa décision. Aucune resaisie n’est demandée en cas de correction."
  >
    <SnapshotGate query={snapshot}>{(data) => {
      const status = data.status;
      const rejectedDocuments = data.documents.filter((document) => document.state === 'REJECTED');
      return <>
        {error && <p className="form-error" role="alert">{error}</p>}
        <section className={`verification-hero is-${status.toLowerCase()}`}>
          <span className="verification-hero-icon">
            {status === 'VERIFIED' ? <BadgeCheck size={26} /> : status === 'REJECTED' || status === 'SUSPENDED' ? <ShieldAlert size={26} /> : <Clock3 size={26} />}
          </span>
          <div>
            <span className="section-kicker">{status === 'VERIFIED' ? 'Entreprise vérifiée' : status === 'REJECTED' ? 'Vérification non validée' : status === 'SUSPENDED' ? 'Vérification suspendue' : 'Vérification en cours'}</span>
            <h2>{data.company_name}</h2>
            <p>{status === 'VERIFIED'
              ? 'Votre entreprise est vérifiée par KEMTA. Le badge est visible sur votre profil public.'
              : status === 'SUSPENDED'
                ? 'La vérification de votre entreprise est suspendue. Contactez l’équipe KEMTA pour connaître les suites.'
                : status === 'REJECTED'
                  ? 'Une correction est nécessaire sur les éléments indiqués ci-dessous, puis vous renvoyez votre dossier.'
                  : 'Votre dossier a été transmis à l’équipe KEMTA. Aucune action n’est requise de votre part pour le moment.'}</p>
          </div>
          <span className={`status-badge status-${verificationTones[status]}`}>{data.status_label}</span>
        </section>

        {status === 'REJECTED' && data.rejection_reason && <div className="verification-reason" role="alert">
          <ShieldAlert size={16} />
          <div><strong>Motif communiqué par KEMTA</strong><p>{data.rejection_reason}</p>
            {rejectedDocuments.length > 0 && <p className="verification-reason-list">Élément à corriger : <strong>{rejectedDocuments.map((document) => document.label).join(', ')}</strong>{rejectedDocuments[0]?.rejection_reason ? ` — ${rejectedDocuments[0].rejection_reason}` : ''}</p>}
            <Link className="button button-primary button-small" to="/entreprise/documents"><RefreshCw size={15} /> Corriger le document concerné</Link>
          </div>
        </div>}

        {status === 'SUSPENDED' && data.rejection_reason && <div className="verification-reason" role="alert"><ShieldAlert size={16} /><div><strong>Motif de la suspension</strong><p>{data.rejection_reason}</p></div></div>}

        <VerificationTimeline snapshot={data} />

        <section className="verification-levels">
          <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Niveau</span><h2>{data.level_label}</h2></div><span className="subtle-note">Compte → Profil → Entreprise → Renforcée</span></div>
          <div className="verification-level-grid">
            {data.levels.map((level) => <div className={`verification-level ${level.reached ? 'is-reached' : ''}`} key={level.level}>
              <span>{level.reached ? <Check size={15} /> : <CircleDashed size={15} />}</span>
              <strong>{level.label}</strong>
            </div>)}
          </div>
        </section>

        {status === 'DRAFT' && <div className="verification-next">
          {data.can_submit
            ? <><p>Votre dossier est complet : vous pouvez le transmettre à KEMTA.</p><button className="button button-primary" type="button" disabled={submitMutation.isPending} onClick={() => submitMutation.mutate()}>{submitMutation.isPending ? 'Envoi du dossier…' : 'Soumettre mon dossier'} <ArrowRight size={16} /></button></>
            : <><p>Votre dossier n’est pas encore complet.</p><Link className="button button-primary" to="/entreprise/documents">Compléter mon dossier <ArrowRight size={16} /></Link></>}
        </div>}

        <div className="verification-actions">
          <Link className="button button-outline" to="/entreprise/profil"><Building2 size={15} /> Mes informations légales</Link>
          {status !== 'DRAFT' && <Link className="button button-outline" to="/entreprise/documents"><FileUp size={15} /> Mes documents</Link>}
          <Link className="button button-outline" to="/dashboard">Retour à mon espace</Link>
        </div>
      </>;
    }}</SnapshotGate>
  </SetupLayout></CompanySpaceGate>;
}
