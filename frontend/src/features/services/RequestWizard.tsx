import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, FileText, HardHat,
  House, MapPin, RotateCcw, Upload, X,
} from 'lucide-react';
import { apiRequest, ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { Brand } from '../../components/Brand';

interface WizardProject {
  id: number;
  name: string;
  city: string;
  project_type: string;
  progress: number;
  current_phase: string;
  status: string;
}

type ServiceKind = 'BUILD' | 'TAKEOVER' | 'MAINTENANCE' | 'OTHER';
type WizardStage = 'service' | 'project' | 'contact' | 'details' | 'context' | 'review' | 'sent';

interface FormState {
  firstName: string;
  lastName: string;
  phone: string;
  email: string;
  city: string;
  projectType: string;
  budget: string;
  desiredDate: string;
  progress: string;
  currentCompany: string;
  spent: string;
  propertyType: string;
  occupancy: string;
  lastVisit: string;
  frequency: string;
  maintenanceServices: string[];
  description: string;
  expectations: string;
}

interface RequestResult {
  id: number;
  request_code: string;
  status: string;
  created_at: string;
}

const initialForm: FormState = {
  firstName: '', lastName: '', phone: '', email: '', city: '', projectType: '',
  budget: '', desiredDate: '', progress: '', currentCompany: '', spent: '',
  propertyType: '', occupancy: '', lastVisit: '', frequency: '',
  maintenanceServices: [], description: '', expectations: '',
};

const serviceOptions: Array<{ type: ServiceKind; icon: typeof HardHat; title: string; description: string }> = [
  { type: 'BUILD', icon: HardHat, title: 'Construire', description: 'Être accompagné de la préparation à la livraison.' },
  { type: 'TAKEOVER', icon: MapPin, title: 'Suivre un chantier', description: 'Reprendre le suivi d’un chantier déjà démarré.' },
  { type: 'MAINTENANCE', icon: House, title: 'Entretenir un bien', description: 'Organiser une visite, un entretien ou une réparation.' },
  { type: 'OTHER', icon: FileText, title: 'Autre besoin', description: 'Poser une question ou décrire une autre demande.' },
];

const stepLabels = ['Votre besoin', 'Projet concerné', 'Vos coordonnées', 'Votre projet', 'Précisions', 'Récapitulatif'];

function serviceName(kind: ServiceKind | null): string {
  return serviceOptions.find((service) => service.type === kind)?.title ?? 'Choisir un service';
}

function formatMoney(value: string): string {
  if (!value) return 'Non précisé';
  const numeric = Number(value.replace(/\D/g, ''));
  return numeric ? `${new Intl.NumberFormat('fr-FR').format(numeric)} FCFA` : value;
}

export function RequestWizard() {
  const [searchParams] = useSearchParams();
  const { user, isReady } = useAuth();
  const initialService = searchParams.get('service')?.toUpperCase();
  const requestedProjectId = Number(searchParams.get('projet') ?? '') || null;
  const [kind, setKind] = useState<ServiceKind | null>(
    initialService === 'BUILD' || initialService === 'TAKEOVER' || initialService === 'MAINTENANCE' || initialService === 'OTHER' ? initialService : null,
  );
  const [stage, setStage] = useState<WizardStage>(initialService ? 'contact' : 'service');
  const [form, setForm] = useState<FormState>(initialForm);
  // Projet du propriétaire auquel la demande se rattache (facultatif : « un autre bien »).
  const [projectId, setProjectId] = useState<number | null>(requestedProjectId);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestResult, setRequestResult] = useState<RequestResult | null>(null);

  const projectsQuery = useQuery({
    queryKey: ['wizard-projects', user?.id],
    queryFn: () => apiRequest<{ results?: WizardProject[] } | WizardProject[]>('/projects/'),
    enabled: Boolean(user && isReady),
  });
  const myProjects: WizardProject[] = useMemo(() => {
    const payload = projectsQuery.data;
    if (!payload) return [];
    return Array.isArray(payload) ? payload : payload.results ?? [];
  }, [projectsQuery.data]);

  // Un utilisateur connecté retrouve ses coordonnées et peut rattacher sa demande à un chantier.
  useEffect(() => {
    if (!user) return;
    setForm((current) => ({
      ...current,
      firstName: current.firstName || user.first_name,
      lastName: current.lastName || user.last_name,
      phone: current.phone || user.phone.replace(/^\+237/, '').replace(/\D/g, '').slice(-9),
      email: current.email || (user.email ?? ''),
    }));
  }, [user]);

  const activeIndex = stage === 'service' ? 0 : stage === 'project' ? 1 : stage === 'contact' ? 2 : stage === 'details' ? 3 : stage === 'context' ? 4 : 5;
  const percent = stage === 'sent' ? 100 : Math.max(12, Math.round(((activeIndex + 1) / stepLabels.length) * 100));
  const update = (key: keyof FormState, value: string | string[]) => setForm((current) => ({ ...current, [key]: value }));
  const toggleService = (service: string) => setForm((current) => ({
    ...current,
    maintenanceServices: current.maintenanceServices.includes(service)
      ? current.maintenanceServices.filter((item) => item !== service)
      : [...current.maintenanceServices, service],
  }));

  const detailsSummary = useMemo<Array<[string, string]>>(() => {
    if (kind === 'TAKEOVER') return [
      ['Type de construction', form.projectType || 'Non précisé'],
      ['Avancement actuel', form.progress || 'Non précisé'],
      ['Entreprise en place', form.currentCompany || 'Non précisé'],
      ['Dépenses engagées', formatMoney(form.spent)],
    ];
    if (kind === 'MAINTENANCE') return [
      ['Type de propriété', form.propertyType || 'Non précisé'],
      ['Occupation', form.occupancy || 'Non précisé'],
      ['Fréquence', form.frequency || 'À définir'],
      ['Interventions', form.maintenanceServices.join(', ') || 'À définir'],
    ];
    if (kind === 'OTHER') return [['Sujet', form.description || 'À préciser']];
    return [
      ['Type de projet', form.projectType || 'Non précisé'],
      ['Budget indicatif', formatMoney(form.budget)],
      ['Démarrage souhaité', form.desiredDate || 'À définir'],
    ];
  }, [form, kind]);

  function goNext(): void {
    setError('');
    if (stage === 'service') {
      if (!kind) { setError('Choisissez le service qui correspond le mieux à votre besoin.'); return; }
      setStage(myProjects.length > 0 ? 'project' : 'contact');
      return;
    }
    if (stage === 'project') {
      setStage('contact');
      return;
    }
    if (stage === 'contact') {
      const phoneDigits = form.phone.replace(/\D/g, '');
      if (!form.firstName.trim() || !form.lastName.trim()) { setError('Indiquez votre nom et votre prénom.'); return; }
      if (phoneDigits.length < 9) { setError('Saisissez un numéro camerounais à 9 chiffres.'); return; }
      setStage('details');
      return;
    }
    if (stage === 'details') {
      if (kind !== 'OTHER' && !form.city.trim()) { setError('Indiquez la ville ou la localité du bien.'); return; }
      if ((kind === 'BUILD' || kind === 'TAKEOVER') && !form.projectType) { setError('Choisissez le type de construction.'); return; }
      if (kind === 'MAINTENANCE' && !form.propertyType) { setError('Choisissez le type de propriété.'); return; }
      setStage('context');
      return;
    }
    if (stage === 'context') {
      if (!form.description.trim() && kind !== 'OTHER') { setError('Ajoutez quelques mots pour nous aider à comprendre votre besoin.'); return; }
      if (kind === 'OTHER' && form.description.trim().length < 8) { setError('Décrivez votre demande en quelques mots.'); return; }
      setStage('review');
    }
  }

  function goBack(): void {
    setError('');
    if (stage === 'project') { setStage('service'); return; }
    if (stage === 'contact') { setStage(myProjects.length > 0 ? 'project' : 'service'); return; }
    if (stage === 'details') { setStage('contact'); return; }
    if (stage === 'context') { setStage('details'); return; }
    if (stage === 'review') { setStage('context'); }
  }

  function handleFiles(selected: FileList | null): void {
    setError('');
    if (!selected) return;
    const selectedFiles = Array.from(selected);
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    const invalidType = selectedFiles.find((file) => !allowedTypes.includes(file.type));
    if (invalidType) { setError('Les pièces jointes doivent être au format JPG, PNG, WebP ou PDF.'); return; }
    if (selectedFiles.some((file) => file.size > 8 * 1024 * 1024)) { setError('Chaque fichier doit faire moins de 8 Mo.'); return; }
    const currentTotal = files.reduce((total, file) => total + file.size, 0);
    const selectedTotal = selectedFiles.reduce((total, file) => total + file.size, 0);
    if (currentTotal + selectedTotal > 32 * 1024 * 1024) { setError('La taille totale des pièces jointes doit rester sous 32 Mo.'); return; }
    setFiles((current) => {
      const next = [...current, ...selectedFiles].slice(0, 5);
      if (current.length + selectedFiles.length > 5) setError('Vous pouvez joindre jusqu’à 5 fichiers.');
      return next;
    });
  }

  async function submitRequest(): Promise<void> {
    if (!kind) return;
    setIsSubmitting(true);
    setError('');
    try {
      const payload = new FormData();
      payload.append('service_type', kind);
      payload.append('first_name', form.firstName.trim());
      payload.append('last_name', form.lastName.trim());
      payload.append('phone', `+237${form.phone.replace(/\D/g, '').slice(-9)}`);
      if (form.email.trim()) payload.append('email', form.email.trim());
      payload.append('city', form.city.trim());
      payload.append('project_type', form.projectType);
      payload.append('description', form.description.trim());
      payload.append('metadata', JSON.stringify({
        budget_fcfa: form.budget ? Number(form.budget.replace(/\D/g, '')) : null,
        desired_date: form.desiredDate || null,
        progress: form.progress || null,
        current_company: form.currentCompany || null,
        spent_fcfa: form.spent ? Number(form.spent.replace(/\D/g, '')) : null,
        property_type: form.propertyType || null,
        occupancy: form.occupancy || null,
        last_visit: form.lastVisit || null,
        frequency: form.frequency || null,
        maintenance_services: form.maintenanceServices,
        expectations: form.expectations.trim() || null,
      }));
      if (projectId) payload.append('related_project', String(projectId));
      files.forEach((file) => payload.append('attachments', file));
      const result = await apiRequest<RequestResult>('/service-requests/', { method: 'POST', body: payload });
      setRequestResult(result);
      setStage('sent');
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Votre demande n’a pas pu être envoyée. Vérifiez votre connexion puis réessayez.');
    } finally {
      setIsSubmitting(false);
    }
  }

  function restart(): void {
    setForm(initialForm);
    setProjectId(null);
    setFiles([]);
    setKind(null);
    setRequestResult(null);
    setError('');
    setStage('service');
  }

  return (
    <main className="request-page">
      <header className="request-header"><div className="page-container request-header-inner"><Brand /><Link to="/" className="request-cancel">Retour à l’accueil <X size={16} /></Link></div></header>
      <div className="request-shell page-container">
        <div className="request-side">
          <span className="section-kicker">Votre projet mérite un bon départ</span>
          <h1>Parlons de<br />votre projet.</h1>
          <p>Quelques informations suffisent pour que notre équipe comprenne votre besoin et prépare un premier échange utile.</p>
          <div className="request-reassurance"><span><CheckCircle2 size={17} /> Quelques étapes courtes</span><span><CheckCircle2 size={17} /> Vos informations restent confidentielles</span><span><CheckCircle2 size={17} /> Vous gardez la main sur la suite</span></div>
          <div className="request-side-note"><span className="request-note-icon"><FileText size={18} /></span><span><strong>Pas besoin d’avoir tout préparé.</strong><small>Vous pourrez compléter les détails avec l’équipe KEMTA.</small></span></div>
        </div>
        <section className="request-form-panel" aria-label="Formulaire de demande de service">
          {stage !== 'sent' && <div className="wizard-progress"><div className="wizard-progress-copy"><span>Étape {activeIndex + 1} sur {stepLabels.length}</span><span>{percent}%</span></div><div className="wizard-progress-track"><span style={{ width: `${percent}%` }} /></div><div className="wizard-steps-labels">{stepLabels.map((label, index) => <span className={index <= activeIndex ? 'step-label-active' : ''} key={label}>{label}</span>)}</div></div>}

          {stage === 'service' && <div className="wizard-content">
            <span className="wizard-kicker">Commençons par l’essentiel</span><h2>Que souhaitez-vous faire ?</h2><p className="wizard-intro">Choisissez l’option la plus proche de votre besoin.</p>
            <div className="service-choice-list">
              {serviceOptions.map(({ type, icon: Icon, title, description }) => <button type="button" className={`service-choice${kind === type ? ' choice-selected' : ''}`} key={type} onClick={() => { setKind(type); setError(''); }} aria-pressed={kind === type}>
                <span className="choice-icon"><Icon size={21} /></span><span className="choice-text"><strong>{title}</strong><small>{description}</small></span><span className="choice-check">{kind === type && <Check size={15} />}</span>
              </button>)}
            </div>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="wizard-actions wizard-actions-right"><button className="button button-primary" onClick={goNext}>Continuer <ArrowRight size={16} /></button></div>
          </div>}

          {stage === 'project' && <div className="wizard-content">
            <button type="button" className="wizard-back" onClick={goBack}><ArrowLeft size={15} /> Modifier le service</button>
            <span className="wizard-kicker">{serviceName(kind)}</span><h2>Quel bien est concerné ?</h2><p className="wizard-intro">Rattachez votre demande à l’un de vos chantiers suivis par KEMTA, ou décrivez un autre bien.</p>
            <div className="service-choice-list">
              {myProjects.map((project) => <button type="button" key={project.id} className={`service-choice${projectId === project.id ? ' choice-selected' : ''}`} onClick={() => { setProjectId(project.id); setError(''); }} aria-pressed={projectId === project.id}>
                <span className="choice-icon"><House size={20} /></span>
                <span className="choice-text"><strong>{project.name}</strong><small>{project.city} · {project.current_phase || 'étape à définir'} · {project.progress}% d’avancement</small></span>
                <span className="choice-check">{projectId === project.id && <Check size={15} />}</span>
              </button>)}
              <button type="button" className={`service-choice${projectId === null ? ' choice-selected' : ''}`} onClick={() => { setProjectId(null); setError(''); }} aria-pressed={projectId === null}>
                <span className="choice-icon"><MapPin size={20} /></span>
                <span className="choice-text"><strong>Un autre bien ou un nouveau projet</strong><small>Vous préciserez la localisation à l’étape suivante.</small></span>
                <span className="choice-check">{projectId === null && <Check size={15} />}</span>
              </button>
            </div>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="wizard-actions"><button className="button button-outline" onClick={goBack}><ArrowLeft size={15} /> Retour</button><button className="button button-primary" onClick={goNext}>Continuer <ArrowRight size={16} /></button></div>
          </div>}

          {stage === 'contact' && <div className="wizard-content">
            <button type="button" className="wizard-back" onClick={goBack}><ArrowLeft size={15} /> {myProjects.length > 0 ? 'Modifier le bien' : 'Modifier le service'}</button>
            <span className="wizard-kicker">{serviceName(kind)}</span><h2>Comment vous joindre ?</h2><p className="wizard-intro">Ces informations nous permettent de revenir vers vous au sujet de votre demande.</p>
            <div className="form-grid form-grid-two">
              <label className="field"><span>Prénom <b>*</b></span><input autoComplete="given-name" value={form.firstName} onChange={(event) => update('firstName', event.target.value)} placeholder="Votre prénom" /></label>
              <label className="field"><span>Nom <b>*</b></span><input autoComplete="family-name" value={form.lastName} onChange={(event) => update('lastName', event.target.value)} placeholder="Votre nom" /></label>
              <label className="field field-full"><span>Téléphone <b>*</b></span><div className="phone-field"><span className="phone-prefix">🇨🇲 +237</span><input autoComplete="tel-national" inputMode="tel" value={form.phone} onChange={(event) => update('phone', event.target.value.replace(/[^0-9\s]/g, '').slice(0, 12))} placeholder="6 XX XX XX XX" aria-label="Numéro de téléphone sans indicatif" /></div><small>Votre numéro sert à vous recontacter. Il ne sera pas affiché publiquement.</small></label>
              <label className="field field-full"><span>Email <small>(facultatif)</small></span><input type="email" autoComplete="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder="vous@exemple.com" /></label>
            </div>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="wizard-actions"><button className="button button-outline" onClick={goBack}><ArrowLeft size={15} /> Retour</button><button className="button button-primary" onClick={goNext}>Continuer <ArrowRight size={16} /></button></div>
          </div>}

          {stage === 'details' && <div className="wizard-content">
            <button type="button" className="wizard-back" onClick={goBack}><ArrowLeft size={15} /> Retour</button>
            <span className="wizard-kicker">{serviceName(kind)}</span><h2>Parlez-nous du bien.</h2><p className="wizard-intro">Un premier aperçu nous aidera à préparer la bonne suite.</p>
            {kind === 'OTHER' ? <div className="form-grid"><label className="field field-full"><span>Le sujet de votre demande</span><input value={form.expectations} onChange={(event) => update('expectations', event.target.value)} placeholder="Ex. Conseil, partenariat, autre question" /></label></div> : <div className="form-grid form-grid-two">
              <label className="field field-full"><span>Ville ou localité <b>*</b></span><input value={form.city} onChange={(event) => update('city', event.target.value)} placeholder="Ex. Douala, Bonapriso" /><small>Indiquez le quartier si vous le connaissez.</small></label>
              {kind === 'BUILD' && <>
                <label className="field field-full"><span>Type de projet <b>*</b></span><select value={form.projectType} onChange={(event) => update('projectType', event.target.value)}><option value="">Sélectionner un type</option><option value="Maison individuelle">Maison individuelle</option><option value="Villa">Villa</option><option value="Immeuble">Immeuble</option><option value="Rénovation">Rénovation</option><option value="Autre">Autre</option></select></label>
                <label className="field"><span>Budget indicatif</span><div className="field-suffix"><input inputMode="numeric" value={form.budget} onChange={(event) => update('budget', event.target.value.replace(/[^0-9]/g, ''))} placeholder="Ex. 25 000 000" /><span>FCFA</span></div></label>
                <label className="field"><span>Date souhaitée</span><input type="month" value={form.desiredDate} onChange={(event) => update('desiredDate', event.target.value)} /></label>
              </>}
              {kind === 'TAKEOVER' && <>
                <label className="field field-full"><span>Type de construction <b>*</b></span><select value={form.projectType} onChange={(event) => update('projectType', event.target.value)}><option value="">Sélectionner un type</option><option value="Maison individuelle">Maison individuelle</option><option value="Villa">Villa</option><option value="Immeuble">Immeuble</option><option value="Rénovation">Rénovation</option><option value="Autre">Autre</option></select></label>
                <label className="field"><span>Avancement actuel</span><select value={form.progress} onChange={(event) => update('progress', event.target.value)}><option value="">Je ne sais pas</option><option value="Études / préparation">Études / préparation</option><option value="Fondations">Fondations</option><option value="Structure / murs">Structure / murs</option><option value="Toiture">Toiture</option><option value="Second œuvre">Second œuvre</option><option value="Finitions">Finitions</option></select></label>
                <label className="field"><span>Budget déjà dépensé</span><div className="field-suffix"><input inputMode="numeric" value={form.spent} onChange={(event) => update('spent', event.target.value.replace(/[^0-9]/g, ''))} placeholder="Facultatif" /><span>FCFA</span></div></label>
                <label className="field field-full"><span>Entreprise actuelle</span><input value={form.currentCompany} onChange={(event) => update('currentCompany', event.target.value)} placeholder="Nom de l’entreprise, si connu" /></label>
              </>}
              {kind === 'MAINTENANCE' && <>
                <label className="field field-full"><span>Type de propriété <b>*</b></span><select value={form.propertyType} onChange={(event) => update('propertyType', event.target.value)}><option value="">Sélectionner un type</option><option value="Maison">Maison</option><option value="Villa">Villa</option><option value="Appartement">Appartement</option><option value="Terrain">Terrain</option><option value="Local commercial">Local commercial</option><option value="Autre">Autre</option></select></label>
                <label className="field"><span>Occupation du bien</span><select value={form.occupancy} onChange={(event) => update('occupancy', event.target.value)}><option value="">Sélectionner</option><option value="Occupé">Occupé</option><option value="Inoccupé">Inoccupé</option><option value="En location">En location</option><option value="En travaux">En travaux</option></select></label>
                <label className="field"><span>Fréquence souhaitée</span><select value={form.frequency} onChange={(event) => update('frequency', event.target.value)}><option value="">À définir</option><option value="Ponctuelle">Ponctuelle</option><option value="Mensuelle">Mensuelle</option><option value="Trimestrielle">Trimestrielle</option><option value="Semestrielle">Semestrielle</option><option value="Sur demande">Sur demande</option></select></label>
              </>}
            </div>}
            {kind === 'MAINTENANCE' && <fieldset className="service-checks"><legend>Quels services vous intéressent ? <small>(plusieurs choix possibles)</small></legend><div>{['Inspection', 'Nettoyage', 'Jardinage', 'Plomberie', 'Électricité', 'Petites réparations'].map((service) => <button type="button" key={service} className={`service-chip${form.maintenanceServices.includes(service) ? ' service-chip-active' : ''}`} onClick={() => toggleService(service)} aria-pressed={form.maintenanceServices.includes(service)}>{form.maintenanceServices.includes(service) && <Check size={13} />}{service}</button>)}</div></fieldset>}
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="wizard-actions"><button className="button button-outline" onClick={goBack}><ArrowLeft size={15} /> Retour</button><button className="button button-primary" onClick={goNext}>Continuer <ArrowRight size={16} /></button></div>
          </div>}

          {stage === 'context' && <div className="wizard-content">
            <button type="button" className="wizard-back" onClick={goBack}><ArrowLeft size={15} /> Retour</button>
            <span className="wizard-kicker">Encore quelques détails</span><h2>Qu’aimeriez-vous nous dire ?</h2><p className="wizard-intro">Décrivez votre objectif, vos difficultés ou ce qui compte le plus pour vous.</p>
            <label className="field field-full"><span>{kind === 'TAKEOVER' ? 'Quels sont les problèmes ou vos attentes ?' : kind === 'MAINTENANCE' ? 'Précisions sur le bien ou l’intervention' : kind === 'OTHER' ? 'Votre demande' : 'Quelques mots sur le projet'} <b>*</b></span><textarea rows={5} value={form.description} onChange={(event) => update('description', event.target.value)} placeholder="Écrivez votre message ici…" /></label>
            {kind === 'TAKEOVER' && <label className="field field-full context-secondary"><span>Votre objectif prioritaire</span><input value={form.expectations} onChange={(event) => update('expectations', event.target.value)} placeholder="Ex. Obtenir un état des lieux indépendant" /></label>}
            {kind !== 'OTHER' && <div className="upload-box"><label className="upload-control"><input type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(event) => handleFiles(event.target.files)} /><span className="upload-icon"><Upload size={20} /></span><strong>Ajouter des photos ou des documents <small>(facultatif)</small></strong><small>JPG, PNG, WebP ou PDF · 8 Mo maximum par fichier · 5 fichiers</small></label>
              {files.length > 0 && <div className="file-list">{files.map((file, index) => <div className="file-row" key={`${file.name}-${index}`}><FileText size={15} /><span>{file.name}</span><small>{(file.size / (1024 * 1024)).toFixed(1)} Mo</small><button type="button" aria-label={`Retirer ${file.name}`} onClick={() => setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index))}><X size={15} /></button></div>)}</div>}
            </div>}
            <p className="privacy-line"><CheckCircle2 size={15} /> Vos documents ne sont visibles que par l’équipe concernée.</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="wizard-actions"><button className="button button-outline" onClick={goBack}><ArrowLeft size={15} /> Retour</button><button className="button button-primary" onClick={goNext}>Vérifier ma demande <ArrowRight size={16} /></button></div>
          </div>}

          {stage === 'review' && <div className="wizard-content">
            <button type="button" className="wizard-back" onClick={goBack}><ArrowLeft size={15} /> Modifier les détails</button>
            <span className="wizard-kicker">Dernière vérification</span><h2>Tout est correct ?</h2><p className="wizard-intro">Votre demande sera transmise à l’équipe KEMTA pour étude.</p>
            <div className="review-card"><div className="review-heading"><span className="review-icon"><CheckCircle2 size={19} /></span><span><small>TYPE DE SERVICE</small><strong>{serviceName(kind)}</strong></span><button type="button" onClick={() => setStage('service')}>Modifier</button></div><div className="review-divider" /><div className="review-grid"><div><small>CONTACT</small><strong>{form.firstName} {form.lastName}</strong><span>+237 {form.phone.replace(/\D/g, '').slice(-9)}{form.email && ` · ${form.email}`}</span></div><div><small>LOCALISATION</small><strong>{form.city || 'Non précisée'}</strong></div><div><small>PROJET CONCERNÉ</small><strong>{myProjects.find((project) => project.id === projectId)?.name ?? 'Autre bien'}</strong></div>{detailsSummary.map(([label, value]) => <div key={label}><small>{label.toUpperCase()}</small><strong>{value}</strong></div>)}<div className="review-description"><small>VOTRE MESSAGE</small><p>{form.description || 'Aucun message complémentaire.'}</p></div>{files.length > 0 && <div className="review-description"><small>PIÈCES JOINTES ({files.length})</small><p>{files.map((file) => file.name).join(' · ')}</p></div>}</div></div>
            <p className="privacy-line"><CheckCircle2 size={15} /> En envoyant cette demande, vous acceptez d’être recontacté au sujet de votre projet.</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="wizard-actions"><button className="button button-outline" onClick={goBack}><ArrowLeft size={15} /> Retour</button><button className="button button-primary" onClick={() => void submitRequest()} disabled={isSubmitting}>{isSubmitting ? 'Envoi en cours…' : 'Envoyer ma demande'} {!isSubmitting && <ArrowRight size={16} />}</button></div>
          </div>}

          {stage === 'sent' && <div className="request-success">
            <span className="success-check"><Check size={26} /></span><span className="wizard-kicker">Demande transmise</span><h2>Merci, {form.firstName}.</h2><p>Votre demande est bien enregistrée. Gardez cette référence pour suivre les échanges avec l’équipe KEMTA.</p>
            <div className="request-reference"><small>RÉFÉRENCE DE DEMANDE</small><strong>{requestResult?.request_code ?? 'KEMTA-REQ'}</strong><span>{requestResult?.created_at ? new Date(requestResult.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : 'Demande reçue'}</span></div>
            <div className="success-next"><span><CheckCircle2 size={16} /></span><p><strong>La suite</strong><br />L’équipe étudiera les informations transmises avant de vous recontacter.</p></div>
            <div className="wizard-actions"><Link className="button button-outline" to="/">Retour à l’accueil</Link><button className="button button-primary" onClick={restart}><RotateCcw size={15} /> Nouvelle demande</button></div>
          </div>}
          <div className="wizard-privacy-footer"><span><ShieldCheckIcon /> KEMTA protège vos informations personnelles.</span><span>Besoin d’aide ? <Link to="/faq">Consulter les réponses</Link></span></div>
        </section>
      </div>
      <div className="request-footnote">KEMTA · La confiance au cœur de votre projet immobilier.</div>
    </main>
  );
}

function ShieldCheckIcon() {
  return <CheckCircle2 size={14} aria-hidden="true" />;
}
