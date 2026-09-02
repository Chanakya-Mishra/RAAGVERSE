import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Logo, WaveBars } from "@/components/Brand";
import { LogOut, Calendar, MapPin, CheckCircle2, XCircle, Ticket, UserCog, X, Save } from "lucide-react";
import { toast } from "sonner";

export default function MemberDashboard() {
  const { user, logout, refresh } = useAuth();
  const nav = useNavigate();
  const [events, setEvents] = useState([]);
  const [myRsvps, setMyRsvps] = useState([]);
  const [profileOpen, setProfileOpen] = useState(false);
  const [pForm, setPForm] = useState({ name: "", phone_number: "", instrument: "", bio: "" });
  const [savingProfile, setSavingProfile] = useState(false);

  const load = async () => {
    try {
      const [e, r] = await Promise.all([
        api.get("/public/events"),
        api.get("/me/rsvps"),
      ]);
      setEvents(e.data.events || []);
      setMyRsvps(r.data.rsvps || []);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  useEffect(() => { if (user && user.role === "member") load(); }, [user]);
  useEffect(() => {
    if (user) setPForm({ name: user.name || "", phone_number: user.phone_number || "", instrument: user.instrument || "", bio: user.bio || "" });
  }, [user]);

  if (user === null) return <div className="min-h-screen bg-mesh flex items-center justify-center text-slate-400">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;

  const rsvpMap = new Map(myRsvps.map((r) => [r.event_id, r]));

  const rsvp = async (eventId) => {
    try {
      const { data } = await api.post(`/events/${eventId}/rsvp`);
      if (data.rsvp?.status === "waitlisted") {
        toast.success(`Waitlisted — you're #${data.rsvp.waitlist_position} in line. We'll email if a seat opens.`);
      } else {
        toast.success("You're in — see you at the jam!");
      }
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };
  const cancel = async (eventId) => {
    if (!confirm("Cancel your RSVP?")) return;
    try { await api.delete(`/events/${eventId}/rsvp`); toast.success("RSVP cancelled"); load(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <div className="min-h-screen bg-mesh grain">
      <header className="glass sticky top-0 z-40 border-b border-white/5">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <Logo />
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-500 to-violet-500 flex items-center justify-center font-display font-black text-sm">{(user.name || "M")[0]}</div>
              <div>
                <div className="text-sm font-semibold">{user.name}</div>
                <div className="text-[10px] uppercase tracking-widest text-violet-300 font-mono">Member</div>
              </div>
            </div>
            <button onClick={() => setProfileOpen(true)} className="btn-ghost text-sm flex items-center gap-2" data-testid="edit-profile-btn"><UserCog size={14} /> Profile</button>
            <button onClick={async () => { await logout(); nav("/login"); }} className="btn-ghost text-sm flex items-center gap-2" data-testid="member-logout-btn"><LogOut size={14} /> Sign Out</button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-12">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-2 flex items-center gap-2"><WaveBars /> Member Lounge</div>
        <h1 className="font-display text-4xl font-black mb-2">Welcome, {user.name.split(" ")[0]}.</h1>
        <p className="text-slate-400 mb-10">RSVP with one tap. Chanakya and Siddharth will see you on the list.</p>

        <div className="grid lg:grid-cols-3 gap-6">
          <section className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <Calendar className="text-orange-400" size={18} />
              <h2 className="font-display text-2xl font-bold">Upcoming Events</h2>
            </div>
            <div className="space-y-3" data-testid="member-events">
              {events.length === 0 && <div className="card p-6 text-slate-500 italic">No events yet.</div>}
              {events.map((e) => {
                const r = rsvpMap.get(e.id);
                return (
                  <div key={e.id} className="card p-5 flex gap-4">
                    {e.image_url && <img src={e.image_url.startsWith("/api") ? `${process.env.REACT_APP_BACKEND_URL}${e.image_url}` : e.image_url} alt={e.title} className="w-28 h-28 object-cover rounded-lg" />}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-[10px] font-mono uppercase tracking-widest text-orange-300 border border-orange-500/30 rounded-full px-2 py-0.5">{e.event_type}</span>
                        <span className="text-xs text-slate-500 font-mono">{new Date(e.date).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>
                        <span className="text-xs text-slate-500 font-mono flex items-center gap-1"><MapPin size={11} /> {e.location}</span>
                      </div>
                      <div className="font-display text-lg font-bold">{e.title}</div>
                      <div className="text-xs text-slate-400 mt-1 line-clamp-2 mb-3">{e.description}</div>
                      {r ? (
                        <button onClick={() => cancel(e.id)} className="text-sm text-red-300 border border-red-500/30 bg-red-500/10 rounded-full px-3 py-1.5 flex items-center gap-1.5 hover:bg-red-500/20 transition" data-testid={`cancel-rsvp-${e.id}`}>
                          <XCircle size={14} /> Cancel {r.status === "waitlisted" ? `Waitlist (#${r.waitlist_position || "?"})` : "RSVP"}
                        </button>
                      ) : (
                        <button onClick={() => rsvp(e.id)} className="btn-primary text-sm py-1.5 px-4 flex items-center gap-1.5" data-testid={`rsvp-${e.id}`}>
                          <Ticket size={14} /> RSVP
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <aside>
            <div className="flex items-center gap-3 mb-4">
              <CheckCircle2 className="text-emerald-400" size={18} />
              <h2 className="font-display text-2xl font-bold">My RSVPs</h2>
            </div>
            <div className="space-y-3" data-testid="my-rsvps">
              {myRsvps.length === 0 && <div className="card p-5 text-slate-500 italic text-sm">You haven't RSVP'd to anything yet.</div>}
              {myRsvps.map((r) => (
                <div key={r.id} className="card p-4">
                  <div className="text-xs text-slate-500 font-mono">{r.event?.event_type} · {r.event?.date && new Date(r.event.date).toLocaleDateString()}</div>
                  <div className="font-display text-base font-bold mt-1">{r.event?.title || "Event"}</div>
                  {r.status === "waitlisted" ? (
                    <div className="text-[11px] text-amber-400 mt-1 uppercase tracking-widest font-mono">Waitlist · #{r.waitlist_position || "?"}</div>
                  ) : (
                    <div className="text-[11px] text-emerald-400 mt-1 uppercase tracking-widest font-mono">Confirmed</div>
                  )}
                </div>
              ))}
            </div>
          </aside>
        </div>
      </main>

      {profileOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur flex items-center justify-center p-4" onClick={() => setProfileOpen(false)}>
          <div className="card p-6 w-full max-w-md relative" onClick={(e) => e.stopPropagation()} data-testid="member-profile-modal">
            <button onClick={() => setProfileOpen(false)} className="absolute top-4 right-4 text-slate-400 hover:text-white" data-testid="profile-close-btn"><X size={18} /></button>
            <div className="font-display text-2xl font-bold mb-1">Your Profile</div>
            <div className="text-sm text-slate-400 mb-5">Add a phone number to enable SMS-based password reset.</div>
            <form
              className="space-y-3"
              onSubmit={async (ev) => {
                ev.preventDefault();
                setSavingProfile(true);
                try {
                  await api.put("/auth/me", { name: pForm.name, phone_number: pForm.phone_number || null, instrument: pForm.instrument || null, bio: pForm.bio || null });
                  await refresh();
                  toast.success("Profile updated");
                  setProfileOpen(false);
                } catch (er) { toast.error(formatApiError(er.response?.data?.detail)); }
                finally { setSavingProfile(false); }
              }}
              data-testid="member-profile-form"
            >
              <input className="input-field" placeholder="Full name" value={pForm.name} onChange={(e) => setPForm({ ...pForm, name: e.target.value })} required data-testid="profile-name-input" />
              <input className="input-field" type="tel" placeholder="Phone (E.164, e.g. +14155552671)" value={pForm.phone_number} onChange={(e) => setPForm({ ...pForm, phone_number: e.target.value })} data-testid="profile-phone-input" />
              <input className="input-field" placeholder="Instrument" value={pForm.instrument} onChange={(e) => setPForm({ ...pForm, instrument: e.target.value })} data-testid="profile-instrument-input" />
              <textarea className="input-field" rows={3} placeholder="Bio (optional)" value={pForm.bio} onChange={(e) => setPForm({ ...pForm, bio: e.target.value })} data-testid="profile-bio-input" />
              <button type="submit" disabled={savingProfile} className="btn-primary w-full flex items-center justify-center gap-2" data-testid="profile-save-btn"><Save size={16} /> {savingProfile ? "Saving..." : "Save Profile"}</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
