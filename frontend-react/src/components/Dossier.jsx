import { Link } from "react-router-dom";

/* Cross-navigation between the publication's sections. Renders three large
   ink-stamp cards; whichever section you're currently on is dropped and the
   Home card takes its place. Section numbers are fixed (Home 00, Appendix 01,
   Pipeline 02, Prospectus 03) so each card keeps a stable identity everywhere. */

const Arrow = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
  </svg>
);

const CARDS = {
  home: {
    to: "/", no: "00 — Home", title: "The Front Page",
    desc: "Back to the masthead — what ALRM is, the live clause exhibit, and the four faculties at a glance.",
    cta: "Back to the front page",
  },
  appendix: {
    to: "/evals", no: "01 — Appendix", title: "The Statistical Appendix",
    desc: "Every measured figure — extraction F1 and grounding, the risk classifier, retrieval MRR/NDCG, and the end-to-end runs — charted, with the commands to reproduce each.",
    cta: "Open the appendix",
  },
  pipeline: {
    to: "/architecture", no: "02 — Pipeline", title: "The Pipeline",
    desc: "How a clause becomes a cited redline: six inspectable stages from intake to output, each with its source-file paths and measured stats.",
    cta: "Trace the pipeline",
  },
  prospectus: {
    to: "/overview", no: "03 — Prospectus", title: "The Prospectus",
    desc: "The sixty-second read — the problem, the hard parts, the measured results, and the stack — for anyone evaluating the engineering.",
    cta: "Read the prospectus",
  },
};

// Display order; the current section is filtered out and Home fills the gap.
const ORDER = ["home", "appendix", "pipeline", "prospectus"];

export default function Dossier({ current, heading = "The rest of the file", kicker = "Read deeper" }) {
  const shown = ORDER.filter((key) => key !== current);
  // Plain `article` (no `obs`): this is shared navigation and must always be
  // visible. The `obs` reveal class starts at opacity:0 and only un-hides when
  // the IntersectionObserver in Landing's useReveal adds `.in` — which doesn't
  // run on the inner pages, so `obs` here would leave the cards invisible but
  // still clickable.
  return (
    <section className="article">
      <div className="art-head">
        <span className="art-sec">Index</span>
        <h2 className="art-title">{heading}</h2>
        <span className="art-kicker">{kicker}</span>
      </div>
      <div className="dossier">
        {shown.map((key) => {
          const c = CARDS[key];
          return (
            <Link key={key} to={c.to} className="dossier-card">
              <span className="dossier-no">№ {c.no}</span>
              <span className="dossier-title">{c.title}</span>
              <span className="dossier-desc">{c.desc}</span>
              <span className="dossier-go">{c.cta} <Arrow /></span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
