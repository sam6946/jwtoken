import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, ArrowUpRight, BriefcaseBusiness, CalendarDays,
  CheckCircle2, MapPin, X,
} from 'lucide-react';
import { SiteHeader } from '../../components/SiteHeader';
import { SiteFooter } from '../../components/SiteFooter';
import { ApiError, apiRequest, jsonBody } from '../../lib/api';
import { useAuth } from '../../lib/auth';

interface Opportunity {
  id: number;
  title: string;
  project_type: string;
  city: string;
  budget_min: string | null;
  budget_max: string | null;
  deadline: string;
  description: string;
  created_at: string;
}
interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }

function formatBudget(min: string | null, max: string | null): string {
  if (!min && !max) return 'Budget à préciser';
  const format = (value: string) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(Number(value));
  if (min && max) return `${format(min)} – ${format(max)} FCFA`;
  return `${format(min ?? max ?? '0')} FCFA${min ? ' +' : ' max'}`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function OpportunitiesPage() {
  const { user, isReady } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [message, setMessage] = useState('');
  const [estimatedBudget, setEstimatedBudget] = useState('');
  const [durationDays, setDurationDays] = useState('');
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const opportunitiesQuery = useQuery({
    queryKey: ['opportunities', 'open'],
    queryFn: () => apiRequest<Paginated<Opportunity>>('/opportunities/?status=OPEN'),
    staleTime: 3 * 60_000,
  });
  const applyMutation = useMutation({
    mutationFn: () => apiRequest('/applications/', {
      method: 'POST',
      body: jsonBody({ opportunity: selected?.id, message, estimated_budget: estimatedBudget || null, duration_days: durationDays ? Number(durationDays) : null }),
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setSelected(null);
      setMessage('');
      setEstimatedBudget('');
      setDurationDays('');
      setError('');
      setSuccessMessage('Votre candidature a bien été envoyée. Vous pourrez suivre son statut dans votre espace entreprise.');
    },
    onError: (caught) => setError(caught instanceof ApiError ? caught.message : 'La candidature n’a pas pu être envoyée.'),
  });

  function beginApplication(opportunity: Opportunity): void {
    setError('');
    if (!user) { navigate(`/connexion?next=${encodeURIComponent('/opportunites')}`); return; }
    if (user.role !== 'BTP_COMPANY') { setError('Les candidatures sont réservées aux comptes entreprise KEMTA BTP.'); return; }
    setSelected(opportunity);
  }

  return <>
    <SiteHeader />
    <main className="opportunities-page">
      <section className="opportunities-hero"><div className="page-container opportunities-hero-inner"><Link to="/" className="back-to-home"><ArrowLeft size={15} /> Accueil</Link><span className="section-kicker">Pour les entreprises BTP</span><h1>Des opportunités<br /><em>à construire.</em></h1><p>Parcourez les projets immobiliers ouverts aux candidatures et répondez avec une proposition claire, depuis votre espace KEMTA BTP.</p><Link to={user?.role === 'BTP_COMPANY' ? '/dashboard' : '/inscription?role=BTP_COMPANY'} className="button button-light button-large">{user?.role === 'BTP_COMPANY' ? 'Accéder à mon espace' : 'Créer mon profil entreprise'} <ArrowUpRight size={17} /></Link><div className="opportunities-hero-art"><span className="opportunities-art-mark"><BriefcaseBusiness size={26} /></span><span className="opportunities-art-line" /><span className="opportunities-art-caption">Un espace clair<br />pour répondre aux projets.</span></div></div></section>
      <section className="section opportunities-list-section"><div className="page-container"><div className="opportunities-list-heading"><div><span className="section-kicker">Appels ouverts</span><h2>Projets à découvrir</h2><p>Chaque opportunité précise le besoin, la localisation et la date limite de candidature.</p></div><span className="opportunity-count"><BriefcaseBusiness size={17} /> {opportunitiesQuery.data?.count ?? 0} opportunité{opportunitiesQuery.data?.count === 1 ? '' : 's'}</span></div>
        {successMessage && <p className="form-notice opportunity-success" role="status"><CheckCircle2 size={16} /> {successMessage}</p>}
        {opportunitiesQuery.isLoading && <div className="opportunities-loading"><span /><span /><span /></div>}
        {opportunitiesQuery.isError && <div className="opportunity-empty"><span className="empty-icon"><BriefcaseBusiness size={22} /></span><strong>Les opportunités ne sont pas disponibles.</strong><p>Réessayez dans un instant.</p><button className="button button-outline" onClick={() => void opportunitiesQuery.refetch()}>Réessayer</button></div>}
        {opportunitiesQuery.data?.results.length === 0 && <div className="opportunity-empty"><span className="empty-icon"><BriefcaseBusiness size={22} /></span><strong>Aucun appel ouvert pour le moment.</strong><p>Les projets seront publiés ici dès qu’ils seront prêts à recevoir des candidatures.</p><Link className="button button-outline" to="/inscription?role=BTP_COMPANY">Créer mon espace entreprise <ArrowRight size={15} /></Link></div>}
        {opportunitiesQuery.data?.results.length ? <div className="opportunity-list">{opportunitiesQuery.data.results.map((opportunity) => <article className="opportunity-card" key={opportunity.id}><div className="opportunity-card-top"><span className="opportunity-category">{opportunity.project_type || 'Projet immobilier'}</span><span className="opportunity-open"><i /> Candidatures ouvertes</span></div><h3>{opportunity.title}</h3><p className="opportunity-description">{opportunity.description}</p><div className="opportunity-facts"><span><MapPin size={15} /> {opportunity.city}</span><span><CalendarDays size={15} /> Limite : {formatDate(opportunity.deadline)}</span><span><BriefcaseBusiness size={15} /> {formatBudget(opportunity.budget_min, opportunity.budget_max)}</span></div><div className="opportunity-card-bottom"><span>Une proposition claire renforce votre candidature.</span><button className="button button-primary" onClick={() => beginApplication(opportunity)}>Voir & candidater <ArrowRight size={15} /></button></div></article>)}</div> : null}
        {error && !selected && <p className="form-error" role="alert">{error}</p>}
      </div></section>
      <section className="opportunities-how"><div className="page-container opportunities-how-inner"><div><span className="section-kicker">Une candidature simple</span><h2>Montrez ce que<br />vous savez faire.</h2></div><div className="application-steps"><div><span>01</span><strong>Consultez le projet</strong><small>Budget, lieu et délai.</small></div><div><span>02</span><strong>Présentez votre approche</strong><small>Expérience et proposition.</small></div><div><span>03</span><strong>Suivez la réponse</strong><small>Chaque statut est visible.</small></div></div></div></section>
    </main>
    <SiteFooter />
    {selected && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}><section className="application-modal" role="dialog" aria-modal="true" aria-labelledby="application-title"><button className="modal-close" onClick={() => setSelected(null)} aria-label="Fermer"><X size={19} /></button><span className="section-kicker">Candidature entreprise</span><h2 id="application-title">{selected.title}</h2><div className="application-opportunity-facts"><span><MapPin size={14} /> {selected.city}</span><span><CalendarDays size={14} /> Limite : {formatDate(selected.deadline)}</span></div><p className="application-modal-copy">Présentez votre approche et les éléments qui rendent votre entreprise adaptée à ce projet.</p><label className="field"><span>Votre présentation <b>*</b></span><textarea rows={4} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Équipe, expérience pertinente, méthode et compréhension du besoin…" /></label><div className="form-grid form-grid-two"><label className="field"><span>Budget estimatif <small>(FCFA)</small></span><input inputMode="numeric" value={estimatedBudget} onChange={(event) => setEstimatedBudget(event.target.value.replace(/[^0-9]/g, ''))} placeholder="Montant proposé" /></label><label className="field"><span>Délai estimatif <small>(jours)</small></span><input type="number" min="1" value={durationDays} onChange={(event) => setDurationDays(event.target.value)} placeholder="Ex. 90" /></label></div><p className="application-note"><CheckCircle2 size={15} /> Les documents et réalisations complémentaires pourront être ajoutés depuis votre espace.</p>{error && <p className="form-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button button-outline" onClick={() => setSelected(null)}>Annuler</button><button className="button button-primary" disabled={applyMutation.isPending || message.trim().length < 8} onClick={() => applyMutation.mutate()}>{applyMutation.isPending ? 'Envoi…' : 'Envoyer ma candidature'} <ArrowRight size={15} /></button></div></section></div>}
    {!isReady && <div className="auth-readiness" aria-live="polite">Chargement de votre session…</div>}
  </>;
}
