/** Types et libellés partagés par l’espace propriétaire (tableau de bord, projet, notifications). */

export interface ProjectPhase {
  id: number;
  name: string;
  status: 'COMPLETED' | 'CURRENT' | 'UPCOMING' | 'ISSUE';
  position: number;
  planned_start: string | null;
  planned_end: string | null;
  completed_at: string | null;
}

export interface Project {
  id: number;
  name: string;
  city: string;
  project_type: string;
  progress: number;
  current_phase: string;
  status: string;
  budget_total: string | null;
  budget_spent: string | null;
  phases: ProjectPhase[];
  updated_at: string;
  planned_start?: string | null;
  planned_end?: string | null;
  last_report_at?: string | null;
}

export interface ProjectExpense {
  id: number;
  project: number;
  label: string;
  category: string;
  category_label: string;
  amount: string;
  spent_at: string;
  status: 'DECLARED' | 'VALIDATED' | 'REJECTED';
  status_label: string;
  reference: string;
  notes: string;
  has_receipt: boolean;
  receipt_url: string | null;
  recorded_by_name: string | null;
  created_at: string;
}

export interface ProjectBudget {
  total: string | null;
  spent: string | null;
  remaining: string | null;
  expenses_total: string;
  justified_total: string;
  expense_count: number;
  receipt_count: number;
  currency: string;
}

export interface ProjectRequest {
  id: number;
  request_code: string;
  service_type: string;
  service_type_label: string;
  status: string;
  status_label: string;
  description: string;
  created_at: string;
  is_origin: boolean;
}

export interface ProjectDetail extends Project {
  owner_name: string;
  manager?: number | null;
  expenses: ProjectExpense[];
  service_requests: ProjectRequest[];
  budget: ProjectBudget | null;
}

export interface EvidenceSummary {
  id: number;
  project_name: string;
  phase_name: string | null;
  title: string;
  caption: string;
  location: string;
  image_url: string | null;
  thumbnail_url: string | null;
  verification_status: 'PENDING' | 'VERIFIED' | 'REJECTED';
  taken_at: string | null;
  created_at: string;
}

export const serviceLabels: Record<string, string> = {
  BUILD: 'Suivi de chantier',
  TAKEOVER: 'Suivi d’un chantier existant',
  MAINTENANCE: 'Entretien immobilier',
  OTHER: 'Autre demande',
};

export const expenseStatusTone: Record<ProjectExpense['status'], string> = {
  DECLARED: 'in_review',
  VALIDATED: 'active',
  REJECTED: 'blocked',
};

export function amount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(number)} FCFA`;
}

export function dateLabel(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function projectStatusLabel(value: string): string {
  const labels: Record<string, string> = { ACTIVE: 'En cours', PAUSED: 'En pause', COMPLETED: 'Terminé', ARCHIVED: 'Archivé' };
  return labels[value] ?? value;
}

export function serviceStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    NEW: 'Reçue', IN_REVIEW: 'En étude', CONTACTED: 'En échange', CONVERTED: 'Projet créé', CLOSED: 'Clôturée',
  };
  return labels[value] ?? value;
}

export const evidenceStatusLabels: Record<EvidenceSummary['verification_status'], string> = {
  PENDING: 'À vérifier',
  VERIFIED: 'Vérifiée',
  REJECTED: 'Refusée',
};
