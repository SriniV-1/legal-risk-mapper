import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { lazy, Suspense, useEffect } from "react";

// Reset scroll to the top on every route change. React Router preserves the
// scroll position by default, so navigating from the bottom of one page (e.g.
// the dossier cards) would otherwise land you mid-page on the next one.
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

// Route-level code splitting: the landing page ships on its own and the
// heavier analysis/compare tools load on demand, so first paint isn't blocked
// by code the visitor may never reach.
const Landing = lazy(() => import("./pages/Landing.jsx"));
const AppPage = lazy(() => import("./pages/AppPage.jsx"));
const ComparePage = lazy(() => import("./pages/ComparePage.jsx"));
const EvalsPage = lazy(() => import("./pages/EvalsPage.jsx"));
const ArchitecturePage = lazy(() => import("./pages/ArchitecturePage.jsx"));
const OverviewPage = lazy(() => import("./pages/OverviewPage.jsx"));

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Suspense fallback={<div className="route-fallback" aria-busy="true" />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/evals" element={<EvalsPage />} />
          <Route path="/architecture" element={<ArchitecturePage />} />
          <Route path="/overview" element={<OverviewPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
