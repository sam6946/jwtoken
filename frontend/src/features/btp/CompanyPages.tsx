import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, BadgeCheck, Building2, Camera, CheckCircle2,
  Globe2, MapPin, ShieldCheck, Wrench,
} from 'lucide-react';
import { SiteHeader } from '../../components/SiteHeader';
import { SiteFooter } from '../../components/SiteFooter';
import { ApiError, apiRequest, jsonBody } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { verificationTones } from './companyVerification';

interface CompanyProfile {
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
  verification_status: 'DRAFT' | 'PENDING' | 'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED';
  verification_status_label: string;
  verification_level_label: string;
  portfolio: PortfolioItem[];
}
interface PortfolioItem {
  id: number;
  title: string;
  description: string;
  project_type: string;
  city: string;
  image_url: string | null;
}
interface CompanyForm {
  name: string;
  city: string;
  description: string;
  servicesText: string;
  areasText: string;
  yearsExperience: string;
}
const emptyForm: CompanyForm = { name: '', city: '', description: '', servicesText: '', areasText: '', yearsExperience: '' };

function parseList(value: string): string[] {
  return value.split(/[,;\n]/).map((entry) => entry.trim()).filter(Boolean).slice(0, 20);
}

export function CompanyProfilePage() {
  const { user, isReady } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CompanyForm>(emptyForm);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const companyQuery = useQuery({
    queryKey: ['company-profile', user?.id],
    queryFn: () => apiRequest<CompanyProfile>('/companies/me/'),
    enabled: Boolean(user && user.role === 'BTP_COMPANY'),
    retry: (failureCount, caught) => !(caught instanceof ApiError && caught.status === 404) && failureCount < 2,
  });

  useEffect(() => {
    const company = companyQuery.data;
    if (!company) return;
    setForm({
      name: company.name,
      city: company.city,
      description: company.description,
      servicesText: company.services.join(', '),
      areasText: company.intervention_areas.join(', '),
      yearsExperience: String(company.years_experience || ''),
    });
  }, [companyQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => apiRequest<CompanyProfile>('/companies/me/', {
      method: 'PUT',
      body: jsonBody({
        name: form.name.trim(),
        city: form.city.trim(),
        description: form.description.trim(),
        services: parseList(form.servicesText),
        intervention_areas: parseList(form.areasText),
        years_experience: Number(form.yearsExperience || 0),
      }),
    }),
    onSuccess: async () => {
      setSaved(true);
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      await queryClient.invalidateQueries({ queryKey: ['company-profile'] });
      navigate('/dashboard');
    },
    onError: (caught) => setError(caught instanceof ApiError ? caught.message : 'Le profil n’a pas pu être enregistré.'),
  });

  if (!isReady) return <div className="app-loading"><span className="loading-mark" /><p>Chargement…</p></div>;
  if (!user) return <Navigate to="/connexion?next=%2Fentreprise%2Fcreer" replace />;
  if (user.role !== 'BTP_COMPANY') return <div className="access-denied"><ShieldCheck size={26} /><h1>Espace réservé aux entreprises</h1><p>Créez un compte KEMTA BTP pour présenter votre entreprise et vos réalisations.</p><Link className="button button-primary" to="/inscription?role=BTP_COMPANY">Créer un compte entreprise <ArrowRight size={16} /></Link></div>;
  const isExisting = Boolean(companyQuery.data);
  const verification = companyQuery.data
    ? {
        status: companyQuery.data.verification_status,
        label: companyQuery.data.verification_status_label,
        level: companyQuery.data.verification_level_label,
      }
    : null;

  function update(key: keyof CompanyForm, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  return <><SiteHeader /><main className="company-edit-page"><div className="page-container company-edit-container"><Link to="/dashboard" className="back-to-home"><ArrowLeft size={15} /> Retour à mon espace</Link><div className="company-edit-heading"><span className="section-kicker">KEMTA BTP · Mon profil</span><h1>{isExisting ? 'Faites évoluer votre vitrine.' : 'Présentez votre entreprise.'}</h1><p>Donnez aux clients une vue claire de votre expertise, de vos services et de vos zones d’intervention.</p></div>
    {verification && <p className={`company-verification-banner status-${verificationTones[verification.status]}`} role="status"><BadgeCheck size={16} /><span><strong>{verification.label}</strong><small>{verification.level}</small></span>{verification.status !== 'VERIFIED' && <Link to="/entreprise/verification">Suivre ma vérification <ArrowRight size={15} /></Link>}</p>}
    {companyQuery.isLoading && <div className="company-form-loading"><span /> Chargement du profil…</div>}
    {companyQuery.isError && !(companyQuery.error instanceof ApiError && companyQuery.error.status === 404) && <div className="form-error" role="alert">Impossible de charger les informations de l’entreprise. <button onClick={() => void companyQuery.refetch()}>Réessayer</button></div>}
    {(!companyQuery.isLoading && (!companyQuery.isError || (companyQuery.error instanceof ApiError && companyQuery.error.status === 404))) && <div className="company-form-layout"><form className="company-form" onSubmit={(event) => { event.preventDefault(); if (!form.name.trim() || !form.city.trim() || form.description.trim().length < 20) { setError('Renseignez le nom, la ville et une présentation d’au moins 20 caractères.'); return; } void saveMutation.mutate(); }}>
      <div className="company-form-section"><div className="company-form-section-title"><span>01</span><div><h2>Informations de base</h2><p>Les éléments indispensables de votre profil public.</p></div></div><div className="form-grid form-grid-two"><label className="field field-full"><span>Nom de l’entreprise <b>*</b></span><input value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="Ex. Bâtir & Rénover" maxLength={120} /></label><label className="field field-full"><span>Ville principale <b>*</b></span><input value={form.city} onChange={(event) => update('city', event.target.value)} placeholder="Ex. Douala" maxLength={100} /></label><label className="field field-full"><span>Présentation <b>*</b></span><textarea rows={5} value={form.description} onChange={(event) => update('description', event.target.value)} placeholder="Présentez votre entreprise, votre expérience et votre façon de travailler…" maxLength={1800} /><small>{form.description.length}/1 800 caractères</small></label><label className="field"><span>Années d’expérience</span><input type="number" min="0" max="80" value={form.yearsExperience} onChange={(event) => update('yearsExperience', event.target.value)} placeholder="Ex. 8" /></label></div></div>
      <div className="company-form-section"><div className="company-form-section-title"><span>02</span><div><h2>Votre expertise</h2><p>Séparez les éléments par une virgule.</p></div></div><div className="form-grid"><label className="field field-full"><span>Services proposés</span><textarea rows={3} value={form.servicesText} onChange={(event) => update('servicesText', event.target.value)} placeholder="Gros œuvre, rénovation, plomberie…" /></label><label className="field field-full"><span>Zones d’intervention</span><textarea rows={2} value={form.areasText} onChange={(event) => update('areasText', event.target.value)} placeholder="Douala, Yaoundé, Kribi…" /></label></div></div>
      {error && <p className="form-error" role="alert">{error}</p>}{saved && <p className="form-notice" role="status">Profil enregistré avec succès.</p>}
      <div className="company-form-actions"><Link className="button button-outline" to="/dashboard">Annuler</Link><button className="button button-primary" type="submit" disabled={saveMutation.isPending}>{saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer mon profil'} <ArrowRight size={16} /></button></div>
    </form><aside className="company-form-aside"><div className="company-profile-preview"><div className="preview-company-cover"><span className="preview-company-logo"><Building2 size={22} /></span><span className="preview-company-badge"><BadgeCheck size={14} /> Profil KEMTA</span></div><div className="preview-company-content"><span className="preview-company-label">APERÇU DE VOTRE VITRINE</span><h3>{form.name || 'Nom de votre entreprise'}</h3><span className="preview-company-city"><MapPin size={13} /> {form.city || 'Votre ville'}</span><p>{form.description || 'Votre présentation apparaîtra ici et permettra aux clients de découvrir votre savoir-faire.'}</p><div className="preview-company-services">{parseList(form.servicesText).slice(0, 3).map((service) => <span key={service}>{service}</span>)}{!form.servicesText && <span>Vos services</span>}</div><div className="preview-company-footer"><span><ShieldCheck size={14} /> Vérification après soumission</span><ArrowRight size={15} /></div></div></div><div className="company-form-tip"><span><CheckCircle2 size={17} /></span><p><strong>Un profil utile est un profil précis.</strong><br />Décrivez vos réalisations et votre périmètre d’intervention. Le badge vérifié est attribué après examen par KEMTA.</p></div></aside></div>}
    </div></main><SiteFooter /></>;
}

export function CompanyPublicPage() {
  const { slug } = useParams();
  const companyQuery = useQuery({
    queryKey: ['public-company', slug],
    queryFn: () => apiRequest<CompanyProfile>(`/companies/${encodeURIComponent(slug ?? '')}/`),
    enabled: Boolean(slug),
    staleTime: 5 * 60_000,
  });
  const company = companyQuery.data;

  return <><SiteHeader /><main className="company-public-page"><div className="company-public-cover"><div className="page-container"><Link to="/" className="company-back"><ArrowLeft size={15} /> Retour à KEMTA</Link></div></div><div className="page-container company-public-container">
    {companyQuery.isLoading && <div className="company-form-loading"><span /> Chargement du profil…</div>}
    {companyQuery.isError && <div className="public-company-error"><Building2 size={28} /><h1>Profil introuvable</h1><p>Cette entreprise n’est pas disponible ou son profil n’est pas public.</p><Link className="button button-primary" to="/opportunites">Découvrir les opportunités <ArrowRight size={15} /></Link></div>}
    {company && <><div className="company-public-header"><span className="company-public-logo"><Building2 size={27} /></span><div className="company-public-title"><h1>{company.name}</h1><span className="company-public-location"><MapPin size={14} /> {company.city} · Cameroun</span></div>{company.verified && <span className="verified-label verified-label-large"><BadgeCheck size={16} /> Entreprise vérifiée</span>}</div><div className="company-public-layout"><article className="company-public-main"><section><span className="section-kicker">À propos</span><h2>Une expertise de terrain.</h2><p>{company.description}</p></section><section className="company-services-section"><span className="section-kicker">Nos services</span><div className="public-service-tags">{company.services.map((service) => <span key={service}><Wrench size={14} /> {service}</span>)}</div></section><section className="company-portfolio-section"><div className="company-section-heading"><div><span className="section-kicker">Réalisations</span><h2>Projets & savoir-faire</h2></div><Camera size={19} /></div>{company.portfolio.length ? <div className="portfolio-grid">{company.portfolio.map((project) => <article className="portfolio-card" key={project.id}>{project.image_url ? <img src={project.image_url} alt={project.title} loading="lazy" /> : <div className="portfolio-placeholder"><Building2 size={26} /></div>}<div><small>{project.project_type} · {project.city}</small><h3>{project.title}</h3><p>{project.description}</p></div></article>)}</div> : <div className="small-empty"><Camera size={18} /><span>Les réalisations seront ajoutées au profil de l’entreprise.</span></div>}</section></article><aside className="company-public-aside"><div className="public-company-info"><h3>En un coup d’œil</h3><div><Globe2 size={16} /><span><small>Zone d’intervention</small><strong>{company.intervention_areas.join(', ') || company.city}</strong></span></div><div><Wrench size={16} /><span><small>Expérience</small><strong>{company.years_experience ? `${company.years_experience} ans` : 'À préciser'}</strong></span></div><div><CheckCircle2 size={16} /><span><small>Profil</small><strong>{company.verified ? 'Vérifié par KEMTA' : 'En cours de vérification'}</strong></span></div><Link className="button button-primary" to="/demande">Demander une mise en relation <ArrowRight size={15} /></Link></div><p className="public-company-note"><ShieldCheck size={15} /> KEMTA présente les informations fournies par les entreprises. Les détails d’une réalisation sont à vérifier dans le cadre du projet.</p></aside></div></>}
  </div></main><SiteFooter /></>;
}
