import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowDown, ArrowRight, ArrowUpRight, BadgeCheck, Banknote, Building2,
  CalendarCheck2, Check, CheckCircle2, ChevronDown, ClipboardCheck,
  FileCheck2, HardHat, House, MapPin, MessageCircle, ShieldCheck, Smartphone,
  Wrench, Camera, Eye, BriefcaseBusiness,
} from 'lucide-react';
import { SiteHeader } from '../components/SiteHeader';
import { SiteFooter } from '../components/SiteFooter';

const services = [
  {
    number: '01',
    icon: HardHat,
    title: 'Suivi de chantier',
    description: 'De la préparation à la livraison, gardez une vision claire de chaque étape.',
    label: 'Je veux construire',
    query: 'service=BUILD',
  },
  {
    number: '02',
    icon: ClipboardCheck,
    title: 'Suivi d’un chantier existant',
    description: 'Reprenez le contrôle avec un état des lieux, des constats et un plan de suivi.',
    label: 'Mon chantier a commencé',
    query: 'service=TAKEOVER',
  },
  {
    number: '03',
    icon: House,
    title: 'Entretien immobilier',
    description: 'Inspection, petites réparations et rapports pour un bien entretenu toute l’année.',
    label: 'Entretenir mon bien',
    query: 'service=MAINTENANCE',
  },
];

const methodSteps = [
  { icon: MessageCircle, title: 'Vous expliquez', text: 'Votre besoin, simplement.' },
  { icon: ClipboardCheck, title: 'KEMTA prépare', text: 'Un cadre clair pour la mission.' },
  { icon: HardHat, title: 'Le terrain avance', text: 'Un suivi adapté à votre projet.' },
  { icon: Camera, title: 'Les preuves remontent', text: 'Photos et constats datés.' },
  { icon: FileCheck2, title: 'Vous décidez', text: 'Un rapport facile à comprendre.' },
];

const faqItems = [
  {
    question: 'Comment fonctionne KEMTA ?',
    answer: 'Vous décrivez votre besoin en quelques étapes. L’équipe KEMTA étudie votre demande, clarifie le périmètre avec vous, puis organise le suivi ou la visite adaptée. Les constats et les prochaines actions sont partagés dans votre espace.',
  },
  {
    question: 'Puis-je suivre mon chantier depuis l’étranger ?',
    answer: 'Oui. Le suivi est conçu pour garder le propriétaire informé à distance grâce aux photos, aux étapes d’avancement, aux dépenses documentées et aux rapports accessibles depuis son espace.',
  },
  {
    question: 'Quels types de projets pouvez-vous suivre ?',
    answer: 'Maisons, villas, immeubles et travaux de rénovation ou de remise en état. Chaque demande est étudiée selon la localisation, l’état du chantier et le niveau d’accompagnement souhaité.',
  },
  {
    question: 'Comment sont contrôlées les dépenses ?',
    answer: 'Les dépenses sont présentées avec leur contexte et les justificatifs disponibles. Le budget prévisionnel, le montant engagé et le montant restant sont affichés séparément pour faciliter la vérification.',
  },
  {
    question: 'Puis-je demander uniquement une visite de chantier ?',
    answer: 'Oui. Vous pouvez demander une visite ponctuelle ou un état des lieux, sans souscrire à un suivi complet. Précisez simplement votre objectif dans le formulaire de demande.',
  },
  {
    question: 'Comment devenir entreprise partenaire KEMTA ?',
    answer: 'Créez un compte entreprise, complétez votre profil et transmettez les informations de vérification demandées. Une fois votre profil contrôlé, vous pourrez présenter vos réalisations et répondre aux opportunités publiées.',
  },
];

function Hero() {
  return (
    <section className="hero-section">
      <div className="hero-grid page-container">
        <div className="hero-copy">
          <span className="eyebrow"><span className="eyebrow-dot" /> Construire · suivre · entretenir</span>
          <h1>Votre projet immobilier au Cameroun, <em>suivi en confiance.</em></h1>
          <p className="hero-lede">De la construction à l’entretien, KEMTA vous aide à garder le contrôle de vos projets et de vos biens, même à distance.</p>
          <div className="hero-actions">
            <Link className="button button-primary button-large" to="/demande">Demander un service <ArrowUpRight size={17} /></Link>
            <a className="button button-quiet button-large" href="#methode">Découvrir KEMTA <ArrowDown size={16} /></a>
          </div>
          <div className="hero-assurance">
            <span className="assurance-icon"><ShieldCheck size={17} /></span>
            <span>Un suivi documenté, pensé pour les réalités du terrain.</span>
          </div>
        </div>
        <div className="hero-visual">
          <img
            className="hero-image"
            src="/images/kemta-hero.webp"
            srcSet="/images/kemta-hero-640.webp 640w, /images/kemta-hero.webp 1440w"
            sizes="(max-width: 780px) 100vw, 52vw"
            width="1440"
            height="960"
            fetchPriority="high"
            alt="Une ingénieure camerounaise consulte le suivi d’un chantier avec un professionnel sur le terrain."
          />
          <div className="hero-image-caption"><span>DOUALA, CAMEROUN</span><span>Un chantier suivi, étape par étape</span></div>
          <div className="floating-progress" aria-label="Exemple de progression d'un projet">
            <div className="floating-progress-top"><span className="mini-status"><i /> Exemple de suivi</span><span className="floating-more">···</span></div>
            <div className="floating-project-name"><span className="project-avatar"><House size={18} /></span><span><strong>Villa familiale</strong><small>Douala · Chantier</small></span></div>
            <div className="floating-progress-foot"><div><span>Avancement indicatif</span><strong>72%</strong></div><div className="progress-track"><span style={{ width: '72%' }} /></div></div>
          </div>
          <div className="hero-stamp"><BadgeCheck size={17} /><span>La confiance<br />se construit.</span></div>
        </div>
      </div>
    </section>
  );
}

function TrustStrip() {
  return (
    <section className="trust-strip">
      <div className="page-container trust-inner">
        <p>Plus de clarté, à chaque étape</p>
        <div><span><CheckCircle2 size={17} /> Des preuves terrain datées</span><i /> <span><ShieldCheck size={17} /> Des dépenses documentées</span><i /> <span><Smartphone size={17} /> Un suivi accessible à distance</span></div>
      </div>
    </section>
  );
}

function ServicesSection() {
  return (
    <section className="section services-section" id="services">
      <div className="page-container">
        <div className="section-heading section-heading-split">
          <div><span className="section-kicker">Nos services</span><h2>Votre besoin.<br /><span>Notre méthode.</span></h2></div>
          <p>Un projet à lancer, un chantier déjà en cours ou un bien à entretenir ? Choisissez le niveau d’accompagnement qui vous correspond.</p>
        </div>
        <div className="services-grid">
          {services.map(({ number, icon: Icon, title, description, label, query }) => (
            <article className="service-item" key={number}>
              <div className="service-head"><span className="service-index">{number}</span><span className="service-icon"><Icon size={23} strokeWidth={1.7} /></span></div>
              <h3>{title}</h3>
              <p>{description}</p>
              <Link to={`/demande?${query}`} className="text-link">{label}<ArrowRight size={16} /></Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function MethodSection() {
  return (
    <section className="section method-section" id="methode">
      <div className="page-container">
        <div className="section-heading section-heading-center">
          <span className="section-kicker">Comment ça marche</span>
          <h2>Simple comme ça.</h2>
          <p>Du premier échange au rapport terrain, vous savez toujours où vous en êtes.</p>
        </div>
        <div className="method-line">
          {methodSteps.map(({ icon: Icon, title, text }, index) => (
            <div className="method-step" key={title}>
              <div className="method-node"><Icon size={20} strokeWidth={1.8} /><span>{String(index + 1).padStart(2, '0')}</span></div>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </div>
        <div className="method-note"><ShieldCheck size={17} /> Vous gardez la main sur les décisions importantes.</div>
      </div>
    </section>
  );
}

function TrackingSection() {
  const steps = [
    { label: 'Étude & préparation', state: 'done' },
    { label: 'Fondations', state: 'done' },
    { label: 'Murs & structure', state: 'done' },
    { label: 'Toiture', state: 'current' },
    { label: 'Électricité', state: 'next' },
    { label: 'Finitions', state: 'next' },
  ];
  return (
    <section className="section tracking-section" id="suivi">
      <div className="page-container tracking-layout">
        <div className="tracking-copy">
          <span className="section-kicker">Un chantier, en un seul regard</span>
          <h2>Vous voyez<br />l’essentiel. <span>Tout de suite.</span></h2>
          <p>Une vue claire sur l’avancement, les étapes terminées et les prochaines actions. Fini les nouvelles à chercher dans plusieurs conversations.</p>
          <ul className="check-list">
            <li><Check size={17} /> Une progression lisible</li>
            <li><Check size={17} /> Une chronologie des étapes</li>
            <li><Check size={17} /> Les points d’attention visibles</li>
          </ul>
          <Link className="text-link" to="/demande?service=BUILD">Parler de mon projet <ArrowRight size={16} /></Link>
        </div>
        <div className="tracking-preview" aria-label="Aperçu illustratif du suivi d'un chantier">
          <div className="preview-topline"><span className="preview-brand-dot" /> <span>ESPACE PROJET</span><span className="preview-time">Aperçu</span></div>
          <div className="preview-project-head"><div><p>PROJET IMMOBILIER</p><h3>Villa familiale</h3><span className="preview-place"><MapPin size={13} /> Douala, Cameroun</span></div><span className="preview-pill"><i /> En cours</span></div>
          <div className="preview-progress-copy"><span>Avancement global</span><strong>72<span>%</span></strong></div>
          <div className="preview-progress-track"><span style={{ width: '72%' }} /></div>
          <div className="preview-estimate"><span>Étape en cours</span><strong>Toiture</strong><span>Prochaine étape : électricité</span></div>
          <div className="preview-divider" />
          <div className="preview-phases">
            {steps.map(({ label, state }) => (
              <div className={`preview-phase phase-${state}`} key={label}>
                <span className="phase-mark">{state === 'done' ? <Check size={12} /> : state === 'current' ? <i /> : null}</span>
                <span>{label}</span>
                <small>{state === 'done' ? 'Terminée' : state === 'current' ? 'En cours' : 'À venir'}</small>
              </div>
            ))}
          </div>
          <div className="preview-footer"><span><CalendarCheck2 size={15} /> Dernière mise à jour</span><strong>Exemple de suivi</strong></div>
        </div>
      </div>
    </section>
  );
}

function EvidenceSection() {
  return (
    <section className="section evidence-section">
      <div className="page-container evidence-layout">
        <div className="evidence-photo-wrap">
          <img
            src="/images/kemta-evidence.webp"
            srcSet="/images/kemta-evidence-640.webp 640w, /images/kemta-evidence.webp 1440w"
            sizes="(max-width: 780px) 100vw, 50vw"
            width="1440"
            height="1080"
            loading="lazy"
            alt="Un superviseur de chantier documente l’avancement des travaux avec son téléphone."
          />
          <div className="evidence-date"><Camera size={15} /><span>Preuve terrain</span><strong>Exemple</strong></div>
        </div>
        <div className="evidence-copy">
          <span className="section-kicker">Les preuves, pas les promesses</span>
          <h2>Le terrain,<br /><span>en toute transparence.</span></h2>
          <p>Chaque point de suivi peut être illustré par des photos, une date, une localisation et un commentaire. Vous comprenez ce qui a été fait, sans interprétation.</p>
          <div className="evidence-meta">
            <div><span className="meta-icon meta-green"><CheckCircle2 size={18} /></span><span><strong>Une date claire</strong><small>Quand le constat a été réalisé</small></span></div>
            <div><span className="meta-icon meta-blue"><MapPin size={18} /></span><span><strong>Un lieu identifié</strong><small>Le chantier concerné</small></span></div>
            <div><span className="meta-icon meta-sand"><MessageCircle size={18} /></span><span><strong>Un contexte utile</strong><small>Ce qu’il faut retenir de l’image</small></span></div>
          </div>
        </div>
      </div>
    </section>
  );
}

function BudgetSection() {
  return (
    <section className="section budget-section">
      <div className="page-container budget-layout">
        <div className="budget-copy">
          <span className="section-kicker">Maîtrise du budget</span>
          <h2>Le budget,<br /><span>sans zone grise.</span></h2>
          <p>Comparez le budget prévu, les dépenses documentées et le montant restant. Une information financière claire aide à prendre les bonnes décisions au bon moment.</p>
          <Link className="text-link" to="/demande">En savoir plus sur le suivi <ArrowRight size={16} /></Link>
        </div>
        <div className="budget-example">
          <div className="budget-example-head"><div><span className="budget-icon"><Banknote size={18} /></span><span><small>BUDGET DU PROJET</small><strong>Exemple illustratif</strong></span></div><span className="budget-menu">···</span></div>
          <div className="budget-total">25 000 000 <small>FCFA</small></div>
          <div className="budget-bar-label"><span>Utilisé</span><strong>74%</strong></div>
          <div className="budget-bar"><span style={{ width: '74%' }} /></div>
          <div className="budget-numbers">
            <div><i className="spent-dot" /><span>Dépensé</span><strong>18,5 M <small>FCFA</small></strong></div>
            <div><i className="remaining-dot" /><span>Restant</span><strong>6,5 M <small>FCFA</small></strong></div>
          </div>
          <div className="budget-note"><ShieldCheck size={16} /><span>Montants à rapprocher des pièces justificatives.</span></div>
        </div>
      </div>
    </section>
  );
}

function MaintenanceSection() {
  const careSteps = [
    { icon: House, title: 'Votre propriété', text: 'Lieu et besoins identifiés.' },
    { icon: Eye, title: 'Une visite', text: 'Inspection sur place.' },
    { icon: Camera, title: 'Des constats', text: 'Photos et points d’attention.' },
    { icon: FileCheck2, title: 'Un rapport', text: 'Un résumé à distance.' },
  ];
  return (
    <section className="section maintenance-section" id="entretien">
      <div className="page-container maintenance-layout">
        <div className="maintenance-visual">
          <img
            src="/images/kemta-maintenance.webp"
            srcSet="/images/kemta-maintenance-640.webp 640w, /images/kemta-maintenance.webp 1440w"
            sizes="(max-width: 780px) 100vw, 51vw"
            width="1440"
            height="960"
            loading="lazy"
            alt="Maison contemporaine entretenue dans un jardin tropical au Cameroun."
          />
          <div className="maintenance-caption"><span className="maintenance-caption-icon"><Wrench size={17} /></span><span><strong>Prendre soin du bien</strong><small>Visite · entretien · compte rendu</small></span></div>
        </div>
        <div className="maintenance-copy">
          <span className="section-kicker">Entretien immobilier</span>
          <h2>Votre bien reste suivi,<br /><span>même quand vous êtes loin.</span></h2>
          <p>Organisez une inspection, un nettoyage, une petite réparation ou un contrôle régulier. Vous recevez un compte rendu simple et des photos après la visite.</p>
          <div className="care-flow">
            {careSteps.map(({ icon: Icon, title, text }, index) => (
              <div className="care-step" key={title}><span className="care-icon"><Icon size={18} /></span><span><strong>{title}</strong><small>{text}</small></span>{index < careSteps.length - 1 && <ArrowRight className="care-arrow" size={14} />}</div>
            ))}
          </div>
          <Link className="button button-primary" to="/demande?service=MAINTENANCE">Organiser un entretien <ArrowUpRight size={16} /></Link>
        </div>
      </div>
    </section>
  );
}

function BtpSection() {
  const btpSteps = [
    { icon: Building2, title: 'Votre entreprise' },
    { icon: Camera, title: 'Vos réalisations' },
    { icon: BriefcaseBusiness, title: 'Les opportunités' },
    { icon: FileCheck2, title: 'Vos candidatures' },
  ];
  return (
    <section className="section btp-section" id="kemta-btp">
      <div className="page-container btp-layout">
        <div className="btp-copy">
          <span className="section-kicker section-kicker-light">KEMTA BTP</span>
          <h2>Votre savoir-faire<br />mérite d’être <em>vu.</em></h2>
          <p>Présentez votre entreprise, mettez vos réalisations en valeur et accédez à de nouvelles opportunités immobilières au Cameroun.</p>
          <div className="btp-benefits"><span><Check size={16} /> Un profil professionnel</span><span><Check size={16} /> Un catalogue de réalisations</span><span><Check size={16} /> Des candidatures suivies</span></div>
          <Link className="button button-light button-large" to="/inscription?role=BTP_COMPANY">Créer mon profil entreprise <ArrowUpRight size={16} /></Link>
          <p className="btp-footnote"><ShieldCheck size={14} /> La vérification des profils est effectuée par l’équipe KEMTA.</p>
        </div>
        <div className="btp-illustration" aria-label="Parcours d'une entreprise BTP sur KEMTA">
          <div className="btp-card-top"><div className="btp-avatar"><Building2 size={21} /></div><span><small>ESPACE ENTREPRISE</small><strong>Votre activité, mieux présentée</strong></span><ArrowUpRight size={18} /></div>
          <div className="btp-path">
            {btpSteps.map(({ icon: Icon, title }, index) => <div className="btp-path-step" key={title}><span className={`btp-path-icon${index === 0 ? ' btp-path-active' : ''}`}><Icon size={18} /></span><span>{title}</span>{index < btpSteps.length - 1 && <span className="btp-path-line" />}</div>)}
          </div>
          <div className="btp-opportunity-sample"><div><span className="opportunity-label"><i /> ESPACE OPPORTUNITÉS</span><strong>Des projets adaptés à votre expertise.</strong><small>Consultez les appels ouverts et suivez vos réponses depuis un seul espace.</small></div><span className="opportunity-arrow"><ArrowRight size={17} /></span></div>
        </div>
      </div>
    </section>
  );
}

function TrustValues() {
  return (
    <section className="section values-section">
      <div className="page-container">
        <div className="section-heading section-heading-center">
          <span className="section-kicker">Notre engagement</span>
          <h2>La confiance se construit sur des faits.</h2>
        </div>
        <div className="values-grid">
          <article><span className="value-icon"><BadgeCheck size={21} /></span><h3>Des informations vérifiables</h3><p>Chaque avancée est reliée à des éléments concrets : étapes, photos, constats et justificatifs disponibles.</p></article>
          <article><span className="value-icon"><MessageCircle size={21} /></span><h3>Une communication claire</h3><p>Les décisions, les questions et les prochaines actions sont rassemblées au même endroit.</p></article>
          <article><span className="value-icon"><ShieldCheck size={21} /></span><h3>Un cadre adapté au terrain</h3><p>Un accompagnement pensé pour les propriétaires au Cameroun et ceux qui suivent leur bien à distance.</p></article>
        </div>
      </div>
    </section>
  );
}

function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  return (
    <section className="section faq-section" id="faq">
      <div className="page-container faq-layout">
        <div className="faq-intro"><span className="section-kicker">Questions fréquentes</span><h2>Une question ?<br /><span>On vous répond.</span></h2><p>Vous ne trouvez pas l’information recherchée ? Décrivez votre besoin, nous vous aiderons à y voir plus clair.</p><Link className="text-link" to="/demande">Poser une question <ArrowRight size={16} /></Link></div>
        <div className="faq-list">
          {faqItems.map(({ question, answer }, index) => {
            const isOpen = openIndex === index;
            return <article className={`faq-item${isOpen ? ' faq-open' : ''}`} key={question}>
              <button className="faq-question" aria-expanded={isOpen} onClick={() => setOpenIndex(isOpen ? null : index)}><span>{question}</span><ChevronDown size={18} /></button>
              {isOpen && <p className="faq-answer">{answer}</p>}
            </article>;
          })}
        </div>
      </div>
    </section>
  );
}

export function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <TrustStrip />
        <ServicesSection />
        <MethodSection />
        <TrackingSection />
        <EvidenceSection />
        <BudgetSection />
        <MaintenanceSection />
        <BtpSection />
        <TrustValues />
        <FaqSection />
        <section className="final-cta">
          <div className="page-container final-cta-inner">
            <div><span className="section-kicker section-kicker-light">Le premier pas est simple</span><h2>Votre projet mérite<br />un suivi à la hauteur.</h2><p>Parlez-nous de votre besoin. Nous vous aiderons à définir la suite.</p></div>
            <Link className="button button-light button-large" to="/demande">Demander un service <ArrowUpRight size={17} /></Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
