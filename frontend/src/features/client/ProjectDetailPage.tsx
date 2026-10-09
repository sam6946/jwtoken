import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, CalendarDays, Camera, Check, CircleAlert, FileDown, FileText,
  House, Info, ListChecks, MapPin, Plus, Receipt, Wallet,
} from 'lucide-react';
import { ApiError, apiRequest, openAuthenticatedFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { DashboardShell } from '../dashboard/DashboardShell';
import {
  amount, dateLabel, evidenceStatusLabels, expenseStatusTone, projectStatusLabel,
  serviceStatusLabel, type EvidenceSummary, type ProjectDetail, type ProjectExpense, type ProjectPhase,
} from '../dashboard/dashboardData';

const phaseStepClass: Record<ProjectPhase['status'], string> = {
  COMPLETED: 'phase-step phase-step-done',
  CURRENT: 'phase-step phase-step-current',
  ISSUE: 'phase-step phase-step-issue',
  UPCOMING: 'phase-step',
};

const phaseTagLabel: Record<ProjectPhase['status'], string> = {
  COMPLETED: 'Terminée',
  CURRENT: 'En cours',
  ISSUE: 'À vérifier',
  UPCOMING: 'À venir',
};

function phaseCaption(phase: ProjectPhase): string {
  if (phase.status === 'COMPLETED') return phase.completed_at ? `Terminée le ${dateLabel(phase.completed_at)}` : 'Terminée';
  if (phase.status === 'CURRENT') return phase.planned_end ? `Livraison visée le ${dateLabel(phase.planned_end)}` : 'Étape en cours sur le chantier';
  if (phase.status === 'ISSUE') return 'Un point doit être vérifié par l’équipe KEMTA';
  return phase.planned_start ? `Prévue à partir du ${dateLabel(phase.planned_start)}` : 'À venir';
}

function budgetShare(project: ProjectDetail): number {
  const total = Number(project.budget?.total ?? 0);
  const spent = Number(project.budget?.spent ?? 0);
  if (!Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.round((spent / total) * 100));
}

/**
 * Fiche d'un chantier : budget, dépenses justifiées par leurs reçus, demandes envoyées
 * et avancement des étapes. Réservée au propriétaire (et à l'équipe KEMTA) par l'API.
 */
export function ProjectDetailPage() {
  const { projectId } = useParams();
  const { user, isReady, signOut } = useAuth();
  const navigate = useNavigate();
  const [openError, setOpenError] = useState<string | null>(null);
  const [busyReceipt, setBusyReceipt] = useState<number | null>(null);

  const projectQuery = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => apiRequest<ProjectDetail>(`/projects/${projectId}/`),
    enabled: Boolean(user && isReady && projectId),
  });
  const evidenceQuery = useQuery({
    queryKey: ['project-evidences', projectId],
    queryFn: () => apiRequest<{ results: EvidenceSummary[] }>(`/evidences/?project=${projectId}`),
    enabled: Boolean(user && isReady && projectId),
  });

  async function handleSignOut(): Promise<void> {
    await signOut();
    navigate('/');
  }

  async function openReceipt(expense: ProjectExpense): Promise<void> {
    if (!expense.receipt_url) return;
    setBusyReceipt(expense.id);
    setOpenError(null);
    try {
      await openAuthenticatedFile(expense.receipt_url);
    } catch (error) {
      setOpenError(error instanceof ApiError ? error.message : 'Le justificatif n’a pas pu être ouvert.');
    } finally {
      setBusyReceipt(null);
    }
  }

  if (!isReady) return <div className="app-loading"><span className="loading-mark" /><p>Préparation de votre espace…</p></div>;
  if (!user) return <Navigate to={`/connexion?next=%2Fdashboard%2Fprojets%2F${projectId ?? ''}`} replace />;

  const project = projectQuery.data;
  const evidences = evidenceQuery.data?.results ?? [];
  const notFound = projectQuery.error instanceof ApiError && projectQuery.error.status === 404;
  const completedPhases = project?.phases.filter((phase) => phase.status === 'COMPLETED').length ?? 0;
  const share = project ? budgetShare(project) : 0;

  return (
    <DashboardShell user={user} breadcrumb={project ? project.name : 'Fiche projet'} active="projects" onSignOut={() => void handleSignOut()}>
      <Link className="back-link" to="/dashboard"><ArrowLeft size={15} /> Retour à mes projets</Link>

      {projectQuery.isLoading && <div className="dashboard-skeleton" aria-label="Chargement du projet"><div /><div /><div /><div className="skeleton-wide" /></div>}

      {projectQuery.isError && (notFound
        ? <div className="dashboard-error"><CircleAlert size={22} /><div><strong>Ce projet n’est pas accessible.</strong><p>Il a peut-être été archivé, ou il n’appartient pas à votre compte.</p><Link className="button button-outline button-small" to="/dashboard">Revenir à mes projets</Link></div></div>
        : <div className="dashboard-error"><CircleAlert size={22} /><div><strong>La fiche du projet ne peut pas être chargée.</strong><p>{projectQuery.error instanceof ApiError ? projectQuery.error.message : 'Vérifiez votre connexion puis réessayez.'}</p><button className="button button-outline button-small" onClick={() => void projectQuery.refetch()}>Réessayer</button></div></div>)}

      {project && <>
        <div className="project-detail-head">
          <div>
            <span className="dashboard-eyebrow">{project.project_type}</span>
            <h1>{project.name}</h1>
            <p>
              <MapPin size={14} /> {project.city}
              <span className="dot-separator" />Propriétaire : {project.owner_name}
              <span className="dot-separator" />Mis à jour le {dateLabel(project.updated_at)}
            </p>
          </div>
          <div className="project-detail-head-side">
            <span className={`status-badge status-${project.status.toLowerCase()}`}>{projectStatusLabel(project.status)}</span>
            <Link className="button button-primary button-small" to={`/demande?projet=${project.id}`}><Plus size={16} /> Nouvelle demande</Link>
          </div>
        </div>

        <div className="kpi-row">
          <div className="kpi-card">
            <span className="kpi-head"><span className="kpi-icon stat-blue"><Wallet size={16} /></span><span className="kpi-label">Budget prévisionnel</span></span>
            <strong className="kpi-value">{amount(project.budget?.total ?? project.budget_total)}</strong>
            <span className="kpi-foot"><CalendarDays size={13} /> Livraison visée le {dateLabel(project.planned_end)}</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-head"><span className="kpi-icon stat-sand"><Receipt size={16} /></span><span className="kpi-label">Dépenses engagées</span></span>
            <strong className="kpi-value">{amount(project.budget?.spent ?? project.budget_spent)}</strong>
            <span className={`kpi-bar${share >= 90 ? ' kpi-bar-warn' : ''}`}><span style={{ width: `${share}%` }} /></span>
            <span className="kpi-foot"><Info size={13} /> {share}% du budget prévisionnel</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-head"><span className="kpi-icon stat-green"><Check size={16} /></span><span className="kpi-label">Dont justifiées</span></span>
            <strong className="kpi-value">{amount(project.budget?.justified_total)}</strong>
            <span className="kpi-foot"><FileDown size={13} /> {project.budget?.receipt_count ?? 0} reçu{(project.budget?.receipt_count ?? 0) === 1 ? '' : 's'} disponible{(project.budget?.receipt_count ?? 0) === 1 ? '' : 's'}</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-head"><span className="kpi-icon stat-blue"><Wallet size={16} /></span><span className="kpi-label">Restant à engager</span></span>
            <strong className="kpi-value">{amount(project.budget?.remaining)}</strong>
            <span className="kpi-foot"><Receipt size={13} /> {project.budget?.expense_count ?? 0} dépense{(project.budget?.expense_count ?? 0) === 1 ? '' : 's'} enregistrée{(project.budget?.expense_count ?? 0) === 1 ? '' : 's'}</span>
          </div>
        </div>

        <section className="dashboard-section" id="projet-depenses">
          <div className="dashboard-section-head">
            <div><span className="dashboard-eyebrow">Justificatifs</span><h2>Dépenses et reçus</h2></div>
            <span className="subtle-note">{project.expenses.length} ligne{project.expenses.length === 1 ? '' : 's'} · montants à rapprocher des pièces</span>
          </div>
          {openError && <div className="dashboard-alert"><CircleAlert size={17} /><span>{openError}</span></div>}
          {project.expenses.length ? <div className="expense-table">
            <div className="expense-row expense-row-head"><span>Date</span><span>Dépense</span><span>Montant</span><span>Statut</span><span>Justificatif</span></div>
            {project.expenses.map((expense) => <div className="expense-row" key={expense.id}>
              <span className="expense-date">{dateLabel(expense.spent_at)}</span>
              <span className="expense-label"><strong>{expense.label}</strong><small>{expense.category_label}{expense.reference ? ` · Réf. ${expense.reference}` : ''}{expense.recorded_by_name ? ` · saisi par ${expense.recorded_by_name}` : ''}</small></span>
              <span className="expense-amount">{amount(expense.amount)}</span>
              <span><span className={`status-badge status-${expenseStatusTone[expense.status]}`}>{expense.status_label}</span></span>
              <span className="expense-receipt">
                {expense.has_receipt
                  ? <button type="button" className="receipt-button" disabled={busyReceipt === expense.id} onClick={() => void openReceipt(expense)}>
                    <FileDown size={15} /> {busyReceipt === expense.id ? 'Ouverture…' : 'Voir le reçu'}
                  </button>
                  : <span className="receipt-missing">Reçu à venir</span>}
              </span>
            </div>)}
          </div> : <div className="small-empty"><Receipt size={18} /><span>Aucune dépense n’a encore été enregistrée sur ce chantier.</span></div>}
          <p className="panel-note"><Info size={13} /> Les montants proviennent des dépenses saisies par l’équipe KEMTA et de leurs justificatifs. Chaque reçu est accessible uniquement depuis votre espace.</p>
        </section>

        <div className="project-detail-grid">
          <section className="dashboard-section project-detail-main">
            <div className="dashboard-section-head">
              <div><span className="dashboard-eyebrow">Suivi des travaux</span><h2>Étapes du chantier</h2></div>
              <span className="subtle-note">{completedPhases} étape{completedPhases === 1 ? '' : 's'} terminée{completedPhases === 1 ? '' : 's'} sur {project.phases.length}</span>
            </div>
            <div className="project-progress-header"><span>Avancement global</span><strong>{project.progress}%</strong></div>
            <div className="project-progress-track"><span style={{ width: `${Math.max(0, Math.min(100, project.progress))}%` }} /></div>
            {project.phases.length ? <ol className="phase-timeline">
              {project.phases.map((phase) => <li className={phaseStepClass[phase.status]} key={phase.id}>
                <span className="phase-dot">{phase.status === 'COMPLETED' ? <Check size={15} /> : phase.status === 'CURRENT' || phase.status === 'ISSUE' ? <i /> : null}</span>
                <span className="phase-info"><strong>{phase.name}</strong><small>{phaseCaption(phase)}</small></span>
                <span className="phase-tag">{phaseTagLabel[phase.status]}</span>
              </li>)}
            </ol> : <div className="small-empty"><ListChecks size={18} /><span>Les étapes seront publiées par l’équipe KEMTA.</span></div>}
            <p className="section-note"><CalendarDays size={14} /> Démarrage : {dateLabel(project.planned_start)} · Livraison visée : {dateLabel(project.planned_end)}</p>
          </section>

          <div className="project-detail-aside">
            <section className="dashboard-section" id="projet-demandes">
              <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Échanges avec KEMTA</span><h2>Demandes liées</h2></div><Link className="subtle-button" to={`/demande?projet=${project.id}`}>Nouvelle <Plus size={15} /></Link></div>
              {project.service_requests.length ? <div className="request-list">{project.service_requests.map((item) => <div className="request-list-row" key={item.id}>
                <span className="request-list-icon"><FileText size={17} /></span>
                <div className="request-list-main"><strong>{item.service_type_label}{item.is_origin ? ' · à l’origine du projet' : ''}</strong><small>{item.request_code} · envoyée le {dateLabel(item.created_at)}</small></div>
                <span className={`status-badge status-${item.status.toLowerCase()}`}>{serviceStatusLabel(item.status)}</span>
              </div>)}</div> : <div className="small-empty"><FileText size={18} /><span>Aucune demande n’est encore rattachée à ce chantier.</span></div>}
            </section>

            <section className="dashboard-section" id="projet-preuves">
              <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Traçabilité</span><h2>Preuves terrain</h2></div><Camera size={18} /></div>
              {evidences.length ? <div className="mini-table">{evidences.map((evidence) => <div className="mini-row" key={evidence.id}>
                <span className="mini-row-icon"><Camera size={16} /></span>
                <div className="mini-row-main"><strong>{evidence.title}</strong><small>{evidence.phase_name ? `${evidence.phase_name} · ` : ''}{evidence.location || 'Localisation non précisée'} · {dateLabel(evidence.created_at)}</small></div>
                <span className={`status-badge status-${evidence.verification_status.toLowerCase()}`}>{evidenceStatusLabels[evidence.verification_status]}</span>
              </div>)}</div> : <div className="small-empty"><Camera size={18} /><span>Aucune preuve publiée pour l’instant : les photos sont transmises par l’équipe terrain depuis le chantier.</span></div>}
            </section>
          </div>
        </div>
      </>}

      {!project && !projectQuery.isLoading && !projectQuery.isError && <div className="small-empty"><House size={18} /><span>Ce projet est introuvable.</span></div>}
      <p className="detail-footnote"><ArrowRight size={14} /> Une question sur une ligne de dépense ? Ouvrez une demande rattachée à ce projet : l’équipe KEMTA vous répond depuis votre espace.</p>
    </DashboardShell>
  );
}
