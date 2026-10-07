import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import {
  ArrowRight, Bell, BellRing, Check, CheckCheck, CircleAlert, HardHat, Info, ShieldCheck,
} from 'lucide-react';
import { ApiError, apiRequest, jsonBody } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { DashboardShell } from '../dashboard/DashboardShell';
import { dateLabel } from '../dashboard/dashboardData';

interface NotificationItem {
  id: number;
  notification_type: string;
  title: string;
  body: string;
  action_url: string;
  data: Record<string, unknown>;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

interface Paginated<T> {
  count: number;
  results: T[];
}

const typeLabels: Record<string, string> = {
  PROJECT: 'Projet',
  TASK: 'Tâche',
  EVIDENCE: 'Preuve terrain',
  PAYMENT: 'Paiement',
  SUBSCRIPTION: 'Abonnement',
  APPLICATION: 'Candidature',
  OPPORTUNITY: 'Opportunité',
  SECURITY: 'Sécurité',
  GENERAL: 'Général',
};

type NoticeFilter = 'all' | 'unread';

/** Journal des notifications de l'utilisateur, avec marquage lu individuel ou global. */
export function NotificationsPage() {
  const { user, isReady, signOut } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<NoticeFilter>('all');
  const [actionError, setActionError] = useState<string | null>(null);

  const notificationsQuery = useQuery({
    queryKey: ['notifications'],
    queryFn: () => apiRequest<Paginated<NotificationItem>>('/notifications/?page_size=100'),
    enabled: Boolean(user && isReady),
  });

  const markRead = useMutation({
    mutationFn: (id: number) => apiRequest<NotificationItem>(`/notifications/${id}/mark-read/`, { method: 'POST' }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['notifications'] }); void queryClient.invalidateQueries({ queryKey: ['dashboard'] }); },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'La notification n’a pas pu être mise à jour.'),
  });

  const markAllRead = useMutation({
    mutationFn: () => apiRequest<{ updated: number }>('/notifications/mark-all-read/', { method: 'POST', body: jsonBody({}) }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['notifications'] }); void queryClient.invalidateQueries({ queryKey: ['dashboard'] }); },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Les notifications n’ont pas pu être mises à jour.'),
  });

  const items = notificationsQuery.data?.results ?? [];
  const unreadCount = items.filter((item) => !item.is_read).length;
  const visible = useMemo(() => (filter === 'unread' ? items.filter((item) => !item.is_read) : items), [filter, items]);

  async function handleSignOut(): Promise<void> {
    await signOut();
    navigate('/');
  }

  function openNotification(item: NotificationItem): void {
    if (!item.is_read) markRead.mutate(item.id);
    const target = item.action_url && item.action_url.startsWith('/') ? item.action_url : '/dashboard';
    navigate(target);
  }

  if (!isReady) return <div className="app-loading"><span className="loading-mark" /><p>Préparation de votre espace…</p></div>;
  if (!user) return <Navigate to="/connexion?next=%2Fdashboard%2Fnotifications" replace />;

  return (
    <DashboardShell user={user} breadcrumb="Notifications" active="notifications" onSignOut={() => void handleSignOut()} unreadNotifications={unreadCount}>
      <div className="dashboard-page-heading">
        <div>
          <span className="dashboard-eyebrow">Votre compte</span>
          <h1>Notifications</h1>
          <p>{unreadCount > 0 ? `${unreadCount} notification${unreadCount === 1 ? '' : 's'} non lue${unreadCount === 1 ? '' : 's'}.` : 'Vous êtes à jour : aucune notification non lue.'}</p>
        </div>
        <button type="button" className="button button-outline button-small" disabled={markAllRead.isPending || unreadCount === 0} onClick={() => markAllRead.mutate()}>
          <CheckCheck size={16} /> {markAllRead.isPending ? 'Mise à jour…' : 'Tout marquer comme lu'}
        </button>
      </div>

      <div className="notice-filters" role="tablist" aria-label="Filtrer les notifications">
        <button type="button" role="tab" aria-selected={filter === 'all'} className={filter === 'all' ? 'notice-filter-active' : ''} onClick={() => setFilter('all')}>Toutes ({items.length})</button>
        <button type="button" role="tab" aria-selected={filter === 'unread'} className={filter === 'unread' ? 'notice-filter-active' : ''} onClick={() => setFilter('unread')}>Non lues ({unreadCount})</button>
      </div>

      {actionError && <div className="dashboard-alert"><CircleAlert size={17} /><span>{actionError}</span></div>}

      {notificationsQuery.isLoading && <div className="dashboard-skeleton" aria-label="Chargement des notifications"><div /><div /><div /></div>}
      {notificationsQuery.isError && <div className="dashboard-error"><CircleAlert size={22} /><div><strong>Vos notifications ne peuvent pas être chargées.</strong><p>{notificationsQuery.error instanceof ApiError ? notificationsQuery.error.message : 'Vérifiez votre connexion puis réessayez.'}</p><button className="button button-outline button-small" onClick={() => void notificationsQuery.refetch()}>Réessayer</button></div></div>}

      {!notificationsQuery.isLoading && !notificationsQuery.isError && (visible.length ? <div className="notice-list">
        {visible.map((item) => <article className={`notice-card${item.is_read ? '' : ' notice-unread'}`} key={item.id}>
          <span className="notice-icon">{item.is_read ? <Bell size={17} /> : <BellRing size={17} />}</span>
          <div className="notice-body">
            <div className="notice-meta"><span className="notice-type">{typeLabels[item.notification_type] ?? item.notification_type}</span><span>{dateLabel(item.created_at)}</span>{!item.is_read && <span className="notice-pill">Non lue</span>}</div>
            <strong>{item.title}</strong>
            {item.body && <p>{item.body}</p>}
            <div className="notice-actions">
              {item.action_url?.startsWith('/') && <button type="button" className="text-link" onClick={() => openNotification(item)}>Ouvrir <ArrowRight size={14} /></button>}
              {!item.is_read && <button type="button" className="text-quiet" disabled={markRead.isPending} onClick={() => markRead.mutate(item.id)}><Check size={14} /> Marquer comme lue</button>}
            </div>
          </div>
        </article>)}
      </div> : <div className="dashboard-empty"><span className="empty-icon"><Info size={22} /></span><div><strong>{filter === 'unread' ? 'Aucune notification non lue.' : 'Aucune notification pour le moment.'}</strong><p>Vous serez averti ici des avancées de vos chantiers, des demandes de service et des échanges avec l’équipe KEMTA.</p><Link className="text-link" to="/dashboard">Revenir à mes projets <HardHat size={15} /></Link></div></div>)}

      <p className="detail-footnote"><ShieldCheck size={14} /> Les notifications sont conservées dans votre espace : elles ne remplacent pas les documents officiels de votre projet.</p>
    </DashboardShell>
  );
}
