import { BrowserRouter, Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";

// Route-level code splitting: the landing page ships on its own and the
// heavier analysis/compare tools load on demand, so first paint isn't blocked
// by code the visitor may never reach.
const Landing = lazy(() => import("./pages/Landing.jsx"));
const AppPage = lazy(() => import("./pages/AppPage.jsx"));
const ComparePage = lazy(() => import("./pages/ComparePage.jsx"));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="route-fallback" aria-busy="true" />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppPage />} />
          <Route path="/compare" element={<ComparePage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
