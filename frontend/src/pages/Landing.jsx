import { Link } from "react-router-dom";
import { Logo, WaveBars } from "@/components/Brand";
import { Calendar, Mic2, Users, Zap, Shield, Sparkles, ArrowRight, MapPin, Mail, Guitar, Music } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const IMG = {
  hero: "https://images.unsplash.com/photo-1565035010268-a3816f98589a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2OTV8MHwxfHNlYXJjaHwxfHxsaXZlJTIwbXVzaWMlMjBjb25jZXJ0JTIwYmFuZCUyMGphbSUyMHNlc3Npb24lMjBzdGFnZXxlbnwwfHx8fDE3ODgxNjg0OTF8MA&ixlib=rb-4.1.0&q=85",
  jam: "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?w=1000",
  band: "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?w=1000",
  guitar: "https://images.unsplash.com/photo-1605340406960-f5b496c38b3d?w=1000",
  stage: "https://images.unsplash.com/photo-1600779547877-be592ef5aad3?w=1000",
  friends: "https://images.unsplash.com/photo-1661925501942-b0c9a9eab08e?w=1000",
};

function Header() {
  return (
    <header className="fixed top-0 inset-x-0 z-50 glass">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
        <Logo />
        <nav className="hidden md:flex items-center gap-8 text-sm text-slate-300">
          <a href="#about" className="hover:text-orange-400 transition-colors" data-testid="nav-about">Who We Are</a>
          <a href="#features" className="hover:text-orange-400 transition-colors" data-testid="nav-features">What We Do</a>
          <a href="#events" className="hover:text-orange-400 transition-colors" data-testid="nav-events">Events</a>
          <a href="#roadmap" className="hover:text-orange-400 transition-colors" data-testid="nav-roadmap">Roadmap</a>
          <a href="#contact" className="hover:text-orange-400 transition-colors" data-testid="nav-contact">Contact</a>
        </nav>
        <div className="flex items-center gap-3">
          <Link to="/login" className="btn-ghost text-sm" data-testid="header-login-btn">Admin Login</Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative min-h-screen bg-mesh flex items-center pt-28 pb-16 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-12 gap-10 items-center relative z-10">
        <div className="lg:col-span-7 reveal">
          <div className="inline-flex items-center gap-3 border border-orange-500/30 bg-orange-500/10 rounded-full px-4 py-1.5 mb-6">
            <WaveBars />
            <span className="text-xs uppercase tracking-widest text-orange-300 font-mono">Live · Now Recruiting</span>
          </div>
          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-black leading-[0.95] mb-6">
            Your Stage.<br />
            Your Voice.<br />
            <span className="gradient-text">Unlimited Possibilities.</span>
          </h1>
          <p className="text-lg text-slate-300 max-w-xl mb-8 leading-relaxed">
            A vibrant home for passion, expression, and pure acoustic energy. Built to empower every musician, vocalist, and enthusiast — across every genre.
          </p>
          <div className="flex flex-wrap gap-4">
            <a href="#contact" className="btn-primary flex items-center gap-2" data-testid="hero-join-btn">
              Get Involved <ArrowRight size={18} />
            </a>
            <a href="#about" className="btn-ghost" data-testid="hero-learn-btn">Learn More</a>
          </div>
          <div className="mt-12 grid grid-cols-3 gap-6 max-w-lg">
            {[
              { k: "0", v: "Barriers to Entry" },
              { k: "10", v: "Week Roadmap" },
              { k: "∞", v: "Genres Welcome" },
            ].map((s) => (
              <div key={s.v}>
                <div className="font-display text-3xl font-black gradient-text">{s.k}</div>
                <div className="text-xs uppercase tracking-wider text-slate-400 mt-1">{s.v}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="lg:col-span-5 relative reveal">
          <div className="gradient-border p-1">
            <img src={IMG.hero} alt="Live music" className="rounded-2xl w-full h-[520px] object-cover" />
          </div>
          <div className="absolute -bottom-6 -left-6 card p-4 flex items-center gap-3 w-64 glass">
            <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center">
              <Guitar className="text-orange-400" size={18} />
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-400">Jam Room #2</div>
              <div className="text-sm font-semibold">Live in session</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function About() {
  return (
    <section id="about" className="py-24 px-6">
      <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-10">
        <div className="lg:col-span-5">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-4">// Who We Are</div>
          <h2 className="font-display text-4xl lg:text-5xl font-black mb-6 leading-tight">
            A welcoming collective, built for every voice.
          </h2>
          <p className="text-slate-300 text-lg leading-relaxed">
            From beginners taking first steps to seasoned performers — this is a home for every musician, vocalist, and music enthusiast on campus.
          </p>
        </div>
        <div className="lg:col-span-7 grid sm:grid-cols-2 gap-4">
          {[
            { Icon: Sparkles, t: "Self-Expression First", d: "Music is the ultimate language of individuality. Play, sing, produce, or write — this club is your canvas." },
            { Icon: Shield, t: "Zero Hierarchy Policy", d: "No titles, no gatekeeping. Every member shapes the club's culture equally." },
            { Icon: Zap, t: "A Stage Without Boundaries", d: "From classical acoustic to electronic soundscapes — every style belongs." },
            { Icon: Users, t: "All Skill Levels Welcome", d: "Instrument collectors, curious listeners, and pros — the door is open." },
          ].map(({ Icon, t, d }, i) => (
            <div key={i} className="card p-6" data-testid={`philosophy-card-${i}`}>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500/20 to-violet-500/20 flex items-center justify-center mb-4">
                <Icon size={18} className="text-orange-400" />
              </div>
              <div className="font-display text-xl font-bold mb-2">{t}</div>
              <div className="text-sm text-slate-400 leading-relaxed">{d}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  const items = [
    { Icon: Music, badge: "Weekly", t: "Jam Sessions", d: "Weekly unstructured jam sessions where members collaborate, improvise, and create original sounds in Jam Room #2.", img: IMG.jam },
    { Icon: Mic2, badge: "Bi-Weekly", t: "Skill Workshops", d: "Vocal coaching, instrument techniques, DAW audio production, and live stage presence — hands-on and unfiltered.", img: IMG.guitar },
    { Icon: Zap, badge: "Monthly", t: "Live Showcases", d: "Campus open mics, acoustic spotlight nights, and an annual high-energy festival concert.", img: IMG.band },
  ];
  return (
    <section id="features" className="py-24 px-6 border-t border-white/5">
      <div className="max-w-7xl mx-auto">
        <div className="mb-14 max-w-2xl">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-4">// What We Do</div>
          <h2 className="font-display text-4xl lg:text-5xl font-black leading-tight">Three things we do — <span className="gradient-text">obsessively well.</span></h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {items.map((it, i) => (
            <div key={it.t} className="card overflow-hidden group" data-testid={`feature-${i}`}>
              <div className="h-48 overflow-hidden">
                <img src={it.img} alt={it.t} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
              </div>
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-lg bg-orange-500/15 flex items-center justify-center">
                    <it.Icon size={18} className="text-orange-400" />
                  </div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-violet-300 border border-violet-500/30 rounded-full px-2 py-0.5">{it.badge}</span>
                </div>
                <div className="font-display text-2xl font-bold mb-2">{it.t}</div>
                <div className="text-sm text-slate-400 leading-relaxed">{it.d}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function UpcomingEvents() {
  const [events, setEvents] = useState([]);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    api.get("/public/events").then((r) => setEvents(r.data.events || [])).catch(() => {});
    api.get("/public/sessions").then((r) => setSessions(r.data.sessions || [])).catch(() => {});
  }, []);

  return (
    <section id="events" className="py-24 px-6 border-t border-white/5">
      <div className="max-w-7xl mx-auto">
        <div className="mb-14 max-w-2xl">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-4">// Upcoming</div>
          <h2 className="font-display text-4xl lg:text-5xl font-black leading-tight">Events & <span className="gradient-text">Sessions</span></h2>
          <p className="text-slate-400 mt-4">Curated by Chanakya & Siddharth. Published live from Command Center.</p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <Calendar className="text-orange-400" size={18} />
              <span className="font-display text-xl font-bold">Events</span>
            </div>
            <div className="space-y-3" data-testid="public-events-list">
              {events.length === 0 && <div className="text-sm text-slate-500 italic">No events published yet — check back soon.</div>}
              {events.map((e) => (
                <div key={e.id} className="card p-5 flex gap-4">
                  {e.image_url && <img src={e.image_url} alt={e.title} className="w-24 h-24 object-cover rounded-lg" />}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono uppercase tracking-widest text-orange-300 border border-orange-500/30 rounded-full px-2 py-0.5">{e.event_type}</span>
                      <span className="text-xs text-slate-500 font-mono">{new Date(e.date).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</span>
                    </div>
                    <div className="font-display text-lg font-bold">{e.title}</div>
                    <div className="text-xs text-slate-400 mt-1 line-clamp-2">{e.description}</div>
                    <div className="text-[11px] text-slate-500 mt-2 flex items-center gap-1"><MapPin size={11} /> {e.location}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-3 mb-4">
              <Mic2 className="text-violet-400" size={18} />
              <span className="font-display text-xl font-bold">Sessions</span>
            </div>
            <div className="space-y-3" data-testid="public-sessions-list">
              {sessions.length === 0 && <div className="text-sm text-slate-500 italic">No sessions scheduled yet.</div>}
              {sessions.map((s) => (
                <div key={s.id} className="card p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono uppercase tracking-widest text-violet-300 border border-violet-500/30 rounded-full px-2 py-0.5">Week {s.week} · {s.session_type}</span>
                    <span className="text-xs text-slate-500 font-mono">{new Date(s.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                  </div>
                  <div className="font-display text-lg font-bold">{s.title}</div>
                  <div className="text-xs text-slate-400 mt-1">Led by {s.facilitator} · {s.duration_minutes} min</div>
                  {s.notes && <div className="text-xs text-slate-500 mt-2 italic">"{s.notes}"</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Roadmap() {
  const items = [
    { week: "Week 1", t: "Meetup", d: "Orientation night, acoustic icebreakers, team introductions." },
    { week: "Week 3", t: "Jams", d: "First open jam sessions and genre crossover groups." },
    { week: "Week 6", t: "Open Mic", d: "First live performance showcase for all new members." },
    { week: "Week 10", t: "Concert", d: "Annual grand campus music festival and showcase." },
  ];
  return (
    <section id="roadmap" className="py-24 px-6 border-t border-white/5">
      <div className="max-w-7xl mx-auto">
        <div className="mb-14 max-w-2xl">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-4">// Semester Roadmap</div>
          <h2 className="font-display text-4xl lg:text-5xl font-black leading-tight">Ten weeks. <span className="gradient-text">One resonance.</span></h2>
        </div>
        <div className="relative">
          <div className="absolute left-4 md:left-1/2 -translate-x-0 md:-translate-x-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-orange-500 via-red-500 to-violet-500" />
          <div className="space-y-10">
            {items.map((it, i) => (
              <div key={it.t} className={`grid md:grid-cols-2 gap-6 items-start`}>
                <div className={`${i % 2 === 0 ? "md:text-right md:pr-12" : "md:col-start-2 md:pl-12"}`}>
                  <div className="pl-12 md:pl-0">
                    <div className="text-xs font-mono uppercase tracking-widest text-orange-400">{it.week}</div>
                    <div className="font-display text-2xl font-black mt-1">{it.t}</div>
                    <div className="text-sm text-slate-400 mt-2 max-w-md">{it.d}</div>
                  </div>
                </div>
                <div className="hidden md:block" />
                <div className="absolute left-4 md:left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-orange-400 shadow-[0_0_20px_rgba(249,115,22,0.7)]" style={{ top: `${i * 120 + 6}px` }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Leadership() {
  return (
    <section id="leadership" className="py-24 px-6 border-t border-white/5">
      <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-10">
        <div className="lg:col-span-4">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-4">// Leadership</div>
          <h2 className="font-display text-4xl font-black leading-tight">Driven by collaboration — <span className="gradient-text">facilitated without hierarchy.</span></h2>
          <p className="text-slate-400 mt-4">Two co-directors. Zero seniority barriers.</p>
        </div>
        <div className="lg:col-span-8 grid sm:grid-cols-2 gap-4">
          {[
            { name: "Chanakya", role: "Creative Direction & Events", d: "Focuses on creative direction, event coordination, and strategic planning to make jams and live concerts seamless." },
            { name: "Siddharth", role: "Community & Gear Ops", d: "Facilitates member ideas, equipment ops in Jam Room #2, and keeps the environment supportive & open." },
          ].map((l) => (
            <div key={l.name} className="card p-6" data-testid={`leader-${l.name.toLowerCase()}`}>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-orange-500 to-violet-500 flex items-center justify-center font-display font-black text-lg">{l.name[0]}</div>
                <div>
                  <div className="font-display text-xl font-bold">{l.name}</div>
                  <div className="text-[11px] uppercase tracking-widest text-orange-300 font-mono">{l.role}</div>
                </div>
              </div>
              <div className="text-sm text-slate-400 leading-relaxed">{l.d}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Contact() {
  return (
    <section id="contact" className="py-24 px-6 border-t border-white/5">
      <div className="max-w-4xl mx-auto text-center">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-4">// Join The Resonance</div>
        <h2 className="font-display text-4xl lg:text-6xl font-black leading-tight mb-6">Your stage <span className="gradient-text">awaits.</span></h2>
        <p className="text-slate-300 text-lg mb-10 max-w-xl mx-auto">Bring your passion, your instruments, or simply your love for music.</p>
        <div className="flex flex-wrap justify-center gap-4 mb-14">
          <a href="https://docs.google.com/forms/d/e/1FAIpQLScsO9gD-O4nGW4aXOM4NsRoOHQibhJJvplMzmFCs4XHkZBTVQ/viewform?usp=dialog" target="_blank" rel="noreferrer" className="btn-primary flex items-center gap-2" data-testid="contact-form-btn">
            Get In Touch <ArrowRight size={16} />
          </a>
          <Link to="/login" className="btn-ghost" data-testid="contact-login-btn">Admin Login</Link>
        </div>
        <div className="grid sm:grid-cols-3 gap-4 text-left">
          {[
            { Icon: Users, t: "Managed by", v: "Chanakya & Siddharth" },
            { Icon: MapPin, t: "Location", v: "Jam Room #2" },
            { Icon: Mail, t: "Email", v: "sidchan901@gmail.com" },
          ].map((c) => (
            <div key={c.t} className="card p-5 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-orange-500/15 flex items-center justify-center">
                <c.Icon size={18} className="text-orange-400" />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{c.t}</div>
                <div className="text-sm font-semibold">{c.v}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/5 py-10 px-6">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
        <Logo small />
        <div className="text-xs text-slate-500 font-mono">© {new Date().getFullYear()} The Music Club — Express Yourself.</div>
      </div>
    </footer>
  );
}

export default function Landing() {
  return (
    <div className="grain min-h-screen">
      <Header />
      <Hero />
      <About />
      <Features />
      <UpcomingEvents />
      <Roadmap />
      <Leadership />
      <Contact />
      <Footer />
    </div>
  );
}
