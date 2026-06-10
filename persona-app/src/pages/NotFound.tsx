import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

export default function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center bg-surface px-4 text-center">
      <div className="flex flex-col items-center gap-4">
        <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary">
          <ShieldCheck size={24} />
        </span>
        <h1 className="text-2xl font-bold">Page not found</h1>
        <p className="text-on-surface-variant">That route doesn’t exist in PersonaLayer.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/app/persona" className="primary-button">Open control center</Link>
          <Link to="/" className="secondary-button">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
