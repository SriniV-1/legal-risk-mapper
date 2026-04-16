/**
 * LoadingOverlay — full-screen modal shown while /analyze runs.
 */
export default function LoadingOverlay({ show }) {
  if (!show) return null;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-sm w-full mx-4 text-center">
        <div className="w-14 h-14 mx-auto mb-4 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin" />
        <h3 className="text-base font-bold text-slate-900 mb-1">Analyzing document…</h3>
        <p className="text-xs text-slate-500">Running hybrid pattern + semantic analysis</p>
      </div>
    </div>
  );
}
