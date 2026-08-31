import { useEffect, useState } from "react";
import { NavLink, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Logo, WaveBars } from "@/components/Brand";
import { LayoutDashboard, Users, Calendar, Mic2, Image as ImageIcon, UserCog, LogOut, Plus, Trash2, Edit3, X, Check } from "lucide-react";
import { toast } from "sonner";

function Shell({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (user === null) return <div className="min-h-screen bg-mesh flex items-center justify-center text-slate-400">Loading...</div>;
  if (!user || user.role !== "admin") return <Navigate to="/login" replace />;

  const items = [
    { to: "/admin", end: true, Icon: LayoutDashboard, label: "Overview" },
    { to: "/admin/members", Icon: Users, label: "Members" },
    { to: "/admin/events", Icon: Calendar, label: "Events" },
    { to: "/admin/sessions", Icon: Mic2, label: "Sessions" },
    { to: "/admin/gallery", Icon: ImageIcon, label: "Gallery" },
    { to: "/admin/profile", Icon: UserCog, label: "Profile" },
  ];

  return (
    <div className="min-h-screen grain bg-mesh flex">
      <aside className="w-64 border-r border-white/5 bg-[#0B0C10]/80 backdrop-blur p-6 flex flex-col gap-6 sticky top-0 h-screen">
        <Logo />
        <nav className="flex flex-col gap-1 mt-2" data-testid="admin-sidebar">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              data-testid={`nav-${it.label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                  isActive ? "bg-gradient-to-r from-orange-500/20 to-violet-500/10 text-white border border-orange-500/30" : "text-slate-400 hover:text-white hover:bg-white/5"
                }`
              }
            >
              <it.Icon size={16} /> {it.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto">
          <div className="card p-3 flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-500 to-violet-500 flex items-center justify-center font-display font-black">
              {(user.name || "A")[0]}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate">{user.name}</div>
              <div className="text-[10px] uppercase tracking-widest text-orange-400 font-mono">Admin</div>
            </div>
          </div>
          <button onClick={async () => { await logout(); nav("/login"); }} className="btn-ghost w-full justify-center flex items-center gap-2 text-sm" data-testid="logout-btn">
            <LogOut size={14} /> Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-8 max-w-full overflow-x-hidden">{children}</main>
    </div>
  );
}

function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
      <div>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-2 flex items-center gap-2"><WaveBars /> Command Center</div>
        <h1 className="font-display text-4xl font-black">{title}</h1>
        {subtitle && <p className="text-slate-400 mt-2 text-sm max-w-2xl">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function StatCard({ label, value, Icon, color }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={18} />
        </div>
      </div>
      <div className="font-display text-4xl font-black">{value}</div>
      <div className="text-xs uppercase tracking-widest text-slate-400 mt-1">{label}</div>
    </div>
  );
}

export function Overview() {
  const [stats, setStats] = useState(null);
  useEffect(() => { api.get("/admin/stats").then((r) => setStats(r.data)).catch(() => {}); }, []);
  return (
    <Shell>
      <PageHeader title="Overview" subtitle="Snapshot of your club — members, events, sessions, and gallery all in one view." />
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="stats-grid">
        <StatCard label="Active Members" value={stats?.members ?? "—"} Icon={Users} color="bg-orange-500/15 text-orange-400" />
        <StatCard label="Events" value={stats?.events ?? "—"} Icon={Calendar} color="bg-violet-500/15 text-violet-400" />
        <StatCard label="Sessions" value={stats?.sessions ?? "—"} Icon={Mic2} color="bg-red-500/15 text-red-400" />
        <StatCard label="Gallery Items" value={stats?.gallery ?? "—"} Icon={ImageIcon} color="bg-emerald-500/15 text-emerald-400" />
      </div>
      <div className="mt-10 grid lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <div className="font-display text-xl font-bold mb-2">Manage the vibe.</div>
          <div className="text-sm text-slate-400 leading-relaxed">Use the sidebar to invite members, publish jams, and curate the live gallery. Every action here shows up on the public site instantly.</div>
        </div>
        <div className="card p-6">
          <div className="font-display text-xl font-bold mb-2">Zero hierarchy — full ops.</div>
          <div className="text-sm text-slate-400 leading-relaxed">Both Chanakya and Siddharth have equal privileges. Everything you do is logged, versioned, and reversible.</div>
        </div>
      </div>
    </Shell>
  );
}

// ---------- CRUD helpers ----------
function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div className="card p-6 w-full max-w-xl relative" onClick={(e) => e.stopPropagation()} data-testid="modal">
        <button className="absolute top-4 right-4 text-slate-400 hover:text-white" onClick={onClose} data-testid="modal-close-btn"><X size={18} /></button>
        <div className="font-display text-2xl font-bold mb-5">{title}</div>
        {children}
      </div>
    </div>
  );
}

function useList(path) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const key = path.replace("/", "");
  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(path);
      setItems(data[key] || data.members || []);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  return { items, loading, reload: load };
}

// ---------- Members ----------
export function Members() {
  const { items, reload } = useList("/members");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ email: "", name: "", password: "", instrument: "", bio: "", status: "active" });

  const openNew = () => { setEditing(null); setForm({ email: "", name: "", password: "", instrument: "", bio: "", status: "active" }); setOpen(true); };
  const openEdit = (m) => { setEditing(m); setForm({ email: m.email, name: m.name, password: "", instrument: m.instrument || "", bio: m.bio || "", status: m.status || "active" }); setOpen(true); };

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        const body = { name: form.name, instrument: form.instrument, bio: form.bio, status: form.status };
        if (form.password) body.password = form.password;
        await api.put(`/members/${editing.id}`, body);
        toast.success("Member updated");
      } else {
        await api.post("/members", form);
        toast.success("Member created");
      }
      setOpen(false); reload();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const remove = async (m) => {
    if (!confirm(`Delete ${m.name}?`)) return;
    try { await api.delete(`/members/${m.id}`); toast.success("Deleted"); reload(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <Shell>
      <PageHeader
        title="Members"
        subtitle="Create, edit, and manage member accounts. Only admins can add new members — no self-registration."
        action={<button className="btn-primary flex items-center gap-2" onClick={openNew} data-testid="add-member-btn"><Plus size={16} /> Add Member</button>}
      />
      <div className="card overflow-hidden" data-testid="members-table">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-widest text-slate-500 font-mono border-b border-white/5">
            <tr><th className="p-4">Name</th><th className="p-4">Email</th><th className="p-4">Role</th><th className="p-4">Instrument</th><th className="p-4">Status</th><th className="p-4"></th></tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.id} className="border-b border-white/5 hover:bg-white/[0.02]" data-testid={`member-row-${m.email}`}>
                <td className="p-4 font-semibold">{m.name}</td>
                <td className="p-4 text-slate-400">{m.email}</td>
                <td className="p-4"><span className={`text-[10px] uppercase tracking-widest font-mono px-2 py-0.5 rounded-full border ${m.role === "admin" ? "text-orange-300 border-orange-500/30 bg-orange-500/10" : "text-violet-300 border-violet-500/30 bg-violet-500/10"}`}>{m.role}</span></td>
                <td className="p-4 text-slate-400">{m.instrument || "—"}</td>
                <td className="p-4"><span className="text-[10px] uppercase tracking-widest font-mono">{m.status}</span></td>
                <td className="p-4 flex gap-2 justify-end">
                  <button onClick={() => openEdit(m)} className="text-slate-400 hover:text-orange-400" data-testid={`edit-member-${m.email}`}><Edit3 size={14} /></button>
                  {m.role !== "admin" && <button onClick={() => remove(m)} className="text-slate-400 hover:text-red-400" data-testid={`delete-member-${m.email}`}><Trash2 size={14} /></button>}
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-slate-500">No members yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Edit Member" : "Add Member"}>
        <form onSubmit={save} className="space-y-4" data-testid="member-form">
          <div className="grid sm:grid-cols-2 gap-3">
            <input className="input-field" placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="member-name-input" />
            <input className="input-field" placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} disabled={!!editing} required data-testid="member-email-input" />
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <input className="input-field" placeholder={editing ? "New password (leave blank to keep)" : "Password (min 6)"} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required={!editing} data-testid="member-password-input" />
            <input className="input-field" placeholder="Instrument (Guitar, Vocals...)" value={form.instrument} onChange={(e) => setForm({ ...form, instrument: e.target.value })} data-testid="member-instrument-input" />
          </div>
          <textarea className="input-field" rows={3} placeholder="Short bio (optional)" value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} data-testid="member-bio-input" />
          <select className="input-field" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} data-testid="member-status-select">
            <option value="active">Active</option><option value="pending">Pending</option><option value="inactive">Inactive</option>
          </select>
          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" data-testid="member-save-btn"><Check size={16} /> {editing ? "Save" : "Create"}</button>
        </form>
      </Modal>
    </Shell>
  );
}

// ---------- Reusable CRUD page ----------
function CrudPage({ resource, title, subtitle, columns, fields, defaults, testid }) {
  const { items, reload } = useList(`/${resource}`);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(defaults);

  const openNew = () => { setEditing(null); setForm(defaults); setOpen(true); };
  const openEdit = (it) => { setEditing(it); setForm({ ...defaults, ...it }); setOpen(true); };

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editing) await api.put(`/${resource}/${editing.id}`, form);
      else await api.post(`/${resource}`, form);
      toast.success(editing ? "Updated" : "Created");
      setOpen(false); reload();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const remove = async (it) => {
    if (!confirm("Delete this item?")) return;
    try { await api.delete(`/${resource}/${it.id}`); toast.success("Deleted"); reload(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <Shell>
      <PageHeader title={title} subtitle={subtitle}
        action={<button className="btn-primary flex items-center gap-2" onClick={openNew} data-testid={`add-${testid}-btn`}><Plus size={16} /> Add</button>} />
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid={`${testid}-list`}>
        {items.map((it) => (
          <div key={it.id} className="card p-5 flex flex-col" data-testid={`${testid}-card-${it.id}`}>
            {it.image_url && <img src={it.image_url} alt="" className="rounded-lg h-32 w-full object-cover mb-3" />}
            <div className="flex-1">
              {columns.map((c) => (
                <div key={c.key} className="mb-1">
                  {c.label && <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{c.label}</div>}
                  <div className={c.className || "text-sm"}>{c.render ? c.render(it) : it[c.key]}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <button onClick={() => openEdit(it)} className="text-slate-400 hover:text-orange-400" data-testid={`edit-${testid}-${it.id}`}><Edit3 size={14} /></button>
              <button onClick={() => remove(it)} className="text-slate-400 hover:text-red-400" data-testid={`delete-${testid}-${it.id}`}><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
        {items.length === 0 && <div className="text-slate-500 col-span-full text-center py-12">No items yet.</div>}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title={editing ? `Edit ${title}` : `New ${title}`}>
        <form onSubmit={save} className="space-y-3" data-testid={`${testid}-form`}>
          {fields.map((f) => {
            if (f.type === "textarea")
              return <textarea key={f.key} rows={3} className="input-field" placeholder={f.label} value={form[f.key] || ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} data-testid={`${testid}-${f.key}-input`} />;
            if (f.type === "select")
              return <select key={f.key} className="input-field" value={form[f.key] || ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} data-testid={`${testid}-${f.key}-select`}>
                {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>;
            if (f.type === "checkbox")
              return <label key={f.key} className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={!!form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.checked })} data-testid={`${testid}-${f.key}-checkbox`} /> {f.label}</label>;
            return <input key={f.key} type={f.type || "text"} className="input-field" placeholder={f.label} value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value })} required={f.required} data-testid={`${testid}-${f.key}-input`} />;
          })}
          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" data-testid={`${testid}-save-btn`}><Check size={16} /> Save</button>
        </form>
      </Modal>
    </Shell>
  );
}

export function Events() {
  const isoNow = new Date().toISOString().slice(0, 16);
  return (
    <CrudPage
      resource="events"
      title="Events"
      subtitle="Publish jams, workshops, open mics, and concerts. Published events appear on the public site."
      testid="event"
      defaults={{ title: "", description: "", event_type: "Jam", date: isoNow, location: "Jam Room #2", capacity: 40, image_url: "", published: true }}
      columns={[
        { key: "title", className: "font-display text-lg font-bold" },
        { key: "event_type", label: "Type" },
        { key: "date", label: "When", render: (i) => new Date(i.date).toLocaleString() },
        { key: "location", label: "Where" },
        { key: "published", label: "Status", render: (i) => (i.published ? "Published" : "Draft") },
      ]}
      fields={[
        { key: "title", label: "Title", required: true },
        { key: "description", label: "Description", type: "textarea" },
        { key: "event_type", label: "Type", type: "select", options: ["Jam", "Workshop", "Open Mic", "Concert"] },
        { key: "date", label: "Date & Time", type: "datetime-local", required: true },
        { key: "location", label: "Location" },
        { key: "capacity", label: "Capacity", type: "number" },
        { key: "image_url", label: "Image URL" },
        { key: "published", label: "Published", type: "checkbox" },
      ]}
    />
  );
}

export function Sessions() {
  const isoNow = new Date().toISOString().slice(0, 16);
  return (
    <CrudPage
      resource="sessions"
      title="Sessions"
      subtitle="Weekly jam sessions, workshops, rehearsals. Add facilitators and notes for members."
      testid="session"
      defaults={{ title: "", facilitator: "", session_type: "Jam Session", week: 1, date: isoNow, duration_minutes: 90, notes: "" }}
      columns={[
        { key: "title", className: "font-display text-lg font-bold" },
        { key: "session_type", label: "Type" },
        { key: "week", label: "Week" },
        { key: "facilitator", label: "Facilitator" },
        { key: "date", label: "When", render: (i) => new Date(i.date).toLocaleString() },
      ]}
      fields={[
        { key: "title", label: "Session Title", required: true },
        { key: "facilitator", label: "Facilitator", required: true },
        { key: "session_type", label: "Type", type: "select", options: ["Jam Session", "Vocal Workshop", "Instrument Workshop", "Production", "Rehearsal"] },
        { key: "week", label: "Week Number", type: "number" },
        { key: "date", label: "Date & Time", type: "datetime-local", required: true },
        { key: "duration_minutes", label: "Duration (min)", type: "number" },
        { key: "notes", label: "Notes", type: "textarea" },
      ]}
    />
  );
}

export function Gallery() {
  return (
    <CrudPage
      resource="gallery"
      title="Gallery"
      subtitle="Curate the visual story of the club — jams, concerts, workshops, open mics."
      testid="gallery"
      defaults={{ caption: "", image_url: "", tag: "Jams", photographer: "" }}
      columns={[
        { key: "caption", className: "font-display text-base font-bold" },
        { key: "tag", label: "Tag" },
        { key: "photographer", label: "By" },
      ]}
      fields={[
        { key: "image_url", label: "Image URL", required: true },
        { key: "caption", label: "Caption", required: true },
        { key: "tag", label: "Tag", type: "select", options: ["Jams", "Concerts", "Workshops", "Open Mic"] },
        { key: "photographer", label: "Photographer" },
      ]}
    />
  );
}

export function Profile() {
  const { user, refresh } = useAuth();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (newPw.length < 6) return toast.error("Password must be 6+ characters");
    if (newPw !== confirmPw) return toast.error("Passwords do not match");
    setLoading(true);
    try {
      await api.post("/auth/change-password", { old_password: oldPw, new_password: newPw });
      toast.success("Password changed");
      setOldPw(""); setNewPw(""); setConfirmPw("");
      refresh();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  return (
    <Shell>
      <PageHeader title="Profile" subtitle="Your admin identity and security controls." />
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-1">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-orange-500 to-violet-500 flex items-center justify-center font-display font-black text-2xl mb-4">
            {(user?.name || "A")[0]}
          </div>
          <div className="font-display text-2xl font-bold">{user?.name}</div>
          <div className="text-sm text-slate-400 mt-1">{user?.email}</div>
          <div className="mt-4 text-[10px] uppercase tracking-widest text-orange-300 font-mono border border-orange-500/30 rounded-full px-2 py-0.5 inline-block">{user?.role}</div>
        </div>
        <div className="card p-6 lg:col-span-2">
          <div className="font-display text-xl font-bold mb-4">Change Password</div>
          <form onSubmit={submit} className="space-y-4" data-testid="change-password-form">
            <input type="password" className="input-field" placeholder="Current password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} required data-testid="old-password-input" />
            <input type="password" className="input-field" placeholder="New password (min 6)" value={newPw} onChange={(e) => setNewPw(e.target.value)} required data-testid="new-password-input" />
            <input type="password" className="input-field" placeholder="Confirm new password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} required data-testid="confirm-password-input" />
            <button type="submit" disabled={loading} className="btn-primary" data-testid="change-password-submit">{loading ? "Saving..." : "Update Password"}</button>
          </form>
        </div>
      </div>
    </Shell>
  );
}
