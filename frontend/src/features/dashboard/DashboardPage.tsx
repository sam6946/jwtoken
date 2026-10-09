/** Orchestration du dashboard : session, chargement et choix de la vue par rôle. */
import { useQuery } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { CircleAlert, Info, Plus } from 'lucide-react';
import { ApiError, apiRequest } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { DashboardShell } from './DashboardShell';
import { FieldOperationsDashboard } from '../field-work/FieldOperations';
import {
  AdminDashboard,
  BtpDashboard,
  ClientDashboard,
  DashboardSkeleton,
} from './DashboardRoleViews';
import { type DashboardResponse } from './dashboardTypes';

export function DashboardPage() {
  const { user, isReady, signOut, sessionLost } = useAuth();
  const navigate = useNavigate();
  const dashboardQuery = useQuery({
    queryKey: ['dashboard', user?.id],
    // Le jeton est appliqué par le client API lui-même : une seule source de vérité.
    queryFn: () => apiRequest<DashboardResponse>('/dashboard/'),
    enabled: Boolean(user && isReady),
    staleTime: 60_000,
    retry: 1,
  });
  const sessionExpired = dashboardQuery.error instanceof ApiError && dashboardQuery.error.status === 401;



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
      {response && (isAdmin
        ? <AdminDashboard data={response} />
        : isBtp
          ? <BtpDashboard data={response} />
          : isManager
            ? <FieldOperationsDashboard manager />
            : isFieldAgent
              ? <FieldOperationsDashboard manager={false} />
              : <ClientDashboard data={response} />)}
    </DashboardShell>
  );
}
