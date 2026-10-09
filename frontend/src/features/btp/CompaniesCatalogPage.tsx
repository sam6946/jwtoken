import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight, BadgeCheck, Building2, MapPin, Search, ShieldCheck,
} from 'lucide-react';
import { SiteHeader } from '../../components/SiteHeader';
import { SiteFooter } from '../../components/SiteFooter';
import { apiRequest } from '../../lib/api';

interface PublicCompany {
  id: number;
  name: string;
  slug: string;
  description: string;
  city: string;
  services: string[];
  intervention_areas: string[];
  years_experience: number;
  verified: boolean;
  profile_completion: number;
  views_count: number;
}
interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }

export function CompaniesCatalogPage() {
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const catalogQuery = useQuery({
    queryKey: ['companies-catalog', search, page],
    queryFn: () => apiRequest<Paginated<PublicCompany>>(`/companies/?page_size=12&page=${page}${search ? `&search=${encodeURIComponent(search)}` : ''}`),
    staleTime: 5 * 60_000,
  });

  return <><SiteHeader /><main className="catalog-page"><section className="catalog-hero"><div className="page-container catalog-hero-inner"><span className="section-kicker">KEMTA BTP · Catalogue</span><h1>Les professionnels<br /><em>du bâtiment.</em></h1><p>Découvrez les entreprises qui présentent leurs services et leurs réalisations sur KEMTA BTP.</p><div className="catalog-trust-note"><ShieldCheck size={16} /> Les profils publics sont vérifiés par l’équipe KEMTA.</div><div className="catalog-hero-mark"><Building2 size={42} /><span>Des compétences<br />au service de vos projets.</span></div></div></section><section className="catalog-list-section"><div className="page-container"><div className="catalog-heading"><div><span className="section-kicker">Trouver un professionnel</span><h2>Entreprises BTP</h2><p>Consultez les services et contactez une entreprise pour votre projet.</p></div><span className="catalog-count"><Building2 size={16} /> {catalogQuery.data?.count ?? 0} profil{catalogQuery.data?.count === 1 ? '' : 's'} public{catalogQuery.data?.count === 1 ? '' : 's'}</span></div><label className="catalog-search"><Search size={18} /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Rechercher par entreprise ou ville…" aria-label="Rechercher une entreprise BTP par nom ou ville" /><span>Douala · Yaoundé · Kribi</span></label>
    {catalogQuery.isLoading && <div className="catalog-grid catalog-skeleton"><span /><span /><span /></div>}
    {catalogQuery.isError && <div className="catalog-empty"><span className="catalog-empty-icon"><Building2 size={22} /></span><strong>Le catalogue est momentanément indisponible.</strong><p>Réessayez dans un instant.</p><button className="button button-outline" onClick={() => void catalogQuery.refetch()}>Réessayer</button></div>}
    {catalogQuery.data?.results.length === 0 && <div className="catalog-empty"><span className="catalog-empty-icon"><Search size={22} /></span><strong>{search ? 'Aucun profil ne correspond à cette recherche.' : 'Aucun profil public pour le moment.'}</strong><p>{search ? 'Essayez un autre nom ou une autre ville.' : 'Les profils apparaîtront ici après vérification par l’équipe KEMTA.'}</p>{search && <button className="button button-outline" onClick={() => { setSearchInput(''); setSearch(''); }}>Effacer la recherche</button>}</div>}
    {catalogQuery.data?.results.length ? <div className="catalog-grid">{catalogQuery.data.results.map((company) => <article className="catalog-company-card" key={company.id}><div className="catalog-company-top"><span className="catalog-company-logo"><Building2 size={23} /></span><span className="catalog-verified"><BadgeCheck size={14} /> Vérifiée</span></div><h3>{company.name}</h3><span className="catalog-company-location"><MapPin size={14} /> {company.city}</span><p>{company.description}</p><div className="catalog-services">{company.services.slice(0, 3).map((service) => <span key={service}>{service}</span>)}{company.services.length > 3 && <small>+{company.services.length - 3}</small>}</div><div className="catalog-company-bottom"><span>{company.years_experience ? `${company.years_experience} ans d’expérience` : 'Professionnel BTP'}</span><Link to={`/entreprises/${company.slug}`}>Voir le profil <ArrowRight size={14} /></Link></div></article>)}</div> : null}
    {catalogQuery.data && catalogQuery.data.count > 12 && <div className="catalog-pagination"><button className="button button-outline button-small" disabled={!catalogQuery.data.previous} onClick={() => setPage((current) => Math.max(1, current - 1))}>Précédent</button><span>Page {page}</span><button className="button button-outline button-small" disabled={!catalogQuery.data.next} onClick={() => setPage((current) => current + 1)}>Suivant <ArrowRight size={14} /></button></div>}
    <div className="catalog-join"><div><span className="section-kicker">Vous êtes un professionnel ?</span><h2>Votre expertise mérite une belle vitrine.</h2><p>Créez un profil entreprise et préparez votre dossier de vérification.</p></div><Link className="button button-primary" to="/inscription?role=BTP_COMPANY">Rejoindre KEMTA BTP <ArrowRight size={16} /></Link></div>
  </div></section></main><SiteFooter /></>;
}
