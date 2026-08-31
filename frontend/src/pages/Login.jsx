import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Logo, WaveBars } from "@/components/Brand";
import { Eye, EyeOff, LogIn, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function googleLogin() {
  const redirectUrl = window.location.origin + "/admin";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const r = await login(email, password);
    setLoading(false);
    if (r.ok) {
      toast.success("Welcome back to the club.");
      nav(r.user?.role === "member" ? "/member" : "/admin");
    } else {
      toast.error(r.error || "Login failed");
    }
  };

  return (
    <div className="min-h-screen bg-mesh grain flex">
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12 relative">
        <Logo />
        <img
          src="https://images.unsplash.com/photo-1565035010268-a3816f98589a?w=1200"
          alt="Live music"
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
        <div className="relative z-10 max-w-md">
          <h2 className="font-display text-5xl font-black leading-tight mb-4">
            Command <span className="gradient-text">Center.</span>
          </h2>
          <p className="text-slate-300 text-lg">
            Sign in to manage members, events, sessions, and the gallery.
          </p>
        </div>
        <div className="relative z-10 text-xs font-mono uppercase tracking-widest text-slate-500 flex items-center gap-3">
          <WaveBars /> Admin access only · encrypted session
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <Link to="/" className="text-sm text-slate-400 hover:text-orange-400 flex items-center gap-1 mb-8" data-testid="back-to-home">
            <ArrowLeft size={14} /> Back to home
          </Link>
          <div className="lg:hidden mb-8"><Logo /></div>
          <h1 className="font-display text-4xl font-black mb-2">Sign in</h1>
          <p className="text-slate-400 mb-8 text-sm">Only registered admins can access the dashboard.</p>

          <form onSubmit={submit} className="space-y-4" data-testid="login-form">
            <div>
              <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">Email</label>
              <input
                type="email"
                className="input-field"
                placeholder="you@musicclub.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="login-email-input"
              />
            </div>
            <div>
              <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">Password</label>
              <div className="relative">
                <input
                  type={show ? "text" : "password"}
                  className="input-field pr-12"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  data-testid="login-password-input"
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-orange-400"
                  data-testid="toggle-password-visibility"
                >
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-sm">
              <Link to="/forgot-password" className="text-orange-400 hover:text-orange-300" data-testid="forgot-password-link">Forgot password?</Link>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center flex items-center gap-2"
              data-testid="login-submit-btn"
            >
              {loading ? "Signing in..." : <>Sign In <LogIn size={16} /></>}
            </button>

            <div className="relative py-2 flex items-center gap-3 text-[10px] font-mono uppercase tracking-widest text-slate-500">
              <div className="h-px bg-white/10 flex-1" /> or <div className="h-px bg-white/10 flex-1" />
            </div>

            <button
              type="button"
              onClick={googleLogin}
              className="w-full border border-white/10 hover:border-orange-500/40 bg-white/[0.02] hover:bg-white/[0.04] transition rounded-full py-3 flex items-center justify-center gap-3 text-sm font-medium"
              data-testid="google-login-btn"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
                <path fill="#EA4335" d="M12 10.2v3.6h5.06c-.22 1.4-1.63 4.1-5.06 4.1a5.9 5.9 0 1 1 0-11.8c1.85 0 3.09.79 3.8 1.47l2.6-2.5C16.87 3.61 14.66 2.7 12 2.7 6.87 2.7 2.7 6.87 2.7 12s4.17 9.3 9.3 9.3c5.37 0 8.93-3.77 8.93-9.08 0-.61-.07-1.08-.16-1.53H12z"/>
              </svg>
              Sign in with Google (Admins only)
            </button>
            <div className="text-[11px] text-slate-500 text-center leading-relaxed">Only <span className="text-orange-300 font-mono">mchanakya64@gmail.com</span> and <span className="text-orange-300 font-mono">siddharthsharma2649@gmail.com</span> can sign in with Google.</div>
          </form>
        </div>
      </div>
    </div>
  );
}
