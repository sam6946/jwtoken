import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  BadgeCheck, Building2, Check, Eye, FileText, Info, Loader2, ShieldAlert, ShieldCheck, X,
} from 'lucide-react';
import { ApiError, apiRequest, jsonBody, openAuthenticatedFile } from '../../lib/api';
import { dateLabel } from './dashboardData';
import {
  documentStateLabels, documentStateTones, verificationTones,
  type QueueCompany, type ReviewQueueResponse,
} from '../btp/companyVerification';

type DecisionAction = 'start_review' | 'approve' | 'reject' | 'request_correction' | 'suspend';

const actionLabels: Record<DecisionAction, string> = {
  start_review: 'Démarrer l’examen',
  approve: 'Approuver',
  reject: 'Rejeter',
  request_correction: 'Demander une correction',
  suspend: 'Suspendre',
};

/** Motif exigé par l'API pour ces décisions (5 caractères minimum). */
const reasonRequired: DecisionAction[] = ['reject', 'request_correction', 'suspend'];

/**
 * Section « Entreprises à vérifier » du dashboard d'administration.
 * Elle s'appuie sur la file d'attente et les décisions déjà exposées par l'API :
 * aucun second back-office n'est créé, l'admin Django reste disponible en parallèle.
 */
export function AdminVerificationQueue() {
  const queryClient = useQueryClient();
  const [openCompanyId, setOpenCompanyId] = useState<number | null>(null);
  const [action, setAction] = useState<DecisionAction>('approve');
  const [reason, setReason] = useState('');
  const [documentType, setDocumentType] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const queueQuery = useQuery({
    queryKey: ['admin-verification-queue'],
    queryFn: () => apiRequest<ReviewQueueResponse>('/companies/verification/queue/?limit=20'),
    staleTime: 30_000,
  });

  const decisionMutation = useMutation({
    mutationFn: ({ companyId, decisionAction, decisionReason, targetDocument }: {
      companyId: number; decisionAction: DecisionAction; decisionReason: string; targetDocument: string;
    }) => apiRequest(`/companies/${companyId}/verification/`, {
      method: 'POST',
      body: jsonBody({
        action: decisionAction,
        reason: decisionReason,
        ...(targetDocument ? { document_type: targetDocument } : {}),
      }),
    }),
    onSuccess: async (_data, variables) => {
      setError('');
      setFeedback(`Décision enregistrée : ${actionLabels[variables.decisionAction].toLowerCase()}.`);
      setReason('');
      setDocumentType('');
      setOpenCompanyId(null);
      await queryClient.invalidateQueries({ queryKey: ['admin-verification-queue'] });
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (caught) => {
      setFeedback('');
      setError(caught instanceof ApiError ? caught.message : 'La décision n’a pas pu être enregistrée.');
    },
  });

  const companies = queueQuery.data?.results ?? [];
  const openCompany = companies.find((company) => company.id === openCompanyId) ?? null;

  function decide(company: QueueCompany): void {
    const trimmed = reason.trim();
    if (reasonRequired.includes(action) && trimmed.length < 5) {
      setError('Indiquez un motif d’au moins 5 caractères pour cette décision.');
      return;
    }
    if (action === 'request_correction' && !documentType) {
      setError('Précisez la pièce concernée par la correction.');
      return;
    }
    decisionMutation.mutate({ companyId: company.id, decisionAction: action, decisionReason: trimmed, targetDocument: documentType });
  }

  return <section className="dashboard-section" id="admin-verifications">
    <div className="dashboard-section-head">
      <div><span className="dashboard-eyebrow">Conformité</span><h2>Entreprises à vérifier</h2></div>
      <span className="subtle-note">{queueQuery.data ? `${queueQuery.data.count} dossier${queueQuery.data.count > 1 ? 's' : ''} en attente` : 'Chargement…'}</span>
    </div>

    {queueQuery.isLoading && <div className="company-form-loading"><span /> Chargement des dossiers…</div>}
    {queueQuery.isError && <div className="form-error" role="alert">La file de vérification n’a pas pu être chargée. <button type="button" onClick={() => void queueQuery.refetch()}>Réessayer</button></div>}
    {feedback && <p className="form-notice" role="status">{feedback}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}

    {queueQuery.data && companies.length === 0 && <div className="small-empty"><ShieldCheck size={18} /><span>Aucun dossier en attente de vérification.</span></div>}

    {companies.length > 0 && <div className="mini-table">
      {companies.map((company) => <div className="verification-queue-item" key={company.id}>
        <div className="mini-row">
          <span className="mini-row-icon"><Building2 size={16} /></span>
          <div className="mini-row-main">
            <strong>{company.name}</strong>
            <small>{company.legal_name || 'Nom légal à préciser'} · {company.city || 'Ville à préciser'} · {company.documents.length} pièce{company.documents.length > 1 ? 's' : ''} · envoyé le {dateLabel(company.verification_submitted_at)}</small>
          </div>
          <span className={`status-badge status-${verificationTones[company.verification_status]}`}>{company.status_label}</span>
          <button type="button" className="subtle-button" aria-expanded={openCompanyId === company.id} onClick={() => { setOpenCompanyId(openCompanyId === company.id ? null : company.id); setAction('approve'); setReason(''); setDocumentType(''); setError(''); setFeedback(''); }}>
            {openCompanyId === company.id ? <X size={15} /> : <Eye size={15} />} {openCompanyId === company.id ? 'Fermer' : 'Examiner'}
          </button>
        </div>

        {openCompany?.id === company.id && <div className="verification-review-panel">
          <div className="verification-review-facts">
            <div><small>Représentant légal</small><strong>{company.owner_name}</strong></div>
            <div><small>Contact</small><strong>{company.owner_phone}{company.owner_email ? ` · ${company.owner_email}` : ''}</strong></div>
            <div><small>Type & secteur</small><strong>{company.company_type || '—'} · {company.sector || '—'}</strong></div>
            <div><small>Adresse</small><strong>{company.address || '—'}, {company.city || '—'} ({company.country})</strong></div>
            <div><small>RCCM / NIU</small><strong>{company.registration_number || '—'} · {company.tax_number || '—'}</strong></div>
            <div><small>Site web</small><strong>{company.website || '—'}</strong></div>
          </div>

          <div className="verification-review-documents">
            <h3><FileText size={15} /> Pièces du dossier</h3>
            {company.documents.length === 0
              ? <p className="setup-note"><Info size={15} /> Aucune pièce n’a été déposée.</p>
              : <ul>{company.documents.map((document) => <li key={document.id}>
                <span className="verification-review-document">
                  <strong>{document.document_type_label}</strong>
                  <small>{document.file_name} · {dateLabel(document.uploaded_at)}</small>
                  {document.rejection_reason && <em><ShieldAlert size={13} /> {document.rejection_reason}</em>}
                </span>
                <span className={`status-badge status-${documentStateTones[document.status]}`}>{documentStateLabels[document.status]}</span>
                <button type="button" className="subtle-button" onClick={() => void openAuthenticatedFile(document.file_url)}><Eye size={15} /> Ouvrir</button>
              </li>)}</ul>}
            <p className="setup-legal-note"><ShieldCheck size={14} /> Documents privés : consultables uniquement par l’équipe KEMTA habilitée.</p>
          </div>

          <div className="verification-review-decision">
            <label className="field"><span>Décision</span><select value={action} onChange={(event) => { setAction(event.target.value as DecisionAction); setError(''); }}>
              {(Object.keys(actionLabels) as DecisionAction[]).map((value) => <option key={value} value={value}>{actionLabels[value]}</option>)}
            </select></label>
            {action === 'request_correction' && <label className="field"><span>Pièce à corriger</span><select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              <option value="">Sélectionner…</option>
              {company.documents.map((document) => <option key={document.id} value={document.document_type}>{document.document_type_label}</option>)}
            </select></label>}
            {reasonRequired.includes(action) && <label className="field field-full"><span>Motif <b>*</b></span><textarea rows={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Expliquez précisément ce qui est attendu. L’entreprise ne corrigera que l’élément concerné." /></label>}
            <div className="verification-review-actions">
              {action === 'approve' && <button type="button" className="button button-primary" disabled={decisionMutation.isPending} onClick={() => decide(company)}>{decisionMutation.isPending ? <Loader2 size={15} className="spin" /> : <BadgeCheck size={15} />} Valider l’entreprise</button>}
              {action === 'start_review' && <button type="button" className="button button-primary" disabled={decisionMutation.isPending} onClick={() => decide(company)}>{decisionMutation.isPending ? <Loader2 size={15} className="spin" /> : <Check size={15} />} Marquer en cours d’examen</button>}
              {action === 'reject' && <button type="button" className="button button-danger" disabled={decisionMutation.isPending} onClick={() => decide(company)}><ShieldAlert size={15} /> Rejeter le dossier</button>}
              {action === 'request_correction' && <button type="button" className="button button-danger" disabled={decisionMutation.isPending} onClick={() => decide(company)}><ShieldAlert size={15} /> Demander la correction</button>}
              {action === 'suspend' && <button type="button" className="button button-danger" disabled={decisionMutation.isPending} onClick={() => decide(company)}><ShieldAlert size={15} /> Suspendre la vérification</button>}
              <Link className="subtle-button" to={`/entreprises/${company.slug}`} target="_blank" rel="noreferrer"><Eye size={15} /> Voir la vitrine publique</Link>
            </div>
          </div>
        </div>}
      </div>)}
    </div>}

    {queueQuery.data && queueQuery.data.count > companies.length && <p className="subtle-note">Seuls les {companies.length} dossiers les plus anciens sont affichés. <Link to="/admin/companies/companyprofile/" target="_blank" rel="noreferrer">Ouvrir l’admin complet</Link>.</p>}
  </section>;
}
