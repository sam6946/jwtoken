import { Link } from 'react-router-dom';

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link className={`brand${light ? ' brand-light' : ''}`} to="/" aria-label="KEMTA, accueil">
      <span className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
        <i />
      </span>
      <span className="brand-word">KEMTA<span className="brand-dot">.</span></span>
    </Link>
  );
}
