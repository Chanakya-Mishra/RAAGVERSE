import { Link } from "react-router-dom";

export function Logo({ small }) {
  return (
    <Link to="/" className="flex flex-col leading-none" data-testid="brand-logo">
      <span className={`font-display font-black ${small ? "text-sm" : "text-lg"} tracking-tight gradient-text`}>BANDISH</span>
      <span className="text-[9px] uppercase tracking-[0.34em] text-orange-400 mt-0.5">Express Yourself</span>
    </Link>
  );
}

export function WaveBars({ className = "text-orange-400" }) {
  return (
    <span className={`inline-flex items-end h-5 ${className}`} aria-hidden>
      <span className="wave-bar" />
      <span className="wave-bar" />
      <span className="wave-bar" />
      <span className="wave-bar" />
      <span className="wave-bar" />
    </span>
  );
}
