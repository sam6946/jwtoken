/** Étape 4 : état, décisions et actions de suivi du dossier entreprise. */
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  Building2,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileUp,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import { apiRequest } from '../../../lib/api';
import {
  type CompanyVerificationSnapshot,
  verificationTones,
} from '../companyVerification';
import {
  apiMessage,
  CompanySpaceGate,
  SetupLayout,
  SnapshotGate,
  useVerificationSnapshot,
} from './shared';

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
