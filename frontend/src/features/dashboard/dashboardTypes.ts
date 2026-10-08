/** Contrats de l'API dashboard et petits libellés partagés par ses vues. */
import type { KemtaUser, UserRole } from '../../lib/auth';
import { dateLabel, type EvidenceSummary, type Project } from './dashboardData';

export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'DONE' | 'BLOCKED';
export interface DashboardTask {
  id: number;
  project: number;
  project_name: string;
  phase_name: string | null;
  assigned_to_name: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  due_date: string | null;
}
export interface RequestSummary {
  id: number;
  request_code: string;
  service_type: string;
  service_type_label?: string;
  status: string;
  city: string;
  owner_name: string;
  related_project?: number | null;
  related_project_name?: string | null;
  created_at: string;
}
export interface OpportunitySummary {
  id: number;
  title: string;
  project_type: string;
  city: string;
  status: string;
  budget_min: string | null;
  budget_max: string | null;
  deadline: string;
  description: string;
}
export interface CompanySummary {
  id: number;
  name: string;
  slug: string;
  verified: boolean;
  is_published: boolean;
  city: string;
  description: string;
  services: string[];
  years_experience: number;
  profile_completion: number;
  portfolio_count: number;
  views_count: number;
  created_at: string;
}
export interface CompanyApplication {
  id: number;
  opportunity: number;
  opportunity_title: string;
  message: string;
  status: string;
  status_label: string;
  estimated_budget: string | null;
  duration_days: number | null;
  created_at: string;
}
export interface ActivityEntry {
  id: number;
  event: string;
  description: string;
  created_at: string;
}
export interface DashboardStats {
  clients?: number;
  companies?: number;
  service_requests?: number;
  all_service_requests?: number;
  projects?: number;
  active_projects?: number;
  tasks?: number;
  pending_tasks?: number;
  overdue_tasks?: number;
  evidences?: number;
  evidences_pending?: number;
  expenses?: number;
  receipts?: number;
  unread_notifications?: number;
  budget_total?: string;
  budget_spent?: string;
  revenue?: string;
  subscriptions?: number;
  active_subscriptions?: number;
  opportunities?: number;
  all_opportunities?: number;
  applications?: number;
  open_opportunities?: number;
  profile_completion?: number;
  portfolio_count?: number;
  views_count?: number;
}
export interface DashboardResponse {
  user: KemtaUser;
  role: UserRole;
  is_demo: boolean;
  statistics: DashboardStats;
  projects: Project[];
  tasks: DashboardTask[];
  evidences: EvidenceSummary[];
  service_requests: RequestSummary[];
  company: CompanySummary | null;
  companies: CompanySummary[];
  opportunities: OpportunitySummary[];
  applications: CompanyApplication[];
  recent_activity: ActivityEntry[];
  notifications: Array<{ id: number; title: string; created_at: string; is_read: boolean }>;
}

export const taskStatusLabels: Record<TaskStatus, string> = {
  TODO: 'À faire',
  IN_PROGRESS: 'En cours',
  DONE: 'Terminée',
  BLOCKED: 'Bloquée',
};

export function deadlineLabel(value: string): string {
  const days = Math.round((new Date(value).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return `Échéance dépassée (${dateLabel(value)})`;
  if (days === 0) return 'À faire aujourd’hui';
  if (days === 1) return 'À faire demain';
  return `Dans ${days} jours`;
}
