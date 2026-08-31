import { Music4 } from "lucide-react";
import { Link } from "react-router-dom";

export function Logo({ small }) {
  return (
    <Link to="/" className="flex items-center gap-2" data-testid="brand-logo">
      <div className="relative">
        <div className="absolute inset-0 blur-lg opacity-70 bg-gradient-to-br from-orange-500 via-red-500 to-violet-500 rounded-full" />
        <div className="relative bg-[#0B0C10] border border-orange-500/40 rounded-full p-1.5">
          <Music4 className="text-orange-400" size={small ? 14 : 18} />
        </div>
      </div>
      <div className="flex flex-col leading-none">
        <span className={`font-display font-black ${small ? "text-sm" : "text-base"} tracking-tight`}>THE MUSIC CLUB</span>
        <span className="text-[9px] uppercase tracking-[0.28em] text-orange-400 mt-0.5">Express Yourself</span>
      </div>
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
