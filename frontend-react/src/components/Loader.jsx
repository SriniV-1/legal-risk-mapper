export default function Loader({ message }) {
  return (
    <div className="loader-overlay">
      <div className="loader-spinner" />
      <div className="loader-text">{message || "Running…"}</div>
    </div>
  );
}
