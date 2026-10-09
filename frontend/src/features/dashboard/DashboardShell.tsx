import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  Bell, BriefcaseBusiness, Building2, Camera, ChevronRight, CircleAlert, ClipboardList,
  FileText, HardHat, House, ListChecks, LogOut, MapPin, Menu, Plus, ShieldCheck, X,
} from 'lucide-react';
import { Brand } from '../../components/Brand';
import type { KemtaUser } from '../../lib/auth';

export type DashboardSpace = 'overview' | 'projects' | 'requests' | 'notifications' | 'help';

function spaceTitleFor(role: KemtaUser['role']): string {
  if (role === 'ADMIN' || role === 'SUPER_ADMIN') return 'Administration';
  if (role === 'BTP_COMPANY') return 'Espace KEMTA BTP';
  if (role === 'PROJECT_MANAGER') return 'Pilotage de chantiers';
  if (role === 'FIELD_AGENT') return 'Espace terrain';
  return 'Espace propriétaire';
}

interface DashboardShellProps {
  user: KemtaUser;
  breadcrumb: string;
  active: DashboardSpace;
  onSignOut: () => void;
  unreadNotifications?: number;
  children: ReactNode;
}

/**
 * Coquille commune des espaces connectés : menu latéral, barre supérieure et en-tête.
 * Chaque page fournit son contenu, ce qui évite de dupliquer la navigation.
 */
export function DashboardShell({ user, breadcrumb, active, onSignOut, unreadNotifications, children }: DashboardShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isAdmin = user.role === 'ADMIN' || user.role === 'SUPER_ADMIN';
  const isBtp = user.role === 'BTP_COMPANY';
  const isManager = user.role === 'PROJECT_MANAGER';
  const isFieldAgent = user.role === 'FIELD_AGENT';
  const spaceTitle = spaceTitleFor(user.role);
  const close = () => setMobileMenuOpen(false);
  const navClass = (key: DashboardSpace) => `dashboard-nav-link${active === key ? ' dashboard-nav-active' : ''}`;

  return (
    <main className="dashboard-app">
      <aside className={`dashboard-sidebar${mobileMenuOpen ? ' dashboard-sidebar-open' : ''}`}>
        <div className="dashboard-brand"><Brand /><button className="dashboard-sidebar-close" onClick={close} aria-label="Fermer la navigation"><X size={19} /></button></div>
        <div className="dashboard-role"><span className="dashboard-role-icon">{isAdmin ? <ShieldCheck size={16} /> : isBtp ? <Building2 size={16} /> : isFieldAgent ? <MapPin size={16} /> : isManager ? <ListChecks size={16} /> : <House size={16} />}</span><span><small>ESPACE</small><strong>{spaceTitle}</strong></span></div>
        <nav className="dashboard-nav" aria-label="Navigation de l’espace">
          <span className="dashboard-nav-caption">MENU PRINCIPAL</span>
          <Link className={navClass('overview')} to="/dashboard" onClick={close}><ClipboardList size={17} /> Vue d’ensemble</Link>
          {isAdmin ? <>
            <a className="dashboard-nav-link" href="/dashboard#admin-demandes"><FileText size={17} /> Demandes</a>
            <a className="dashboard-nav-link" href="/dashboard#admin-projets"><HardHat size={17} /> Projets</a>
            <a className="dashboard-nav-link" href="/dashboard#admin-entreprises"><Building2 size={17} /> Entreprises</a>
            <a className="dashboard-nav-link" href="/dashboard#admin-opportunites"><BriefcaseBusiness size={17} /> Opportunités</a>
          </> : isBtp ? <>
            <a className="dashboard-nav-link" href="/dashboard#btp-company"><Building2 size={17} /> Mon entreprise</a>
            <a className="dashboard-nav-link" href="/dashboard#btp-candidatures"><FileText size={17} /> Candidatures</a>
            <Link className="dashboard-nav-link" to="/opportunites" onClick={close}><BriefcaseBusiness size={17} /> Opportunités</Link>
          </> : isFieldAgent ? <>
            <a className="dashboard-nav-link" href="/dashboard#terrain-taches"><ListChecks size={17} /> Mes tâches</a>
            <a className="dashboard-nav-link" href="/dashboard#terrain-chantiers"><HardHat size={17} /> Mes chantiers</a>
            <a className="dashboard-nav-link" href="/dashboard#terrain-preuves"><Camera size={17} /> Mes preuves</a>
          </> : isManager ? <>
            <a className="dashboard-nav-link" href="/dashboard#pilotage-projets"><HardHat size={17} /> Projets suivis</a>
            <a className="dashboard-nav-link" href="/dashboard#pilotage-taches"><ListChecks size={17} /> Tâches</a>
            <a className="dashboard-nav-link" href="/dashboard#pilotage-preuves"><Camera size={17} /> Preuves terrain</a>
          </> : <>
            <Link className={navClass('projects')} to="/dashboard#client-projets" onClick={close}><HardHat size={17} /> Mes projets</Link>
            <Link className={navClass('requests')} to="/dashboard#client-demandes" onClick={close}><FileText size={17} /> Mes demandes</Link>
            <Link className="dashboard-nav-link" to="/demande" onClick={close}><Plus size={17} /> Demander un service</Link>
          </>}
          <span className="dashboard-nav-caption dashboard-nav-caption-lower">VOTRE COMPTE</span>
          <Link className={navClass('notifications')} to="/dashboard/notifications" onClick={close}>
            <Bell size={17} /> Notifications
            {unreadNotifications ? <span className="nav-badge">{unreadNotifications}</span> : null}
          </Link>
          <Link className={navClass('help')} to="/dashboard#aide" onClick={close}><CircleAlert size={17} /> Aide &amp; support</Link>
        </nav>
        <div className="dashboard-user-card"><span className="user-initials">{(user.first_name[0] ?? 'K').toUpperCase()}{(user.last_name[0] ?? '').toUpperCase()}</span><span className="user-info"><strong>{user.first_name} {user.last_name}</strong><small>{user.phone}</small></span><button type="button" aria-label="Se déconnecter" onClick={onSignOut}><LogOut size={16} /></button></div>
      </aside>
      {mobileMenuOpen && <button className="dashboard-scrim" aria-label="Fermer la navigation" onClick={close} />}
      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <button className="dashboard-menu-button" onClick={() => setMobileMenuOpen(true)} aria-label="Ouvrir la navigation"><Menu size={20} /></button>
          <div className="dashboard-breadcrumb"><Link to="/">KEMTA</Link><ChevronRight size={14} /><span>{breadcrumb}</span></div>
          <div className="dashboard-topbar-right">
            <Link className="topbar-alert" to="/dashboard/notifications" aria-label={`Notifications${unreadNotifications ? ` (${unreadNotifications} non lues)` : ''}`}><Bell size={17} />{unreadNotifications ? <span className="topbar-alert-count">{unreadNotifications}</span> : null}</Link>
            <span className="online-status"><i /> Espace sécurisé</span>
            <span className="topbar-avatar">{(user.first_name[0] ?? 'K').toUpperCase()}</span>
          </div>
        </header>
        <div className="dashboard-content">{children}</div>
      </div>
    </main>
  );
}
