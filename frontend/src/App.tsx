import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { ArrowLeft, ArrowRight, House } from 'lucide-react';
import { Brand } from './components/Brand';
import { LandingPage } from './pages/LandingPage';
import { RequestWizard } from './features/services/RequestWizard';
import { AuthPage } from './features/auth/AuthPage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { ProjectDetailPage } from './features/client/ProjectDetailPage';
import { NotificationsPage } from './features/client/NotificationsPage';
import { OpportunitiesPage } from './features/btp/OpportunitiesPage';
import { CompanyProfilePage, CompanyPublicPage } from './features/btp/CompanyPages';
import { CompanyDocumentsPage, CompanyProfileSetupPage, CompanyVerificationStatusPage } from './features/btp/CompanySetupPages';
import { CompaniesCatalogPage } from './features/btp/CompaniesCatalogPage';
import { LegalPage } from './pages/LegalPage';

export function App() {
  return <Routes>
    <Route path="/" element={<LandingPage />} />
    <Route path="/demande" element={<RequestWizard />} />
    <Route path="/connexion" element={<AuthPage />} />
    <Route path="/inscription" element={<AuthPage />} />
    <Route path="/mot-de-passe-oublie" element={<AuthPage />} />
    <Route path="/dashboard" element={<DashboardPage />} />
    <Route path="/dashboard/projets/:projectId" element={<ProjectDetailPage />} />
    <Route path="/dashboard/notifications" element={<NotificationsPage />} />
    <Route path="/espace-client" element={<Navigate to="/dashboard" replace />} />
    <Route path="/opportunites" element={<OpportunitiesPage />} />
    <Route path="/entreprises-btp" element={<CompaniesCatalogPage />} />
    <Route path="/entreprise/creer" element={<CompanyProfilePage />} />
    <Route path="/entreprise/modifier" element={<CompanyProfilePage />} />
    <Route path="/entreprise/profil" element={<CompanyProfileSetupPage />} />
    <Route path="/entreprise/documents" element={<CompanyDocumentsPage />} />
    <Route path="/entreprise/verification" element={<CompanyVerificationStatusPage />} />
    <Route path="/entreprises/:slug" element={<CompanyPublicPage />} />
    <Route path="/mentions-legales" element={<LegalPage />} />
    <Route path="/confidentialite" element={<LegalPage />} />
    <Route path="/conditions" element={<LegalPage />} />
    <Route path="/faq" element={<Navigate to="/#faq" replace />} />
    <Route path="*" element={<NotFoundPage />} />
  </Routes>;
}

function NotFoundPage() {
  return <main className="not-found-page"><div><Brand /><span className="not-found-code">404</span><h1>Cette page n’est pas disponible.</h1><p>Le lien est peut-être incorrect ou la page a été déplacée.</p><div><Link className="button button-primary" to="/"><House size={16} /> Retour à l’accueil</Link><Link className="text-link" to="/demande"><ArrowLeft size={15} /> Faire une demande</Link></div></div><span className="not-found-mark"><ArrowRight size={120} /></span></main>;
}
