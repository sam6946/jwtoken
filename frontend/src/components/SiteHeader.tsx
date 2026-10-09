import { useState } from 'react';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { Brand } from './Brand';

export function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user } = useAuth();
  const closeMenu = () => setMenuOpen(false);

  return (
    <header className="site-header">
      <div className="header-inner page-container">
        <Brand />
        <button
          className="menu-toggle"
          aria-label={menuOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((current) => !current)}
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <nav className={`main-nav${menuOpen ? ' main-nav-open' : ''}`} aria-label="Navigation principale">
          <a href="#services" onClick={closeMenu}>Nos services</a>
          <a href="#methode" onClick={closeMenu}>Comment ça marche</a>
          <a href="#kemta-btp" onClick={closeMenu}>KEMTA BTP</a>
          <Link to="/entreprises-btp" onClick={closeMenu}>Catalogue</Link>
          <Link to="/opportunites" onClick={closeMenu}>Opportunités</Link>
        </nav>
        <div className="header-actions">
          {user ? (
            <Link className="header-login" to="/dashboard">Mon espace</Link>
          ) : (
            <Link className="header-login" to="/connexion">Se connecter</Link>
          )}
          <Link className="button button-primary button-small header-cta" to="/demande">
            Demander un service <ArrowUpRight size={15} strokeWidth={2.3} />
          </Link>
        </div>
      </div>
    </header>
  );
}
