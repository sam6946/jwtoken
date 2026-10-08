import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, Eye, EyeOff,
  Info, KeyRound, LockKeyhole, MessageSquareText, ShieldCheck, Smartphone,
} from 'lucide-react';
import { Brand } from '../../components/Brand';
import { ApiError, apiRequest, jsonBody } from '../../lib/api';
import { useAuth, type KemtaUser, type UserRole } from '../../lib/auth';
import {
  countryCallingCodes,
  isValidPhoneNumber,
  normalizePhoneInput,
  OtpInput,
  PhoneNumberInput,
  phoneForApi,
} from './AuthPhoneFields';


type AuthMode = 'login' | 'register' | 'reset';
type RegisterStep = 'phone' | 'otp' | 'profile';
type OtpPurpose = 'REGISTER' | 'LOGIN' | 'PASSWORD_RESET';
interface AuthResponse { access: string; refresh?: string; user: KemtaUser }
interface OtpRequestResponse { detail: string; expires_in: number; debug_code?: string }
interface OtpVerifyResponse { verification_token: string; phone: string }

// Exports conservés pour les consommateurs existants (tests et futurs écrans auth).
export {
  countryCallingCodes,
  isValidPhoneNumber,
  normalizePhoneInput,
  OtpInput,
  PhoneNumberInput,
  phoneForApi,
};

const demoAccounts = [
  { phone: '2025550101', role: 'Client / propriétaire', displayPhone: '+1 202-555-0101' },
  { phone: '2025550102', role: 'Entreprise BTP', displayPhone: '+1 202-555-0102' },
  { phone: '2025550103', role: 'Agent terrain', displayPhone: '+1 202-555-0103' },
  { phone: '2025550104', role: 'Chef de projet', displayPhone: '+1 202-555-0104' },
  { phone: '2025550105', role: 'Administrateur', displayPhone: '+1 202-555-0105' },
  { phone: '2025550106', role: 'Super-administrateur', displayPhone: '+1 202-555-0106' },
];
const demoPassword = 'KemtaDemo2026!';

function getMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Impossible de joindre le service. Vérifiez votre connexion puis réessayez.';
}

export function AuthPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, establishSession, isReady } = useAuth();
  const mode: AuthMode = location.pathname === '/inscription' ? 'register' : location.pathname === '/mot-de-passe-oublie' ? 'reset' : 'login';
  const [phone, setPhone] = useState('');
  const [dialingCode, setDialingCode] = useState('237');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpToken, setOtpToken] = useState('');
  const [debugCode, setDebugCode] = useState('');
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [registerStep, setRegisterStep] = useState<RegisterStep>('phone');
  const [otpFlow, setOtpFlow] = useState<'none' | 'login' | 'reset'>('none');
  const [loginMethod, setLoginMethod] = useState<'password' | 'otp'>('password');
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const requestedRole: UserRole = searchParams.get('role') === 'BTP_COMPANY' ? 'BTP_COMPANY' : 'CUSTOMER';
  const isBtpSignup = mode === 'register' && requestedRole === 'BTP_COMPANY';
  const redirectTo = searchParams.get('next') || '/dashboard';
  // Reprise après expiration : on explique la redirection plutôt que de laisser l'utilisateur deviner.
  const sessionExpiredNotice = searchParams.get('session') === 'expiree';

  useEffect(() => {
    if (secondsLeft <= 0) return undefined;
    const timer = window.setTimeout(() => setSecondsLeft((seconds) => Math.max(0, seconds - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [secondsLeft]);

  useEffect(() => {
    setError('');
    setNotice('');
    setRegisterStep('phone');
    setOtpFlow('none');
    setLoginMethod('password');
    setOtp('');
    setOtpSent(false);
    setOtpToken('');
    setDebugCode('');
    setCompanyName('');
  }, [location.pathname]);

  const currentTitle = useMemo(() => {
    if (mode === 'register') {
      if (registerStep === 'phone') return isBtpSignup ? 'Créez votre espace entreprise.' : 'Votre projet commence ici.';
      if (registerStep === 'otp') return 'Vérifions votre numéro.';
      return isBtpSignup ? 'Votre entreprise, en quelques informations.' : 'Quelques informations et c’est prêt.';
    }
    if (mode === 'reset') return otpFlow === 'reset' && otpToken ? 'Choisissez un nouveau mot de passe.' : otpFlow === 'reset' ? 'Entrez le code reçu.' : 'Réinitialisez votre mot de passe.';
    if (loginMethod === 'otp' && otpFlow === 'login') return otpToken ? 'Connexion confirmée.' : 'Entrez le code reçu.';
    return 'Content de vous revoir.';
  }, [mode, registerStep, isBtpSignup, otpFlow, otpToken, loginMethod]);

  async function requestOtp(purpose: OtpPurpose): Promise<void> {
    const digits = normalizePhoneInput(phone);
    if (!isValidPhoneNumber(digits, dialingCode)) { setError(dialingCode === '237' ? 'Saisissez un numéro camerounais valide à 9 chiffres.' : 'Vérifiez le numéro et l’indicatif sélectionné.'); return; }
    setError('');
    setNotice('');
    setIsBusy(true);
    try {
      const response = await apiRequest<OtpRequestResponse>('/auth/otp/request/', {
        method: 'POST',
        body: jsonBody({ phone: phoneForApi(phone, dialingCode), purpose }),
      });
      setSecondsLeft(30);
      setDebugCode(response.debug_code ?? '');
      setOtp('');
      setOtpSent(true);
      if (purpose === 'REGISTER') setRegisterStep('otp');
      if (purpose === 'LOGIN') { setOtpFlow('login'); setLoginMethod('otp'); }
      if (purpose === 'PASSWORD_RESET') setOtpFlow('reset');
      setNotice(response.detail || 'Si ce numéro peut recevoir un code, celui-ci vient d’être envoyé.');
    } catch (caught) {
      setError(getMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  async function verifyOtp(purpose: OtpPurpose): Promise<void> {
    if (otp.replace(/\D/g, '').length !== 6) { setError('Saisissez les 6 chiffres du code reçu.'); return; }
    setIsBusy(true);
    setError('');
    try {
      const response = await apiRequest<OtpVerifyResponse>('/auth/otp/verify/', {
        method: 'POST',
        body: jsonBody({ phone: phoneForApi(phone, dialingCode), code: otp, purpose }),
      });
      setOtpToken(response.verification_token);
      setNotice('Numéro vérifié. Vous pouvez continuer.');
      if (purpose === 'REGISTER') setRegisterStep('profile');
      if (purpose === 'PASSWORD_RESET') setOtpFlow('reset');
      if (purpose === 'LOGIN') {
        const auth = await apiRequest<AuthResponse>('/auth/otp/login/', {
          method: 'POST', body: jsonBody({ verification_token: response.verification_token }),
        });
        establishSession(auth.access, auth.user, auth.refresh);
        navigate(redirectTo, { replace: true });
      }
    } catch (caught) {
      setError(getMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (loginMethod === 'otp') { await verifyOtp('LOGIN'); return; }
    if (!isValidPhoneNumber(normalizePhoneInput(phone), dialingCode) || !password) { setError('Vérifiez votre numéro de téléphone, son indicatif et votre mot de passe.'); return; }
    setIsBusy(true);
    setError('');
    try {
      const response = await apiRequest<AuthResponse>('/auth/login/', {
        method: 'POST', body: jsonBody({ phone: phoneForApi(phone, dialingCode), password }),
      });
      establishSession(response.access, response.user, response.refresh);
      navigate(redirectTo, { replace: true });
    } catch (caught) {
      setError(getMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  async function submitRegistration(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!otpToken) { setError('Vérifiez votre numéro avant de créer le compte.'); setRegisterStep('phone'); return; }
    if (!firstName.trim() || !lastName.trim()) { setError('Renseignez votre prénom et votre nom.'); return; }
    if (isBtpSignup && companyName.trim().length < 2) { setError('Renseignez le nom de votre entreprise.'); return; }
    if (password.length < 10) { setError('Utilisez un mot de passe d’au moins 10 caractères.'); return; }
    if (password !== confirmPassword) { setError('Les deux mots de passe ne correspondent pas.'); return; }
    setIsBusy(true);
    setError('');
    try {
      const response = await apiRequest<AuthResponse>('/auth/register/', {
        method: 'POST',
        body: jsonBody({
          phone: phoneForApi(phone, dialingCode),
          verification_token: otpToken,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim() || null,
          password,
          role: requestedRole,
          terms_accepted: true,
          ...(isBtpSignup ? { company_name: companyName.trim() } : {}),
        }),
      });
      establishSession(response.access, response.user, response.refresh);
      // Un compte entreprise enchaîne sur son dossier de vérification.
      navigate(isBtpSignup ? '/entreprise/profil' : redirectTo, { replace: true });
    } catch (caught) {
      setError(getMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  async function submitPasswordReset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!otpToken) { setError('Vérifiez d’abord le code reçu sur votre téléphone.'); return; }
    if (password.length < 10) { setError('Utilisez un mot de passe d’au moins 10 caractères.'); return; }
    if (password !== confirmPassword) { setError('Les deux mots de passe ne correspondent pas.'); return; }
    setIsBusy(true);
    setError('');
    try {
      await apiRequest<{ detail: string }>('/auth/password-reset/confirm/', {
        method: 'POST', body: jsonBody({ verification_token: otpToken, password }),
      });
      setNotice('Votre mot de passe a été modifié. Vous pouvez vous connecter.');
      setOtpFlow('none');
      setOtpToken('');
      setPassword('');
      setConfirmPassword('');
    } catch (caught) {
      setError(getMessage(caught));
    } finally {
      setIsBusy(false);
    }
  }

  function resetOtpFlow(): void {
    setOtpFlow('none');
    setLoginMethod('password');
    setOtpToken('');
    setOtp('');
    setOtpSent(false);
    setDebugCode('');
    setError('');
    setNotice('');
  }

  function selectDemoAccount(demoPhone: string): void {
    setDialingCode('1');
    setPhone(demoPhone);
    setPassword(demoPassword);
    setLoginMethod('password');
    setOtpFlow('none');
    setOtpSent(false);
    setOtp('');
    setError('');
    setNotice('');
  }

  const isOtpScreen = (mode === 'register' && registerStep === 'otp')
    || (mode === 'login' && loginMethod === 'otp' && otpFlow === 'login' && otpSent)
    || (mode === 'reset' && otpFlow === 'reset' && !otpToken);

  // Une session déjà ouverte ne doit pas rester sur l'écran de connexion (place après tous les hooks).
  if (isReady && user && mode === 'login') return <Navigate to={redirectTo} replace />;

  return (
    <main className="auth-page">
      <div className="auth-topbar page-container"><Brand /><Link to="/" className="auth-back-link"><ArrowLeft size={15} /> Retour à KEMTA</Link></div>
      <div className="auth-layout page-container">
        <aside className="auth-aside">
          <span className="auth-aside-kicker"><span /> UN ESPACE QUI VOUS RESSEMBLE</span>
          <h1>{mode === 'register' && isBtpSignup ? <>Votre entreprise,<br /><em>plus visible.</em></> : <>Votre projet,<br /><em>en confiance.</em></>}</h1>
          <p>Retrouvez vos demandes, les étapes de votre chantier et les nouvelles du terrain dans un espace clair et personnel.</p>
          <div className="auth-aside-list"><span><CheckCircle2 size={17} /> Un suivi à votre rythme</span><span><CheckCircle2 size={17} /> Vos informations protégées</span><span><CheckCircle2 size={17} /> Un compte lié à votre téléphone</span></div>
          <div className="auth-aside-visual"><div className="auth-visual-icon"><Smartphone size={23} /></div><span><strong>À portée de main.</strong><small>Simple à utiliser, même à distance.</small></span><ArrowRight size={17} /></div>
        </aside>

        <section className="auth-card">
          <div className="auth-card-top"><span className="auth-kicker">{mode === 'register' ? isBtpSignup ? 'Espace KEMTA BTP' : 'Espace propriétaire' : mode === 'reset' ? 'Sécurité du compte' : 'Votre espace KEMTA'}</span><span className="auth-lock"><LockKeyhole size={16} /> Connexion sécurisée</span></div>
          <h2>{currentTitle}</h2>
          <p className="auth-lede">{mode === 'register' ? 'Le téléphone est votre identifiant principal. Votre adresse email reste facultative.' : mode === 'reset' ? 'Nous vérifierons votre numéro avant de modifier votre mot de passe.' : 'Connectez-vous avec votre numéro de téléphone.'}</p>

          {mode === 'login' && sessionExpiredNotice && <p className="auth-session-note" role="status"><Info size={15} /> <span><strong>Votre session a expiré.</strong> Reconnectez-vous pour retrouver votre espace : aucune donnée n’a été perdue.</span></p>}
          {mode === 'login' && <form onSubmit={(event) => void submitLogin(event)}>
            <label className="field auth-field"><span>Numéro de téléphone</span><PhoneNumberInput value={phone} dialingCode={dialingCode} onValueChange={(value) => { setPhone(value); setError(''); }} onDialingCodeChange={(code) => { setDialingCode(code); setError(''); }} /></label>
            {loginMethod === 'password' ? <>
              <label className="field auth-field"><span>Mot de passe</span><div className="password-field"><input autoComplete="current-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Votre mot de passe" /><button type="button" aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label>
              <div className="auth-inline-links"><Link to="/mot-de-passe-oublie">Mot de passe oublié ?</Link><button type="button" onClick={() => { setLoginMethod('otp'); setOtpFlow('login'); setOtp(''); setOtpSent(false); setError(''); setNotice(''); }}>Recevoir un code OTP</button></div>
              <button className="button button-primary auth-submit" type="submit" disabled={isBusy || !isReady}>{isBusy ? 'Connexion…' : 'Se connecter'} <ArrowRight size={16} /></button>
            </> : <>
              <div className="otp-form-inline">
                <p>Nous enverrons un code à usage unique au numéro indiqué.</p>
                {isOtpScreen && <OtpInput value={otp} onChange={setOtp} />}
                {debugCode && isOtpScreen && <p className="dev-code"><KeyRound size={14} /> Code de test local : <strong>{debugCode}</strong></p>}
                {notice && <p className="form-notice" role="status">{notice}</p>}
                {isOtpScreen ? <div className="otp-actions-row"><button type="button" className="auth-text-button" onClick={resetOtpFlow}><ArrowLeft size={14} /> Changer de méthode</button><button type="button" className="auth-text-button" disabled={secondsLeft > 0 || isBusy} onClick={() => void requestOtp('LOGIN')}>{secondsLeft > 0 ? `Renvoyer dans ${secondsLeft}s` : 'Renvoyer le code'}</button></div> : <button type="button" className="button button-outline auth-submit" onClick={() => void requestOtp('LOGIN')} disabled={isBusy || !isReady}>Envoyer un code de connexion <MessageSquareText size={16} /></button>}
                {isOtpScreen && <button className="button button-primary auth-submit" type="submit" disabled={isBusy}>{isBusy ? 'Vérification…' : 'Confirmer et se connecter'} <ArrowRight size={16} /></button>}
              </div>
            </>}
          </form>}
          {mode === 'login' && import.meta.env.DEV && <section className="demo-access-panel" aria-label="Comptes de démonstration"><div className="demo-access-heading"><span className="section-kicker">Aperçu local</span><strong>Essayer un compte démo</strong><p>Ces identifiants et profils sont fictifs.</p></div><div className="demo-access-list">{demoAccounts.map((account) => <button type="button" className="demo-access-item" key={account.phone} onClick={() => selectDemoAccount(account.phone)}><span><strong>{account.role}</strong><small>{account.displayPhone}</small></span><ArrowRight size={15} /></button>)}</div><p className="demo-access-password">Mot de passe commun : <code>{demoPassword}</code></p></section>}

          {mode === 'register' && <>
            {registerStep === 'phone' && <form onSubmit={(event) => { event.preventDefault(); void requestOtp('REGISTER'); }}>
              <label className="field auth-field"><span>Numéro de téléphone</span><PhoneNumberInput value={phone} dialingCode={dialingCode} onValueChange={(value) => { setPhone(value); setError(''); }} onDialingCodeChange={(code) => { setDialingCode(code); setError(''); }} /><small>Un code de vérification sera envoyé par SMS.</small></label>
              <button className="button button-primary auth-submit" type="submit" disabled={isBusy}>{isBusy ? 'Envoi du code…' : 'Recevoir le code'} <ArrowRight size={16} /></button>
              <p className="auth-consent"><ShieldCheck size={15} /> Votre numéro ne sera jamais publié.</p>
            </form>}
            {registerStep === 'otp' && <div className="otp-screen"><div className="otp-phone-summary"><span className="otp-phone-icon"><Smartphone size={19} /></span><span>Code envoyé au <strong>{phoneForApi(phone, dialingCode)}</strong></span><button type="button" onClick={() => { setRegisterStep('phone'); setError(''); }}>Modifier</button></div><OtpInput value={otp} onChange={setOtp} /><p className="otp-hint">Saisissez les 6 chiffres du SMS reçu.</p>{debugCode && <p className="dev-code"><KeyRound size={14} /> Code de test local : <strong>{debugCode}</strong></p>}{notice && <p className="form-notice" role="status">{notice}</p>}<div className="otp-actions-row"><button type="button" className="auth-text-button" disabled={secondsLeft > 0 || isBusy} onClick={() => void requestOtp('REGISTER')}>{secondsLeft > 0 ? `Renvoyer dans ${secondsLeft}s` : 'Renvoyer le code'}</button><span>Le code expire dans quelques minutes.</span></div><button type="button" className="button button-primary auth-submit" onClick={() => void verifyOtp('REGISTER')} disabled={isBusy}>{isBusy ? 'Vérification…' : 'Vérifier mon numéro'} <ArrowRight size={16} /></button></div>}
            {registerStep === 'profile' && <form onSubmit={(event) => void submitRegistration(event)}>
              <div className="verified-banner"><CheckCircle2 size={17} /><span><strong>Numéro vérifié</strong><small>{phoneForApi(phone, dialingCode)}</small></span><Check size={15} /></div>
              {isBtpSignup && <label className="field auth-field"><span>Nom de l’entreprise <b>*</b></span><input autoComplete="organization" value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="Ex. Bâtir & Rénover SARL" maxLength={140} /><small>Il s’agit du nom commercial affiché sur votre profil.</small></label>}
              <div className="form-grid form-grid-two auth-profile-grid"><label className="field"><span>Prénom</span><input autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} placeholder="Votre prénom" /></label><label className="field"><span>Nom</span><input autoComplete="family-name" value={lastName} onChange={(event) => setLastName(event.target.value)} placeholder="Votre nom" /></label><label className="field field-full"><span>{isBtpSignup ? 'Email professionnel' : 'Email'} <small>(facultatif)</small></span><input autoComplete="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="vous@exemple.com" /></label><label className="field field-full"><span>Mot de passe</span><div className="password-field"><input autoComplete="new-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="10 caractères minimum" /><button type="button" aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label><label className="field field-full"><span>Confirmer le mot de passe</span><div className="password-field"><input autoComplete="new-password" type={showConfirmation ? 'text' : 'password'} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Répétez le mot de passe" /><button type="button" aria-label={showConfirmation ? 'Masquer la confirmation' : 'Afficher la confirmation'} onClick={() => setShowConfirmation((visible) => !visible)}>{showConfirmation ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label></div>
              <label className="terms-check"><input type="checkbox" required /> <span>J’accepte les <Link to="/conditions">conditions d’utilisation</Link> et la politique de confidentialité de KEMTA.</span></label>
              <button className="button button-primary auth-submit" type="submit" disabled={isBusy}>{isBusy ? 'Création du compte…' : isBtpSignup ? 'Créer mon compte entreprise' : 'Créer mon compte'} <ArrowRight size={16} /></button>
            </form>}
          </>}

          {mode === 'reset' && <>
            {!otpFlow && <form onSubmit={(event) => { event.preventDefault(); void requestOtp('PASSWORD_RESET'); }}><label className="field auth-field"><span>Numéro de téléphone</span><PhoneNumberInput value={phone} dialingCode={dialingCode} onValueChange={(value) => { setPhone(value); setError(''); }} onDialingCodeChange={(code) => { setDialingCode(code); setError(''); }} /><small>Si un compte est associé à ce numéro, un code vous sera envoyé.</small></label><button className="button button-primary auth-submit" type="submit" disabled={isBusy}>{isBusy ? 'Envoi du code…' : 'Recevoir un code de réinitialisation'} <ArrowRight size={16} /></button></form>}
            {otpFlow === 'reset' && !otpToken && <div className="otp-screen"><div className="otp-phone-summary"><span className="otp-phone-icon"><Smartphone size={19} /></span><span>Code envoyé au <strong>{phoneForApi(phone, dialingCode)}</strong></span><button type="button" onClick={resetOtpFlow}>Modifier</button></div><OtpInput value={otp} onChange={setOtp} /><p className="otp-hint">Saisissez les 6 chiffres du SMS reçu.</p>{debugCode && <p className="dev-code"><KeyRound size={14} /> Code de test local : <strong>{debugCode}</strong></p>}<div className="otp-actions-row"><button type="button" className="auth-text-button" disabled={secondsLeft > 0 || isBusy} onClick={() => void requestOtp('PASSWORD_RESET')}>{secondsLeft > 0 ? `Renvoyer dans ${secondsLeft}s` : 'Renvoyer le code'}</button><span>Le code expire dans quelques minutes.</span></div><button type="button" className="button button-primary auth-submit" onClick={() => void verifyOtp('PASSWORD_RESET')} disabled={isBusy}>{isBusy ? 'Vérification…' : 'Vérifier le code'} <ArrowRight size={16} /></button></div>}
            {otpFlow === 'reset' && otpToken && <form onSubmit={(event) => void submitPasswordReset(event)}><div className="verified-banner"><CheckCircle2 size={17} /><span><strong>Numéro vérifié</strong><small>Choisissez un mot de passe robuste.</small></span></div><label className="field auth-field"><span>Nouveau mot de passe</span><div className="password-field"><input autoComplete="new-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="10 caractères minimum" /><button type="button" aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label><label className="field auth-field"><span>Confirmer le mot de passe</span><div className="password-field"><input autoComplete="new-password" type={showConfirmation ? 'text' : 'password'} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Répétez le mot de passe" /><button type="button" aria-label={showConfirmation ? 'Masquer la confirmation' : 'Afficher la confirmation'} onClick={() => setShowConfirmation((visible) => !visible)}>{showConfirmation ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label><button className="button button-primary auth-submit" type="submit" disabled={isBusy}>{isBusy ? 'Modification…' : 'Modifier mon mot de passe'} <ArrowRight size={16} /></button></form>}
            {notice && <p className="form-notice" role="status">{notice} <Link to="/connexion">Se connecter</Link></p>}
          </>}

          {error && <p className="form-error auth-error" role="alert">{error}</p>}
          <div className="auth-card-bottom">{mode === 'login' ? <p>Pas encore de compte ? <Link to="/inscription">Créer un compte</Link></p> : mode === 'register' ? <p>Vous avez déjà un compte ? <Link to="/connexion">Se connecter</Link></p> : <p>Vous vous souvenez du mot de passe ? <Link to="/connexion">Se connecter</Link></p>}</div>
          <div className="auth-secure-note"><ShieldCheck size={14} /> Vos informations sont accessibles aux personnes habilitées à traiter votre demande.</div>
        </section>
      </div>
      <footer className="auth-footer"><span>© {new Date().getFullYear()} KEMTA</span><span><Link to="/">Accueil</Link> · <a href="#confidentialite">Confidentialité</a></span></footer>
    </main>
  );
}
