import { Link } from "react-router-dom";

/* Shared masthead for the publication's inner sections. `section` is the
   running head shown after the nameplate, e.g. "Statistical Appendix". */
export default function Masthead({ section }) {
  return (
    <header className="mast">
      <Link to="/" className="mast-mark">ALRM</Link>
      <span className="mast-rule" />
      <span className="mast-sub">{section}</span>
      <span className="mast-spacer" />
      <nav className="mast-nav" aria-label="Sections">
        <Link to="/evals">Appendix</Link>
        <Link to="/architecture">Pipeline</Link>
        <Link to="/overview">Prospectus</Link>
      </nav>
      <Link to="/app" className="mast-cta">Launch the Monitor</Link>
    </header>
  );
}
