import { Link, useLocation } from 'react-router-dom';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { SiteHeader } from '../components/SiteHeader';
import { SiteFooter } from '../components/SiteFooter';

const legalContent = {
  '/mentions-legales': {
    label: 'Informations légales',
    title: 'Mentions légales',
    intro: 'Les informations d’identification de l’entité exploitant KEMTA doivent être publiées et vérifiées avant toute ouverture commerciale.',
    sections: [
      ['Éditeur de la plateforme', 'KEMTA — dénomination sociale, forme juridique, adresse du siège, numéro RCCM, NIU et responsable de publication à compléter par l’entité exploitante.'],
      ['Hébergement', 'Le nom et les coordonnées de l’hébergeur de production seront indiqués ici après le choix définitif de l’infrastructure.'],
      ['Contact', 'Pour une question liée à la plateforme ou à un projet, utilisez le formulaire de demande KEMTA. Les coordonnées officielles seront ajoutées avant la mise en service commerciale.'],
      ['Propriété intellectuelle', 'Les textes, éléments visuels et composants de la plateforme sont protégés. Toute utilisation ou reproduction doit faire l’objet d’une autorisation de l’entité exploitante.'],
    ],
  },
  '/confidentialite': {
    label: 'Protection des données',
    title: 'Politique de confidentialité',
    intro: 'KEMTA traite les informations nécessaires à la gestion de votre compte, de vos demandes de service et de vos projets immobiliers.',
    sections: [
      ['Informations utilisées', 'Le numéro de téléphone est l’identifiant principal. Le nom et le prénom sont requis à la création du compte ; l’adresse email reste facultative. Une demande de service peut inclure une localisation, une description, des estimations et des photos ou documents transmis volontairement.'],
      ['Codes et sécurité du compte', 'Les codes OTP sont hachés et conservés temporairement dans un cache avec expiration ; ils ne sont pas enregistrés en clair dans la base de données. Les mots de passe sont hachés par Django. Le jeton de renouvellement de session est transmis dans un cookie HttpOnly.'],
      ['Utilisation et accès', 'Les informations servent à étudier les demandes, organiser les visites, suivre les projets, documenter les dépenses et communiquer les avancées. L’accès est limité aux personnes habilitées qui interviennent sur le service concerné.'],
      ['Fichiers et conservation', 'Les photos et documents sont conservés dans un stockage de fichiers séparé de la base de données. Les durées de conservation et les modalités de suppression doivent être fixées par l’entité exploitante avant le lancement commercial.'],
      ['Vos demandes', 'Pour demander l’accès, la rectification ou la suppression de vos données, précisez votre demande dans le formulaire KEMTA. Les coordonnées du responsable de traitement seront publiées dès leur validation.'],
      ['Cookies et mesure', 'L’application n’intègre pas de publicité comportementale. Un cookie HttpOnly sert au renouvellement sécurisé de la session. Les outils d’analyse éventuels devront être déclarés avant leur activation.'],
    ],
  },
  '/conditions': {
    label: 'Conditions d’utilisation',
    title: 'Conditions d’utilisation',
    intro: 'Cette version présente les principes de fonctionnement du service. Les conditions définitives doivent être validées par l’entité exploitante avant l’ouverture commerciale.',
    sections: [
      ['Compte et téléphone', 'Le compte est associé à un numéro de téléphone vérifié. Vous êtes responsable de la confidentialité de votre mot de passe et de l’accès à votre appareil. Signalez immédiatement toute utilisation suspecte.'],
      ['Demandes et accompagnement', 'L’envoi d’une demande permet à l’équipe KEMTA de préciser votre besoin. Le périmètre, les tarifs, les délais, les intervenants et les modalités de paiement sont confirmés séparément avant le démarrage d’une prestation.'],
      ['Informations de suivi', 'Les photos, rapports et budgets documentent l’avancement à partir des éléments disponibles. Ils n’exonèrent pas les parties de leurs obligations contractuelles et ne remplacent pas les validations qui doivent être effectuées sur le terrain.'],
      ['Entreprises BTP', 'Les entreprises sont responsables de l’exactitude de leurs profils, de leurs références et de leurs candidatures. Le badge KEMTA reflète un processus de vérification défini par la plateforme ; il ne constitue pas une garantie de résultat ni une recommandation financière.'],
      ['Évolution des conditions', 'La version applicable et sa date d’entrée en vigueur devront être publiées ici avant la mise en service commerciale.'],
    ],
  },
} as const;

export function LegalPage() {
  const { pathname } = useLocation();
  const content = legalContent[pathname as keyof typeof legalContent] ?? legalContent['/mentions-legales'];
  return <><SiteHeader /><main className="legal-page"><div className="page-container legal-container"><Link to="/" className="back-to-home"><ArrowLeft size={15} /> Retour à KEMTA</Link><div className="legal-heading"><span className="section-kicker">{content.label}</span><h1>{content.title}</h1><p>{content.intro}</p></div><div className="legal-review-note"><ShieldCheck size={18} /><p><strong>À valider avant la production.</strong> Les informations juridiques propres à l’entité KEMTA et les durées de conservation doivent être complétées et validées localement avant le lancement commercial.</p></div><div className="legal-content">{content.sections.map(([heading, body]) => <section key={heading}><h2>{heading}</h2><p>{body}</p></section>)}</div><div className="legal-next-step"><span>Vous avez une question sur votre projet ?</span><Link to="/demande">Contacter KEMTA <span aria-hidden="true">→</span></Link></div></div></main><SiteFooter /></>;
}
