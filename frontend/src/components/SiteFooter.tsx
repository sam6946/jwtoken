import { ArrowUpRight, Mail, MapPin } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Brand } from './Brand';

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="page-container">
        <div className="footer-main">
          <div className="footer-brand-block">
            <Brand light />
            <p>Construire avec confiance.<br />Au Cameroun, où que vous soyez.</p>
            <Link className="footer-contact-link" to="/demande"><Mail size={16} /> Écrivez-nous via le formulaire</Link>
          </div>
          <div className="footer-links-group">
            <h3>Pour les propriétaires</h3>
            <a href="#services">Suivi de chantier</a>
            <a href="#services">Chantier existant</a>
            <a href="#entretien">Entretien immobilier</a>
            <Link to="/demande">Demander un service <ArrowUpRight size={13} /></Link>
          </div>
          <div className="footer-links-group">
            <h3>Pour les professionnels</h3>
            <a href="#kemta-btp">KEMTA BTP</a>
            <Link to="/entreprises-btp">Catalogue BTP</Link>
            <Link to="/opportunites">Opportunités</Link>
            <Link to="/inscription?role=BTP_COMPANY">Créer mon profil entreprise</Link>
            <Link to="/connexion">Espace entreprise</Link>
          </div>
          <div className="footer-contact" id="contact">
            <h3>Parlons de votre projet</h3>
            <Link to="/demande"><Mail size={15} /> Nous contacter</Link>
            <span><MapPin size={15} /> Cameroun</span>
            <small>Un membre de l'équipe pourra vous recontacter après l'envoi de votre demande.</small>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} KEMTA. Tous droits réservés.</span>
          <div><Link to="/mentions-legales">Mentions légales</Link><Link to="/confidentialite">Confidentialité</Link></div>
          <span className="footer-made">Une plateforme pensée pour le Cameroun <span>♥</span></span>
        </div>
      </div>
    </footer>
  );
}
