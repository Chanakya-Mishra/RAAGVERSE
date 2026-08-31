import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Logo, WaveBars } from "@/components/Brand";
import { Link } from "react-router-dom";
import { ArrowLeft, X } from "lucide-react";

const TAGS = ["All", "Jams", "Concerts", "Workshops", "Open Mic"];

function resolveUrl(image_url) {
  if (!image_url) return "";
  return image_url.startsWith("/api") ? `${process.env.REACT_APP_BACKEND_URL}${image_url}` : image_url;
}

export default function PublicGallery() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("All");
  const [lightbox, setLightbox] = useState(null);

  useEffect(() => {
    api.get("/public/gallery").then((r) => setItems(r.data.gallery || [])).catch(() => {});
  }, []);

  const filtered = useMemo(() => (filter === "All" ? items : items.filter((i) => i.tag === filter)), [filter, items]);

  return (
    <div className="min-h-screen bg-mesh grain">
      <header className="glass sticky top-0 z-40 border-b border-white/5">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <Logo />
          <Link to="/" className="btn-ghost text-sm flex items-center gap-1" data-testid="gallery-back-home"><ArrowLeft size={14} /> Home</Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-orange-400 mb-2 flex items-center gap-2"><WaveBars /> Live Vault</div>
        <h1 className="font-display text-5xl font-black mb-3">The <span className="gradient-text">Gallery</span></h1>
        <p className="text-slate-400 mb-10 max-w-2xl">Frames from jams, workshops, open mics, and campus concerts. Every photo captured live at Jam Room #2 and beyond.</p>

        <div className="flex flex-wrap gap-2 mb-8" data-testid="gallery-filters">
          {TAGS.map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`text-xs font-mono uppercase tracking-widest px-4 py-1.5 rounded-full transition-all ${
                filter === t ? "bg-gradient-to-r from-orange-500 to-red-500 text-white" : "border border-white/10 text-slate-300 hover:border-orange-500/40"
              }`}
              data-testid={`filter-${t.toLowerCase().replace(" ", "-")}`}
            >
              {t}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4" data-testid="gallery-grid">
          {filtered.map((it, i) => (
            <button
              key={it.id}
              onClick={() => setLightbox(it)}
              className="group relative overflow-hidden rounded-xl card p-0 aspect-square"
              style={{ gridRow: i % 5 === 0 ? "span 2" : undefined }}
              data-testid={`gallery-item-${it.id}`}
            >
              <img src={resolveUrl(it.image_url)} alt={it.caption} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-3 text-left">
                <div className="text-[10px] font-mono uppercase tracking-widest text-orange-300">{it.tag}</div>
                <div className="text-sm font-semibold text-white line-clamp-2">{it.caption}</div>
              </div>
            </button>
          ))}
          {filtered.length === 0 && <div className="col-span-full text-center py-16 text-slate-500 italic">No photos in this category yet.</div>}
        </div>
      </main>

      {lightbox && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-6" onClick={() => setLightbox(null)}>
          <button className="absolute top-6 right-6 text-white hover:text-orange-400" onClick={() => setLightbox(null)} data-testid="lightbox-close"><X size={24} /></button>
          <div className="max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
            <img src={resolveUrl(lightbox.image_url)} alt={lightbox.caption} className="w-full h-auto max-h-[80vh] object-contain rounded-xl" />
            <div className="mt-4 text-center">
              <div className="text-[10px] font-mono uppercase tracking-widest text-orange-300">{lightbox.tag}</div>
              <div className="font-display text-xl font-bold text-white mt-1">{lightbox.caption}</div>
              {lightbox.photographer && <div className="text-sm text-slate-400 mt-1">Shot by {lightbox.photographer}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
