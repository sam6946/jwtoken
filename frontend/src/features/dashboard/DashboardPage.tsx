import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import {
  ArrowRight, BadgeCheck, Bell, BriefcaseBusiness, Building2, CalendarDays, Camera, Check,
  CheckCircle2, ChevronRight, CircleAlert, ClipboardList, FileText, HardHat, House, Info,
  ListChecks, MapPin, Plus, Receipt, ShieldCheck, Wallet,
} from 'lucide-react';
import { ApiError, apiRequest, jsonBody } from '../../lib/api';
import { useAuth, type KemtaUser, type UserRole } from '../../lib/auth';
import { DashboardShell } from './DashboardShell';
import {
  amount, dateLabel, projectStatusLabel, serviceLabels, serviceStatusLabel,
  evidenceStatusLabels, type EvidenceSummary, type Project,
} from './dashboardData';

type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'DONE' | 'BLOCKED';
interface DashboardTask {
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
interface RequestSummary {
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
interface OpportunitySummary {
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
interface CompanySummary {
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
interface CompanyApplication {
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
interface ActivityEntry {
  id: number;
  event: string;
  description: string;
  created_at: string;
}
interface DashboardStats {
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
interface DashboardResponse {
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

const taskStatusLabels: Record<TaskStatus, string> = {
  TODO: 'À faire',
  IN_PROGRESS: 'En cours',
  DONE: 'Terminée',
  BLOCKED: 'Bloquée',
};

function deadlineLabel(value: string): string {
  const days = Math.round((new Date(value).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return `Échéance dépassée (${dateLabel(value)})`;
  if (days === 0) return 'À faire aujourd’hui';
  if (days === 1) return 'À faire demain';
  return `Dans ${days} jours`;
}

export function DashboardPage() {
  const { user, isReady, signOut, sessionLost } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [busyTaskId, setBusyTaskId] = useState<number | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const dashboardQuery = useQuery({
    queryKey: ['dashboard', user?.id],
    // Le jeton est appliqué par le client API lui-même : une seule source de vérité.
    queryFn: () => apiRequest<DashboardResponse>('/dashboard/'),
    enabled: Boolean(user && isReady),
    staleTime: 60_000,
    retry: 1,
  });
  const sessionExpired = dashboardQuery.error instanceof ApiError && dashboardQuery.error.status === 401;

  async function updateTaskStatus(taskId: number, status: TaskStatus): Promise<void> {
    setBusyTaskId(taskId);
    setTaskError(null);
    try {
      await apiRequest(`/project-tasks/${taskId}/`, { method: 'PATCH', body: jsonBody({ status }) });
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    } catch (error) {
      setTaskError(error instanceof ApiError ? error.message : 'La mise à jour de la tâche a échoué. Réessayez.');
    } finally {
      setBusyTaskId(null);
    }
  }

  if (!isReady) return <div className="app-loading"><span className="loading-mark" /><p>Préparation de votre espace…</p></div>;
  if (!user) {
    // Session perdue en cours de route : on l'explique au lieu de renvoyer sans un mot.
    return <Navigate to={sessionLost ? '/connexion?session=expiree&next=%2Fdashboard' : '/connexion?next=%2Fdashboard'} replace />;
  }

  const response = dashboardQuery.data;
  const isAdmin = user.role === 'ADMIN' || user.role === 'SUPER_ADMIN';
  const isBtp = user.role === 'BTP_COMPANY';
  const isManager = user.role === 'PROJECT_MANAGER';
  const isFieldAgent = user.role === 'FIELD_AGENT';
  const isClient = !isAdmin && !isBtp && !isManager && !isFieldAgent;
  const title = isAdmin ? 'Administration' : isBtp ? 'Espace KEMTA BTP' : isManager ? 'Pilotage de chantiers' : isFieldAgent ? 'Espace terrain' : 'Espace propriétaire';
  const displayName = user.first_name || 'vous';
  const unreadCount = response?.statistics.unread_notifications ?? response?.notifications.filter((item) => !item.is_read).length ?? 0;

  async function handleSignOut(): Promise<void> {
    await signOut();
    navigate('/');
  }

  return (
    <DashboardShell user={user} breadcrumb={title} active="overview" onSignOut={() => void handleSignOut()} unreadNotifications={unreadCount}>
      <div className="dashboard-page-heading">
        <div>
          <span className="dashboard-eyebrow">{new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
          <h1>Bonjour, {displayName} <span>👋</span></h1>
          <p>{isClient ? 'Voici vos projets suivis par KEMTA, leurs dépenses et vos demandes.' : 'Voici l’état de vos projets et de vos activités KEMTA.'}</p>
        </div>
        {isClient && <Link className="button button-primary" to="/demande"><Plus size={17} /> Nouvelle demande</Link>}
      </div>

      {dashboardQuery.isLoading && <DashboardSkeleton />}
      {dashboardQuery.isError && (sessionExpired
        ? <div className="dashboard-error"><CircleAlert size={22} /><div><strong>Votre session a expiré.</strong><p>Reconnectez-vous pour retrouver votre espace : aucune donnée n’a été perdue.</p><button className="button button-primary button-small" onClick={() => void handleSignOut()}>Se reconnecter</button></div></div>
        : <div className="dashboard-error"><CircleAlert size={22} /><div><strong>Votre espace ne peut pas être chargé.</strong><p>{dashboardQuery.error instanceof ApiError ? dashboardQuery.error.message : 'Vérifiez votre connexion puis réessayez.'}</p><button className="button button-outline button-small" onClick={() => void dashboardQuery.refetch()}>Réessayer</button></div></div>)}
      {response?.is_demo && <div className="demo-banner"><Info size={17} /><span><strong>Environnement de démonstration.</strong> Les comptes, projets, entreprises et candidatures affichés ici sont fictifs et servent uniquement à présenter la plateforme. Aucune donnée réelle n’est utilisée.</span></div>}
      {taskError && <div className="dashboard-alert"><CircleAlert size={17} /><span>{taskError}</span></div>}
      {response && (isAdmin
        ? <AdminDashboard data={response} />
        : isBtp
          ? <BtpDashboard data={response} />
          : isManager
            ? <ManagerDashboard data={response} busyTaskId={busyTaskId} onTaskStatus={updateTaskStatus} />
            : isFieldAgent
              ? <FieldAgentDashboard data={response} busyTaskId={busyTaskId} onTaskStatus={updateTaskStatus} />
              : <ClientDashboard data={response} />)}
    </DashboardShell>
  );
}

function ClientDashboard({ data }: { data: DashboardResponse }) {
  const stats = data.statistics;
  const projectCount = stats.projects ?? data.projects.length;
  const unread = stats.unread_notifications ?? data.notifications.filter((item) => !item.is_read).length;
  const activeProjects = data.projects.filter((project) => project.status === 'ACTIVE').length;
  const completedProjects = data.projects.filter((project) => project.status === 'COMPLETED').length;
  return <>
    <div className="kpi-row">
      <Link className="kpi-card" to="/dashboard#client-projets">
        <span className="kpi-head"><span className="kpi-icon stat-blue"><HardHat size={16} /></span><span className="kpi-label">Projets suivis par KEMTA</span></span>
        <strong className="kpi-value">{projectCount}</strong>
        <span className="kpi-foot"><House size={13} /> {activeProjects} en cours · {completedProjects} terminé{completedProjects === 1 ? '' : 's'}</span>
      </Link>
      <div className="kpi-card">
        <span className="kpi-head"><span className="kpi-icon stat-green"><FileText size={16} /></span><span className="kpi-label">Demandes envoyées</span></span>
        <strong className="kpi-value">{stats.service_requests ?? data.service_requests.length}</strong>
        <span className="kpi-foot"><FileText size={13} /> {data.service_requests[0] ? `Dernière : ${data.service_requests[0].request_code}` : 'Aucune demande pour l’instant'}</span>
      </div>
      <div className="kpi-card">
        <span className="kpi-head"><span className="kpi-icon stat-sand"><Receipt size={16} /></span><span className="kpi-label">Reçus disponibles</span></span>
        <strong className="kpi-value">{stats.receipts ?? 0}</strong>
        <span className="kpi-foot"><Receipt size={13} /> sur {stats.expenses ?? 0} dépense{(stats.expenses ?? 0) === 1 ? '' : 's'} enregistrée{(stats.expenses ?? 0) === 1 ? '' : 's'}</span>
      </div>
      <Link className="kpi-card" to="/dashboard/notifications">
        <span className="kpi-head"><span className="kpi-icon stat-blue"><Bell size={16} /></span><span className="kpi-label">Notifications non lues</span></span>
        <strong className="kpi-value">{unread}</strong>
        <span className="kpi-foot"><Bell size={13} /> Journal des alertes de vos chantiers</span>
      </Link>
    </div>

    {stats.budget_total && Number(stats.budget_total) > 0 && <div className="budget-strip">
      <span className="budget-strip-icon"><Wallet size={18} /></span>
      <span><small>Budget total suivi</small><strong>{amount(stats.budget_total)}</strong></span>
      <span><small>Dépenses engagées</small><strong>{amount(stats.budget_spent)}</strong></span>
      <span className="budget-strip-note"><Info size={13} /> Chaque projet détaille ses dépenses et ses justificatifs.</span>
    </div>}

    <section className="dashboard-section" id="client-projets">
      <div className="dashboard-section-head">
        <div><span className="dashboard-eyebrow">Vos chantiers</span><h2>Mes projets avec KEMTA</h2></div>
        <span className="subtle-note">{projectCount} projet{projectCount === 1 ? '' : 's'} · cliquez pour ouvrir le détail</span>
      </div>
      {data.projects.length ? <div className="project-card-grid">
        {data.projects.map((project) => <Link className="project-card" key={project.id} to={`/dashboard/projets/${project.id}`} aria-label={`Ouvrir ${project.name}`}>
          <div className="project-card-head">
            <span className="project-house-icon"><House size={18} /></span>
            <span className="project-card-title"><strong>{project.name}</strong><small><MapPin size={12} /> {project.city} · {project.project_type}</small></span>
            <span className={`status-badge status-${project.status.toLowerCase()}`}>{projectStatusLabel(project.status)}</span>
          </div>
          <div className="project-progress-header"><span>{project.current_phase || 'Étape à définir'}</span><strong>{project.progress}%</strong></div>
          <div className="project-progress-track"><span style={{ width: `${Math.max(0, Math.min(100, project.progress))}%` }} /></div>
          <div className="project-card-foot">
            <span><small>Budget</small><strong>{amount(project.budget_total)}</strong></span>
            <span><small>Dépensé</small><strong>{amount(project.budget_spent)}</strong></span>
            <span className="project-card-open">Voir le détail <ArrowRight size={15} /></span>
          </div>
        </Link>)}
      </div> : <div className="dashboard-empty"><span className="empty-icon"><House size={22} /></span><div><strong>Votre espace projet est prêt.</strong><p>Après votre première demande et la création d’un projet, vous retrouverez ici ses étapes, ses dépenses, leurs reçus et son budget.</p><Link className="button button-primary button-small" to="/demande">Présenter mon projet <ArrowRight size={15} /></Link></div></div>}
    </section>

    <div className="dashboard-bottom-grid">
      <section className="dashboard-section" id="client-demandes">
        <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Demandes de service</span><h2>Vos dernières demandes</h2></div><Link to="/demande" className="subtle-button">Nouvelle demande <Plus size={15} /></Link></div>
        {data.service_requests.length ? <div className="request-list">{data.service_requests.map((request) => <RequestRow key={request.id} request={request} />)}</div> : <div className="small-empty"><FileText size={18} /><span>Vos demandes envoyées apparaîtront ici.</span></div>}
      </section>

      <NotificationsPanel data={data} emptyText="Vous serez informé ici des avancées importantes de votre projet." />
    </div>

    <ActivityPanel data={data} />
  </>;
}

interface TaskHandlers {
  busyTaskId: number | null;
  onTaskStatus: (taskId: number, status: TaskStatus) => Promise<void>;
}

function ManagerDashboard({ data, busyTaskId, onTaskStatus }: { data: DashboardResponse } & TaskHandlers) {
  return <>
    <div className="admin-stat-grid">
      <AdminMetric icon={<HardHat size={18} />} label="Projets suivis" value={data.statistics.projects ?? 0} tone="blue" />
      <AdminMetric icon={<CheckCircle2 size={18} />} label="Projets en cours" value={data.statistics.active_projects ?? 0} tone="green" />
      <AdminMetric icon={<ListChecks size={18} />} label="Tâches ouvertes" value={data.statistics.pending_tasks ?? 0} tone="sand" />
      <AdminMetric icon={<Camera size={18} />} label="Preuves à vérifier" value={data.statistics.evidences_pending ?? 0} tone="blue" />
    </div>

    <section className="dashboard-section" id="pilotage-projets">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Pilotage</span><h2>Projets suivis</h2></div><span className="subtle-note">{data.projects.length} projet{data.projects.length === 1 ? '' : 's'} affiché{data.projects.length === 1 ? '' : 's'}</span></div>
      {data.projects.length ? <div className="mini-table">{data.projects.map((project) => <Link className="mini-row mini-row-link" to={`/dashboard/projets/${project.id}`} key={project.id}><span className="mini-row-icon"><House size={16} /></span><div className="mini-row-main"><strong>{project.name}</strong><small>{project.city} · {project.current_phase || 'Étape à définir'} · {project.phases.filter((phase) => phase.status === 'COMPLETED').length}/{project.phases.length} étapes terminées</small></div><span className="mini-progress"><span style={{ width: `${Math.max(0, Math.min(100, project.progress))}%` }} /></span><strong className="mini-value">{project.progress}%</strong><ChevronRight size={16} /></Link>)}</div> : <div className="small-empty"><HardHat size={18} /><span>Aucun projet ne vous est encore attribué.</span></div>}
    </section>

    <section className="dashboard-section" id="pilotage-taches">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Suivi terrain</span><h2>Tâches de chantier</h2></div><span className="subtle-note">{data.statistics.pending_tasks ?? 0} ouverte{(data.statistics.pending_tasks ?? 0) === 1 ? '' : 's'}</span></div>
      {data.tasks.length ? <div className="mini-table">{data.tasks.map((task) => <TaskRow key={task.id} task={task} busy={busyTaskId === task.id} onStatus={onTaskStatus} />)}</div> : <div className="small-empty"><ListChecks size={18} /><span>Aucune tâche ouverte sur vos projets.</span></div>}
    </section>

    <section className="dashboard-section" id="pilotage-preuves">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Contrôle qualité</span><h2>Preuves terrain à vérifier</h2></div><span className="subtle-note">{data.statistics.evidences_pending ?? 0} en attente</span></div>
      {data.evidences.length ? <div className="mini-table">{data.evidences.map((evidence) => <div className="mini-row" key={evidence.id}><span className="mini-row-icon"><Camera size={16} /></span><div className="mini-row-main"><strong>{evidence.title}</strong><small>{evidence.project_name}{evidence.phase_name ? ` · ${evidence.phase_name}` : ''}{evidence.location ? ` · ${evidence.location}` : ''} · {dateLabel(evidence.created_at)}</small></div><span className={`status-badge status-${evidence.verification_status.toLowerCase()}`}>{evidenceStatusLabels[evidence.verification_status]}</span></div>)}</div> : <div className="small-empty"><Camera size={18} /><span>Aucune preuve transmise pour l’instant. Les photos de chantier arrivent depuis l’application mobile avec le même compte.</span></div>}
    </section>

    <div className="dashboard-bottom-grid">
      <NotificationsPanel data={data} emptyText="Les alertes de chantier et de tâches apparaîtront ici." />
      <ActivityPanel data={data} />
    </div>
  </>;
}

function FieldAgentDashboard({ data, busyTaskId, onTaskStatus }: { data: DashboardResponse } & TaskHandlers) {
  return <>
    <div className="admin-stat-grid">
      <AdminMetric icon={<HardHat size={18} />} label="Chantiers suivis" value={data.statistics.projects ?? 0} tone="blue" />
      <AdminMetric icon={<ListChecks size={18} />} label="Tâches assignées" value={data.statistics.tasks ?? 0} tone="green" />
      <AdminMetric icon={<CheckCircle2 size={18} />} label="À traiter" value={data.statistics.pending_tasks ?? 0} tone="sand" />
      <AdminMetric icon={<CalendarDays size={18} />} label="En retard" value={data.statistics.overdue_tasks ?? 0} tone="blue" />
      <AdminMetric icon={<Camera size={18} />} label="Preuves transmises" value={data.statistics.evidences ?? 0} tone="green" />
    </div>

    <section className="dashboard-section" id="terrain-taches">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Vos missions</span><h2>Mes tâches</h2></div><span className="subtle-note">Mettez à jour le statut depuis le terrain</span></div>
      {data.tasks.length ? <div className="mini-table">{data.tasks.map((task) => <TaskRow key={task.id} task={task} busy={busyTaskId === task.id} onStatus={onTaskStatus} />)}</div> : <div className="small-empty"><ListChecks size={18} /><span>Aucune tâche ne vous est encore assignée.</span></div>}
    </section>

    <section className="dashboard-section" id="terrain-chantiers">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Affectations</span><h2>Mes chantiers</h2></div></div>
      {data.projects.length ? <div className="mini-table">{data.projects.map((project) => <Link className="mini-row mini-row-link" to={`/dashboard/projets/${project.id}`} key={project.id}><span className="mini-row-icon"><House size={16} /></span><div className="mini-row-main"><strong>{project.name}</strong><small><MapPin size={12} /> {project.city} · {project.current_phase || 'Étape à définir'}</small></div><span className="mini-progress"><span style={{ width: `${Math.max(0, Math.min(100, project.progress))}%` }} /></span><span className="status-badge status-active">{projectStatusLabel(project.status)}</span><ChevronRight size={16} /></Link>)}</div> : <div className="small-empty"><HardHat size={18} /><span>Vous serez affecté à un chantier par l’équipe KEMTA.</span></div>}
      <p className="section-note"><Camera size={14} /> Les preuves terrain (photos géolocalisées) se transmettent depuis l’application mobile, connectée au même compte.</p>
    </section>

    <section className="dashboard-section" id="terrain-preuves">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Traçabilité</span><h2>Mes preuves transmises</h2></div><span className="subtle-note">{data.statistics.evidences ?? 0} enregistrée{(data.statistics.evidences ?? 0) === 1 ? '' : 's'}</span></div>
      {data.evidences.length ? <div className="mini-table">{data.evidences.map((evidence) => <div className="mini-row" key={evidence.id}><span className="mini-row-icon"><Camera size={16} /></span><div className="mini-row-main"><strong>{evidence.title}</strong><small>{evidence.project_name} · {dateLabel(evidence.created_at)}</small></div><span className={`status-badge status-${evidence.verification_status.toLowerCase()}`}>{evidenceStatusLabels[evidence.verification_status]}</span></div>)}</div> : <div className="small-empty"><Camera size={18} /><span>Aucune preuve transmise pour l’instant. Une photo publiée depuis l’application mobile apparaîtra ici avec son statut de vérification.</span></div>}
    </section>

    <div className="dashboard-bottom-grid">
      <NotificationsPanel data={data} emptyText="Les consignes et rappels de visite apparaîtront ici." />
      <ActivityPanel data={data} />
    </div>
  </>;
}

function TaskRow({ task, busy, onStatus }: { task: DashboardTask; busy: boolean; onStatus: (taskId: number, status: TaskStatus) => Promise<void> }) {
  return <div className="mini-row mini-row-task">
    <span className="mini-row-icon"><ListChecks size={16} /></span>
    <div className="mini-row-main">
      <strong>{task.title}</strong>
      <small>{task.project_name}{task.phase_name ? ` · ${task.phase_name}` : ''}{task.assigned_to_name ? ` · ${task.assigned_to_name}` : ''}{task.due_date ? ` · ${deadlineLabel(task.due_date)}` : ''}</small>
    </div>
    <span className={`status-badge status-${task.status.toLowerCase()}`}>{taskStatusLabels[task.status]}</span>
    <span className="task-actions">
      {task.status !== 'IN_PROGRESS' && task.status !== 'DONE' && <button type="button" className="task-button" disabled={busy} onClick={() => void onStatus(task.id, 'IN_PROGRESS')}>Commencer</button>}
      {task.status !== 'DONE' && <button type="button" className="task-button task-button-primary" disabled={busy} onClick={() => void onStatus(task.id, 'DONE')}>Terminer</button>}
      {task.status === 'DONE' && <span className="task-done"><Check size={14} /> Terminée</span>}
    </span>
  </div>;
}

function BtpDashboard({ data }: { data: DashboardResponse }) {
  const company = data.company;
  return <>
    <div className="dashboard-stat-grid btp-stat-grid">
      <div className="dashboard-metric"><span className="metric-icon metric-blue"><Building2 size={18} /></span><span><small>Mon entreprise</small><strong>{company ? company.name : 'À créer'}</strong><em>{company ? `Profil complété à ${company.profile_completion}%` : 'Créez votre vitrine KEMTA'}</em></span></div>
      <div className="dashboard-metric"><span className="metric-icon metric-green"><BriefcaseBusiness size={18} /></span><span><small>Opportunités ouvertes</small><strong>{data.statistics.open_opportunities ?? 0}</strong><em>Publiées par l’équipe KEMTA</em></span></div>
      <div className="dashboard-metric"><span className="metric-icon metric-sand"><ClipboardList size={18} /></span><span><small>Candidatures</small><strong>{data.statistics.applications ?? 0}</strong><em>Envoyées depuis votre espace</em></span></div>
    </div>

    <section className="dashboard-section" id="btp-company">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Votre vitrine professionnelle</span><h2>Mon entreprise</h2></div>{company && <Link to={company.is_published ? `/entreprises/${company.slug}` : '/entreprise/modifier'} className="subtle-button">{company.is_published ? 'Voir le profil public' : 'Compléter mon profil'} <ArrowRight size={15} /></Link>}</div>
      {company ? <div className="company-profile-summary">
        <div className="company-summary-brand"><span className="company-summary-icon"><Building2 size={23} /></span><span><strong>{company.name}</strong><small><MapPin size={13} /> {company.city || 'Localisation à compléter'}</small></span>{company.verified && <span className="verified-label"><BadgeCheck size={14} /> Vérifiée</span>}</div>
        <div className="company-completion"><div><span>Profil complété</span><strong>{company.profile_completion}%</strong></div><div className="completion-track"><span style={{ width: `${company.profile_completion}%` }} /></div><Link className="text-link" to={company.is_published ? `/entreprises/${company.slug}/modifier` : '/entreprise/modifier'}>{company.is_published ? 'Mettre à jour ma vitrine' : 'Compléter mon profil'} <ArrowRight size={15} /></Link></div>
        <div className="company-stats-inline"><span><strong>{company.portfolio_count}</strong><small>Réalisations</small></span><span><strong>{company.views_count}</strong><small>Vues du profil</small></span><span><strong>{data.statistics.applications ?? 0}</strong><small>Candidatures</small></span></div>
      </div> : <div className="dashboard-empty"><span className="empty-icon"><Building2 size={22} /></span><div><strong>Votre profil entreprise reste à créer.</strong><p>Présentez votre équipe, vos services, votre zone d’intervention et vos réalisations pour apparaître dans le catalogue KEMTA BTP.</p><Link className="button button-primary button-small" to="/entreprise/creer">Créer mon profil <ArrowRight size={15} /></Link></div></div>}
    </section>

    <section className="dashboard-section" id="btp-candidatures">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Suivi des réponses</span><h2>Mes candidatures</h2></div><Link className="subtle-button" to="/opportunites">Répondre à un appel <ArrowRight size={15} /></Link></div>
      {data.applications.length ? <div className="mini-table">{data.applications.map((application) => <div className="mini-row" key={application.id}><span className="mini-row-icon"><ClipboardList size={16} /></span><div className="mini-row-main"><strong>{application.opportunity_title}</strong><small>Envoyée le {dateLabel(application.created_at)}{application.estimated_budget ? ` · Budget proposé : ${amount(application.estimated_budget)}` : ''}{application.duration_days ? ` · ${application.duration_days} jours` : ''}</small></div><span className={`status-badge status-${application.status.toLowerCase()}`}>{application.status_label}</span></div>)}</div> : <div className="small-empty"><ClipboardList size={18} /><span>Vos candidatures et leur avancement apparaîtront ici.</span></div>}
    </section>

    <section className="dashboard-section" id="btp-opportunites">
      <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">À découvrir</span><h2>Opportunités BTP</h2></div><Link className="subtle-button" to="/opportunites">Toutes les opportunités <ArrowRight size={15} /></Link></div>
      {data.opportunities.length ? <div className="opportunity-mini-list">{data.opportunities.map((item) => <div className="opportunity-mini-row" key={item.id}><span className="opportunity-mini-icon"><HardHat size={17} /></span><div><strong>{item.title}</strong><small>{item.project_type} · {item.city}</small></div><span className="deadline-label"><CalendarDays size={14} /> {dateLabel(item.deadline)}</span><Link aria-label={`Voir ${item.title}`} to="/opportunites"><ArrowRight size={16} /></Link></div>)}</div> : <div className="small-empty"><BriefcaseBusiness size={18} /><span>Aucune opportunité ouverte pour le moment. Vous serez informé dès qu’un appel correspondra à votre profil.</span></div>}
    </section>

    <div className="dashboard-bottom-grid">
      <NotificationsPanel data={data} emptyText="Les nouvelles opportunités et décisions apparaîtront ici." />
      <ActivityPanel data={data} />
    </div>
  </>;
}

function AdminDashboard({ data }: { data: DashboardResponse }) {
  const stats = data.statistics;
  return <>
    <div className="admin-stat-grid">
      <AdminMetric icon={<House size={18} />} label="Projets actifs" value={stats.active_projects ?? 0} tone="blue" />
      <AdminMetric icon={<FileText size={18} />} label="Demandes à traiter" value={stats.service_requests ?? 0} tone="green" />
      <AdminMetric icon={<Building2 size={18} />} label="Entreprises" value={stats.companies ?? 0} tone="sand" />
      <AdminMetric icon={<BriefcaseBusiness size={18} />} label="Opportunités ouvertes" value={stats.opportunities ?? 0} tone="blue" />
      <AdminMetric icon={<ClipboardList size={18} />} label="Candidatures" value={stats.applications ?? 0} tone="green" />
      <AdminMetric icon={<Wallet size={18} />} label="Revenus enregistrés" value={amount(stats.revenue)} tone="sand" />
    </div>

    <div className="admin-content-grid">
      <section className="dashboard-section admin-table-section" id="admin-demandes">
        <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Suivi opérationnel</span><h2>Demandes récentes</h2></div><a className="subtle-button" href="/admin/service_requests/servicerequest/" target="_blank" rel="noreferrer">Traiter dans l’admin <ArrowRight size={15} /></a></div>
        {data.service_requests.length ? <div className="request-list">{data.service_requests.slice(0, 6).map((request) => <RequestRow key={request.id} request={request} showOwner />)}</div> : <div className="small-empty"><FileText size={18} /><span>Aucune demande à afficher.</span></div>}
      </section>
      <section className="admin-quick-links">
        <span className="dashboard-eyebrow">Administration</span><h2>Accès rapide</h2>
        <a href="/admin/service_requests/servicerequest/" target="_blank" rel="noreferrer"><FileText size={17} /> Gérer les demandes <ArrowRight size={15} /></a>
        <a href="/admin/companies/companyprofile/" target="_blank" rel="noreferrer"><Building2 size={17} /> Vérifier les entreprises <ArrowRight size={15} /></a>
        <a href="/admin/opportunities/opportunity/" target="_blank" rel="noreferrer"><BriefcaseBusiness size={17} /> Publier une opportunité <ArrowRight size={15} /></a>
        <a href="/admin/projects/projectexpense/" target="_blank" rel="noreferrer"><Receipt size={17} /> Enregistrer des dépenses <ArrowRight size={15} /></a>
        <a href="/admin/projects/project/" target="_blank" rel="noreferrer"><HardHat size={17} /> Suivre les projets <ArrowRight size={15} /></a>
        <p>Les actions d’administration sont journalisées et soumises aux permissions du compte.</p>
      </section>
    </div>

    <div className="admin-columns">
      <section className="dashboard-section" id="admin-projets">
        <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Chantiers</span><h2>Projets récents</h2></div><span className="subtle-note">{stats.projects ?? 0} au total</span></div>
        {data.projects.length ? <div className="mini-table">{data.projects.map((project) => <Link className="mini-row mini-row-link" to={`/dashboard/projets/${project.id}`} key={project.id}><span className="mini-row-icon"><House size={16} /></span><div className="mini-row-main"><strong>{project.name}</strong><small>{project.city} · {project.current_phase || 'Étape à définir'}</small></div><span className="mini-progress"><span style={{ width: `${Math.max(0, Math.min(100, project.progress))}%` }} /></span><span className="status-badge status-active">{projectStatusLabel(project.status)}</span><ChevronRight size={16} /></Link>)}</div> : <div className="small-empty"><HardHat size={18} /><span>Aucun projet enregistré.</span></div>}
      </section>

      <section className="dashboard-section" id="admin-entreprises">
        <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Catalogue BTP</span><h2>Entreprises</h2></div><span className="subtle-note">{stats.companies ?? 0} compte{(stats.companies ?? 0) === 1 ? '' : 's'}</span></div>
        {data.companies.length ? <div className="mini-table">{data.companies.map((company) => <div className="mini-row" key={company.id}><span className="mini-row-icon"><Building2 size={16} /></span><div className="mini-row-main"><strong>{company.name}</strong><small>{company.city || 'Ville à préciser'} · Profil {company.profile_completion}% · {company.portfolio_count} réalisation{company.portfolio_count === 1 ? '' : 's'}</small></div><span className={`status-badge ${company.is_published ? 'status-active' : 'status-in_review'}`}>{company.verified ? 'Vérifiée' : company.is_published ? 'Publiée' : 'À vérifier'}</span></div>)}</div> : <div className="small-empty"><Building2 size={18} /><span>Aucune entreprise enregistrée.</span></div>}
      </section>

      <section className="dashboard-section" id="admin-opportunites">
        <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Appels d’offres</span><h2>Opportunités</h2></div><span className="subtle-note">{stats.all_opportunities ?? 0} au total</span></div>
        {data.opportunities.length ? <div className="mini-table">{data.opportunities.map((item) => <div className="mini-row" key={item.id}><span className="mini-row-icon"><BriefcaseBusiness size={16} /></span><div className="mini-row-main"><strong>{item.title}</strong><small>{item.city} · Limite : {dateLabel(item.deadline)}</small></div><span className={`status-badge status-${item.status.toLowerCase()}`}>{item.status === 'OPEN' ? 'Ouverte' : item.status === 'DRAFT' ? 'Brouillon' : item.status === 'CLOSED' ? 'Clôturée' : 'Annulée'}</span></div>)}</div> : <div className="small-empty"><BriefcaseBusiness size={18} /><span>Aucune opportunité enregistrée.</span></div>}
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Journal</span><h2>Activité récente</h2></div><ShieldCheck size={18} /></div>
        {data.recent_activity.length ? <div className="activity-list">{data.recent_activity.map((entry) => <div className="activity-row" key={entry.id}><span className="activity-dot" /><span><strong>{entry.description}</strong><small>{dateLabel(entry.created_at)}</small></span></div>)}</div> : <div className="small-empty"><ShieldCheck size={18} /><span>Aucune activité enregistrée pour le moment.</span></div>}
      </section>
    </div>

    <div className="dashboard-bottom-grid">
      <NotificationsPanel data={data} emptyText="Aucune notification pour le moment." />
      <section className="support-panel" id="aide"><span className="support-icon"><MessageIcon /></span><div><h3>Besoin d’assistance ?</h3><p>Les accès d’administration permettent de vérifier les entreprises, publier des opportunités et suivre les paiements.</p><Link to="/demande">Contacter l’équipe KEMTA <ArrowRight size={15} /></Link></div></section>
    </div>
  </>;
}

function RequestRow({ request, showOwner = false }: { request: RequestSummary; showOwner?: boolean }) {
  return <div className="request-list-row">
    <span className="request-list-icon"><FileText size={17} /></span>
    <div className="request-list-main">
      <strong>{request.service_type_label ?? serviceLabels[request.service_type] ?? request.service_type}{showOwner && request.owner_name ? ` · ${request.owner_name}` : ''}</strong>
      <small>{request.request_code}{request.related_project_name ? ` · ${request.related_project_name}` : ''} · {request.city || 'Localisation à préciser'} · {dateLabel(request.created_at)}</small>
    </div>
    <span className={`status-badge status-${request.status.toLowerCase()}`}>{serviceStatusLabel(request.status)}</span>
    <ChevronRight size={17} />
  </div>;
}

function NotificationsPanel({ data, emptyText }: { data: DashboardResponse; emptyText: string }) {
  return <section className="dashboard-info-panel" id="notifications">
    <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">À ne pas manquer</span><h2>Notifications</h2></div><Link className="subtle-button" to="/dashboard/notifications">Tout voir <ArrowRight size={15} /></Link></div>
    {data.notifications.length ? data.notifications.slice(0, 4).map((item) => <div className="notification-row" key={item.id}><span className={`notification-dot${item.is_read ? ' notification-dot-read' : ''}`} /><span><strong>{item.title}</strong><small>{dateLabel(item.created_at)}</small></span></div>) : <p className="muted-text">{emptyText}</p>}
  </section>;
}

function ActivityPanel({ data }: { data: DashboardResponse }) {
  return <section className="dashboard-info-panel" id="aide">
    <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Traçabilité</span><h2>Activité de votre compte</h2></div><ShieldCheck size={18} /></div>
    {data.recent_activity.length ? data.recent_activity.slice(0, 4).map((entry) => <div className="notification-row" key={entry.id}><span className="notification-dot" /><span><strong>{entry.description}</strong><small>{dateLabel(entry.created_at)}</small></span></div>) : <p className="muted-text">Vos actions importantes sont enregistrées et consultables par l’équipe KEMTA.</p>}
    <p className="panel-note"><Info size={13} /> Une question sur votre projet ? L’équipe KEMTA vous répond depuis la page de demande.</p>
  </section>;
}

function AdminMetric({ icon, label, value, tone }: { icon: ReactNode; label: string; value: string | number; tone: string }) {
  return <div className="admin-metric"><span className={`metric-icon metric-${tone}`}>{icon}</span><span><small>{label}</small><strong>{value}</strong></span></div>;
}

function DashboardSkeleton() {
  return <div className="dashboard-skeleton" aria-label="Chargement du tableau de bord"><div /><div /><div /><div className="skeleton-wide" /></div>;
}

function MessageIcon() {
  return <span className="message-mark">?</span>;
}
