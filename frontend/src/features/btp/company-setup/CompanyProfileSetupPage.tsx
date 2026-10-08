/** Étape 2 : informations légales et coordonnées de l'entreprise. */
import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, BadgeCheck, Info, Lock } from 'lucide-react';
import { ApiError, apiRequest, jsonBody } from '../../../lib/api';
import { companyTypeOptions, countryOptions } from '../companyVerification';
import {
  apiMessage,
  CompanySpaceGate,
  SetupLayout,
  SnapshotGate,
  useVerificationSnapshot,
} from './shared';

interface CompanyFormState {
  name: string;
  legal_name: string;
  company_type: string;
  sector: string;
  country: string;
  city: string;
  address: string;
  phone: string;
  email: string;
  website: string;
}

const emptyCompanyForm: CompanyFormState = {
  name: '', legal_name: '', company_type: '', sector: '', country: 'Cameroun',
  city: '', address: '', phone: '', email: '', website: '',
};

const requiredFields: Array<[keyof CompanyFormState, string]> = [
  ['name', 'Nom commercial'], ['legal_name', 'Nom légal'], ['company_type', 'Type d’entreprise'],
  ['sector', 'Secteur d’activité'], ['city', 'Ville'], ['address', 'Adresse'],
];

export function CompanyProfileSetupPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const snapshot = useVerificationSnapshot();
  const [form, setForm] = useState<CompanyFormState>(emptyCompanyForm);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const isNewProfile = snapshot.error instanceof ApiError && snapshot.error.status === 404;

  useEffect(() => {
    const profile = snapshot.data?.profile;
    if (!profile) return;
    setForm({
      name: profile.name ?? '',
      legal_name: profile.legal_name ?? '',
      company_type: profile.company_type ?? '',
      sector: profile.sector ?? '',
      country: profile.country || 'Cameroun',
      city: profile.city ?? '',
      address: profile.address ?? '',
      phone: profile.phone ?? '',
      email: profile.email ?? '',
      website: profile.website ?? '',
    });
  }, [snapshot.data]);

  const saveMutation = useMutation({
    mutationFn: (_goTo: 'documents' | 'later') => {
      const payload = { ...form, country: form.country.trim() || 'Cameroun' };
      // PATCH : enregistrement partiel, « continuer plus tard » reste possible.
      return apiRequest(`/companies/me/`, isNewProfile
        ? { method: 'PUT', body: jsonBody(payload) }
        : { method: 'PATCH', body: jsonBody(payload) });
    },
    onSuccess: async (_data, goTo) => {
      await queryClient.invalidateQueries({ queryKey: ['company-verification'] });
      await queryClient.invalidateQueries({ queryKey: ['company-profile'] });
      navigate(goTo === 'later' ? '/dashboard' : '/entreprise/documents');
    },
    onError: (caught) => setError(apiMessage(caught, 'Les informations n’ont pas pu être enregistrées.')),
  });

  function update(key: keyof CompanyFormState, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
    setNotice('');
  }

  function save(goTo: 'documents' | 'later'): void {
    setError('');
    // L'enregistrement anticipé exige au minimum le nom commercial (clé du profil).
    if (!form.name.trim()) { setError('Renseignez au moins le nom commercial de l’entreprise.'); return; }
    if (goTo === 'documents') {
      const missing = requiredFields.filter(([key]) => !String(form[key] ?? '').trim()).map(([, label]) => label);
      if (missing.length) { setError(`Complétez ces informations pour continuer : ${missing.join(', ')}.`); return; }
    }
    // Le champ `name` est obligatoire pour créer le profil : le reste peut être enregistré plus tard.
    saveMutation.mutate(goTo);
  }

  return <CompanySpaceGate><SetupLayout
    step="profile"
    kicker="KEMTA BTP · Étape 2 sur 4"
    title="Informations sur votre entreprise"
    lede="Ces informations légales restent privées. Elles servent uniquement à vérifier votre entreprise."
  >
    <SnapshotGate query={snapshot}>{(data) => <>
      {data.status === 'VERIFIED' && <p className="form-notice" role="status"><BadgeCheck size={15} /> Entreprise vérifiée : vos informations sont à jour.</p>}
      {isNewProfile && <p className="form-notice" role="status"><Info size={15} /> Aucun profil n’existe encore : le formulaire en crée un à l’enregistrement.</p>}
      {data.missing_profile_fields.length > 0 && <p className="setup-note"><Info size={15} /> Encore à compléter pour la soumission : <strong>{data.missing_profile_fields.join(', ')}</strong>.</p>}
      <form className="company-form" onSubmit={(event) => { event.preventDefault(); save('documents'); }}>
        <div className="company-form-section">
          <div className="company-form-section-title"><span>01</span><div><h2>Identité de l’entreprise</h2><p>Les informations figurant sur vos documents officiels.</p></div></div>
          <div className="form-grid form-grid-two">
            <label className="field"><span>Nom commercial <b>*</b></span><input value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="Ex. Bâtir & Rénover" maxLength={140} /></label>
            <label className="field"><span>Nom légal <b>*</b></span><input value={form.legal_name} onChange={(event) => update('legal_name', event.target.value)} placeholder="Ex. BÂTIR ET RÉNOVER SARL" maxLength={160} /></label>
            <label className="field"><span>Type d’entreprise <b>*</b></span><select value={form.company_type} onChange={(event) => update('company_type', event.target.value)}><option value="">Sélectionner…</option>{companyTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="field"><span>Secteur d’activité <b>*</b></span><input value={form.sector} onChange={(event) => update('sector', event.target.value)} placeholder="Ex. Bâtiment et travaux publics" maxLength={80} /></label>
          </div>
        </div>
        <div className="company-form-section">
          <div className="company-form-section-title"><span>02</span><div><h2>Localisation & contact</h2><p>Où intervient votre entreprise et comment vous joindre.</p></div></div>
          <div className="form-grid form-grid-two">
            <label className="field"><span>Pays</span><select value={form.country} onChange={(event) => update('country', event.target.value)}>{countryOptions.map((country) => <option key={country} value={country}>{country}</option>)}</select></label>
            <label className="field"><span>Ville <b>*</b></span><input value={form.city} onChange={(event) => update('city', event.target.value)} placeholder="Ex. Douala" maxLength={100} /></label>
            <label className="field field-full"><span>Adresse <b>*</b></span><input value={form.address} onChange={(event) => update('address', event.target.value)} placeholder="Ex. Rue Njo-Njo, Bonapriso" maxLength={200} /></label>
            <label className="field"><span>Téléphone professionnel</span><input autoComplete="tel" value={form.phone} onChange={(event) => update('phone', event.target.value)} placeholder="+237 6 XX XX XX XX" maxLength={32} /></label>
            <label className="field"><span>Email professionnel</span><input type="email" autoComplete="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder="contact@entreprise.cm" /></label>
            <label className="field field-full"><span>Site web <small>(facultatif)</small></span><input type="url" value={form.website} onChange={(event) => update('website', event.target.value)} placeholder="https://www.entreprise.cm" maxLength={300} /></label>
          </div>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="form-notice" role="status">{notice}</p>}
        <div className="company-form-actions company-setup-actions">
          <button className="button button-outline" type="button" disabled={saveMutation.isPending} onClick={() => save('later')}>{saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer et continuer plus tard'}</button>
          <button className="button button-primary" type="submit" disabled={saveMutation.isPending}>{saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer et continuer'} <ArrowRight size={16} /></button>
        </div>
        <p className="setup-legal-note"><Lock size={14} /> Vos informations légales et vos pièces justificatives ne sont jamais publiées : seule l’équipe KEMTA y a accès.</p>
      </form>
    </>}</SnapshotGate>
  </SetupLayout></CompanySpaceGate>;
}
