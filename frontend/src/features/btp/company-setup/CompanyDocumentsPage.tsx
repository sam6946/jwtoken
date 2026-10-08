/** Étape 3 : dépôt, remplacement et soumission des pièces justificatives. */
import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  CheckCircle2,
  CircleDashed,
  Eye,
  FileUp,
  Info,
  Loader2,
  Lock,
  ShieldAlert,
} from 'lucide-react';
import { apiRequest, openAuthenticatedFile } from '../../../lib/api';
import {
  acceptedDocumentTypes,
  documentHints,
  documentStateLabels,
  documentStateTones,
  maxDocumentSize,
  type CompanyVerificationSnapshot,
  type VerificationDocumentState,
} from '../companyVerification';
import {
  apiMessage,
  CompanySpaceGate,
  SetupLayout,
  SnapshotGate,
  useVerificationSnapshot,
} from './shared';

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
