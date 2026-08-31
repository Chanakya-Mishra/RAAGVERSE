import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { WaveBars } from "@/components/Brand";
import { toast } from "sonner";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const location = useLocation();
  const nav = useNavigate();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      nav("/login", { replace: true });
      return;
    }
    const sessionId = match[1];
    // Clear hash from URL immediately
    window.history.replaceState({}, "", window.location.pathname);

    (async () => {
      try {
        const { data } = await api.post("/auth/google/callback", { session_id: sessionId });
        setUser(data.user);
        toast.success(`Welcome, ${data.user.name}`);
        nav("/admin", { replace: true });
      } catch (e) {
        toast.error(formatApiError(e.response?.data?.detail) || "Google sign-in failed");
        nav("/login", { replace: true });
      }
    })();
  }, [location, nav, setUser]);

  return (
    <div className="min-h-screen bg-mesh grain flex items-center justify-center flex-col gap-4 text-slate-300">
      <WaveBars className="text-orange-400" />
      <div className="font-display text-2xl">Tuning your session…</div>
    </div>
  );
}
