import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, CalendarDays, Camera, Check, CircleAlert, FileDown, FileText,
  HardHat, House, Info, ListChecks, MapPin, Plus, Receipt, Wallet,
} from 'lucide-react';
import { ApiError, apiRequest, openAuthenticatedFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { DashboardShell } from '../dashboard/DashboardShell';
import {
  amount, dateLabel, evidenceStatusLabels, expenseStatusTone, projectStatusLabel,
  serviceStatusLabel, type EvidenceSummary, type ProjectDetail, type ProjectExpense,
} from '../dashboard/dashboardData';

function phaseTone(status: string): string {
  return `project-phase project-phase-${status.toLowerCase()}`;
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
            <p><MapPin size={14} /> {project.city}<span className="dot-separator" />Propriétaire : {project.owner_name}<span className="dot-separator" />Mis à jour le {dateLabel(project.updated_at)}</p>
          </div>
          <div className="project-detail-head-side">
            <span className={`status-badge status-${project.status.toLowerCase()}`}>{projectStatusLabel(project.status)}</span>
            <Link className="button button-primary button-small" to={`/demande?projet=${project.id}`}><Plus size={16} /> Nouvelle demande</Link>
          </div>
        </div>

        <div className="client-stat-row project-kpi-row">
          <div className="client-stat-card"><span className="client-stat-icon stat-blue"><Wallet size={17} /></span><small>Budget prévisionnel</small><strong>{amount(project.budget?.total ?? project.budget_total)}</strong></div>
          <div className="client-stat-card"><span className="client-stat-icon stat-sand"><Receipt size={17} /></span><small>Dépenses déclarées</small><strong>{amount(project.budget?.spent ?? project.budget_spent)}</strong></div>
          <div className="client-stat-card"><span className="client-stat-icon stat-green"><Check size={17} /></span><small>Restant à engager</small><strong>{amount(project.budget?.remaining)}</strong></div>
          <div className="client-stat-card"><span className="client-stat-icon stat-blue"><HardHat size={17} /></span><small>Avancement</small><strong>{project.progress}%</strong></div>
        </div>

        <div className="project-detail-grid">
          <section className="dashboard-section project-detail-main">
            <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Suivi des travaux</span><h2>Étapes du chantier</h2></div><span className="subtle-note">Étape actuelle : {project.current_phase || 'à définir'}</span></div>
            <div className="project-progress-header"><span>Avancement global</span><strong>{project.progress}%</strong></div>
            <div className="project-progress-track"><span style={{ width: `${Math.max(0, Math.min(100, project.progress))}%` }} /></div>
            {project.phases.length ? <ol className="phase-timeline">
              {project.phases.map((phase) => <li className={phaseTone(phase.status)} key={phase.id}>
                <span className="phase-marker">{phase.status === 'COMPLETED' ? <Check size={13} /> : phase.status === 'CURRENT' ? <i /> : null}</span>
                <span className="phase-body"><strong>{phase.name}</strong><small>{phase.status === 'COMPLETED' ? `Terminée${phase.completed_at ? ` le ${dateLabel(phase.completed_at)}` : ''}` : phase.status === 'CURRENT' ? 'En cours' : phase.status === 'ISSUE' ? 'À vérifier' : 'À venir'}{phase.planned_end ? ` · prévue le ${dateLabel(phase.planned_end)}` : ''}</small></span>
              </li>)}
            </ol> : <div className="small-empty"><ListChecks size={18} /><span>Les étapes seront publiées par l’équipe KEMTA.</span></div>}
            <p className="section-note"><CalendarDays size={14} /> Démarrage prévu : {dateLabel(project.planned_start)} · Livraison visée : {dateLabel(project.planned_end)}</p>
          </section>

          <section className="dashboard-section" id="projet-budget">
            <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Finances du chantier</span><h2>Budget &amp; dépenses</h2></div><Wallet size={18} /></div>
            {project.budget && <>
              <div className="budget-rows">
                <div><small>Budget prévisionnel</small><strong>{amount(project.budget.total)}</strong></div>
                <div><small>Dépenses engagées</small><strong>{amount(project.budget.spent)}</strong></div>
                <div><small>Dont justifiées</small><strong>{amount(project.budget.justified_total)}</strong></div>
                <div><small>Restant à engager</small><strong>{amount(project.budget.remaining)}</strong></div>
              </div>
              <div className="budget-consumption">
                <div className="project-progress-header"><span>Consommation du budget</span><strong>{consumptionPercent(project)}%</strong></div>
                <div className="project-progress-track"><span style={{ width: `${consumptionPercent(project)}%` }} /></div>
              </div>
              <ul className="budget-checklist">
                <li><Receipt size={14} /> {project.budget.expense_count} dépense{project.budget.expense_count === 1 ? '' : 's'} enregistrée{project.budget.expense_count === 1 ? '' : 's'}</li>
                <li><FileDown size={14} /> {project.budget.receipt_count} reçu{project.budget.receipt_count === 1 ? '' : 's'} disponible{project.budget.receipt_count === 1 ? '' : 's'}</li>
              </ul>
            </>}
            <p className="panel-note"><Info size={13} /> Les montants affichés proviennent des dépenses saisies par l’équipe KEMTA et de leurs justificatifs.</p>
          </section>
        </div>

        <section className="dashboard-section" id="projet-depenses">
          <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Justificatifs</span><h2>Dépenses et reçus</h2></div><span className="subtle-note">{project.expenses.length} ligne{project.expenses.length === 1 ? '' : 's'}</span></div>
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
        </section>

        <div className="dashboard-bottom-grid">
          <section className="dashboard-section" id="projet-demandes">
            <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Échanges avec KEMTA</span><h2>Demandes liées à ce projet</h2></div><Link className="subtle-button" to={`/demande?projet=${project.id}`}>Nouvelle demande <Plus size={15} /></Link></div>
            {project.service_requests.length ? <div className="request-list">{project.service_requests.map((item) => <div className="request-list-row" key={item.id}>
              <span className="request-list-icon"><FileText size={17} /></span>
              <div className="request-list-main"><strong>{item.service_type_label}{item.is_origin ? ' · à l’origine du projet' : ''}</strong><small>{item.request_code} · envoyée le {dateLabel(item.created_at)}</small></div>
              <span className={`status-badge status-${item.status.toLowerCase()}`}>{serviceStatusLabel(item.status)}</span>
            </div>)}</div> : <div className="small-empty"><FileText size={18} /><span>Aucune demande n’est encore rattachée à ce chantier.</span></div>}
          </section>

          <section className="dashboard-section" id="projet-preuves">
            <div className="dashboard-section-head"><div><span className="dashboard-eyebrow">Traçabilité du chantier</span><h2>Preuves terrain</h2></div><Camera size={18} /></div>
            {evidences.length ? <div className="mini-table">{evidences.map((evidence) => <div className="mini-row" key={evidence.id}>
              <span className="mini-row-icon"><Camera size={16} /></span>
              <div className="mini-row-main"><strong>{evidence.title}</strong><small>{evidence.phase_name ? `${evidence.phase_name} · ` : ''}{evidence.location || 'Localisation non précisée'} · {dateLabel(evidence.created_at)}</small></div>
              <span className={`status-badge status-${evidence.verification_status.toLowerCase()}`}>{evidenceStatusLabels[evidence.verification_status]}</span>
            </div>)}</div> : <div className="small-empty"><Camera size={18} /><span>Aucune preuve publiée pour l’instant. Les photos de chantier sont transmises par l’équipe terrain depuis l’application mobile, avec le même compte.</span></div>}
          </section>
        </div>
      </>}

      {!project && !projectQuery.isLoading && !projectQuery.isError && <div className="small-empty"><House size={18} /><span>Ce projet est introuvable.</span></div>}
      <p className="detail-footnote"><ArrowRight size={14} /> Une question sur une ligne de dépense ? Ouvrez une nouvelle demande rattachée à ce projet, l’équipe KEMTA vous répond depuis votre espace.</p>
    </DashboardShell>
  );
}

function consumptionPercent(project: ProjectDetail): number {
  const total = Number(project.budget?.total ?? 0);
  const spent = Number(project.budget?.spent ?? 0);
  if (!Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.round((spent / total) * 100));
}
