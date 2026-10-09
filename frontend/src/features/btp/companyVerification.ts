/**
 * Types et libellés partagés du parcours de vérification des entreprises.
 * Le dossier est entièrement piloté par l'API (`/api/v1/companies/...`) :
 * aucun état métier n'est dupliqué côté navigateur.
 */

export type VerificationStatus = 'DRAFT' | 'PENDING' | 'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED';
export type VerificationStepState = 'DONE' | 'PENDING' | 'IN_REVIEW' | 'REJECTED';
export type DocumentState = 'MISSING' | 'PENDING' | 'APPROVED' | 'REJECTED';

export interface VerificationStep {
  key: 'ACCOUNT' | 'PHONE' | 'PROFILE' | 'DOCUMENTS' | 'REVIEW';
  label: string;
  state: VerificationStepState;
}

export interface VerificationDocumentState {
  document_type: string;
  label: string;
  required: boolean;
  state: DocumentState;
  document_id: number | null;
  file_name: string;
  uploaded_at: string | null;
  rejection_reason: string;
}

export interface VerificationLevel {
  level: string;
  label: string;
  reached: boolean;
}

export interface CompanyOwnerProfile {
  id: number;
  name: string;
  slug: string;
  description: string;
  city: string;
  services: string[];
  intervention_areas: string[];
  years_experience: number;
  verified: boolean;
  is_published: boolean;
  profile_completion: number;
  legal_name: string;
  company_type: string;
  sector: string;
  country: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  registration_number: string;
  tax_number: string;
  verification_status: VerificationStatus;
  verification_status_label: string;
  verification_level: string;
  verification_level_label: string;
  advanced_verified: boolean;
  verification_submitted_at: string | null;
  verification_reviewed_at: string | null;
  verification_rejection_reason: string;
  documents_count: number;
}

export interface CompanyVerificationSnapshot {
  company_id: number;
  company_name: string;
  status: VerificationStatus;
  status_label: string;
  level: string;
  level_label: string;
  verified: boolean;
  is_published: boolean;
  advanced_verified: boolean;
  submitted_at: string | null;
  reviewed_at: string | null;
  rejection_reason: string;
  can_submit: boolean;
  ready_for_review: boolean;
  missing_profile_fields: string[];
  missing_documents: string[];
  checklist: VerificationStep[];
  documents: VerificationDocumentState[];
  levels: VerificationLevel[];
  profile: CompanyOwnerProfile;
}

export interface CompanyDocumentUploadResponse {
  id: number;
  document_type: string;
  document_type_label: string;
  status: DocumentState;
  status_label: string;
  file_name: string;
  file_url: string;
  rejection_reason: string;
  uploaded_at: string;
}

export interface QueueCompany extends CompanyOwnerProfile {
  status_label: string;
  level_label: string;
  owner_name: string;
  owner_phone: string;
  owner_email: string | null;
  documents: Array<{
    id: number;
    document_type: string;
    document_type_label: string;
    status: DocumentState;
    status_label: string;
    file_name: string;
    file_url: string;
    rejection_reason: string;
    uploaded_at: string;
  }>;
}

export interface ReviewQueueResponse {
  count: number;
  results: QueueCompany[];
}

/** « 1 Compte · 2 Profil · 3 Documents · 4 Vérification » */
export const onboardingSteps = [
  { key: 'account', label: 'Compte' },
  { key: 'profile', label: 'Profil' },
  { key: 'documents', label: 'Documents' },
  { key: 'review', label: 'Vérification' },
] as const;

export type OnboardingStepKey = (typeof onboardingSteps)[number]['key'];

export const companyTypeOptions = [
  { value: 'SARL', label: 'SARL' },
  { value: 'SA', label: 'SA' },
  { value: 'SAS', label: 'SAS' },
  { value: 'ETS', label: 'Établissement' },
  { value: 'EI', label: 'Entreprise individuelle' },
  { value: 'GIE', label: 'GIE' },
  { value: 'COOPERATIVE', label: 'Coopérative' },
  { value: 'AUTRE', label: 'Autre' },
];

export const countryOptions = [
  'Cameroun', 'Gabon', 'Congo', 'Tchad', 'République centrafricaine',
  'Guinée équatoriale', 'Nigéria', 'Côte d’Ivoire', 'Sénégal', 'Autre',
];

/** Documents attendus par le dossier, dans l'ordre du parcours. */
export const documentHints: Record<string, string> = {
  RCCM: 'Registre du commerce et du crédit mobilier, en cours de validité.',
  NIU: 'Numéro d’identifiant unique délivré par l’administration fiscale.',
  REGISTRATION_CERTIFICATE: 'Attestation ou certificat d’immatriculation de l’entreprise.',
  IDENTITY_DOCUMENT: 'CNI, passeport ou carte de séjour du représentant légal.',
  ADDRESS_PROOF: 'Facture d’électricité, quittance ou attestation de domiciliation.',
};

export const documentStateLabels: Record<DocumentState, string> = {
  MISSING: 'À ajouter',
  PENDING: 'À vérifier',
  APPROVED: 'Validé',
  REJECTED: 'À corriger',
};

export const documentStateTones: Record<DocumentState, string> = {
  MISSING: 'in_review',
  PENDING: 'in_review',
  APPROVED: 'active',
  REJECTED: 'blocked',
};

export const verificationTones: Record<VerificationStatus, string> = {
  DRAFT: 'in_review',
  PENDING: 'in_review',
  UNDER_REVIEW: 'in_review',
  VERIFIED: 'active',
  REJECTED: 'blocked',
  SUSPENDED: 'blocked',
};

export const maxDocumentSize = 8 * 1024 * 1024;
export const acceptedDocumentTypes = '.pdf,.jpg,.jpeg,.png,.webp';

export function formatFileSize(size: number): string {
  if (!Number.isFinite(size) || size <= 0) return '';
  if (size < 1024) return `${size} o`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} Ko`;
  return `${(size / (1024 * 1024)).toFixed(1)} Mo`;
}
