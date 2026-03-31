"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import type { TKey } from "@/lib/i18n";
import {
  apiCommunityList,
  apiCommunityUpload,
  apiCommunityRate,
  type CommunityPrint,
} from "@/lib/api";
import { Navbar } from "@/components/Navbar";

const STARS = [1, 2, 3, 4, 5];

function StarRating({
  value,
  onChange,
  readonly = false,
}: {
  value: number | null;
  onChange?: (s: number) => void;
  readonly?: boolean;
}) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-0.5">
      {STARS.map((s) => (
        <button
          key={s}
          type="button"
          disabled={readonly}
          onClick={() => onChange?.(s)}
          onMouseEnter={() => !readonly && setHover(s)}
          onMouseLeave={() => !readonly && setHover(0)}
          className={`text-lg leading-none transition-colors ${
            readonly ? "cursor-default" : "cursor-pointer"
          } ${
            s <= (hover || value || 0) ? "text-yellow-400" : "text-zinc-700"
          }`}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function PhotoDropzone({
  value,
  onChange,
  hint,
}: {
  value: File | null;
  onChange: (f: File) => void;
  hint: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const preview = value ? URL.createObjectURL(value) : null;

  return (
    <div
      className={`relative border-2 border-dashed rounded-lg transition-colors cursor-pointer overflow-hidden
        ${drag ? "border-brand bg-brand/5" : "border-surface-border hover:border-zinc-600"}`}
      onClick={() => ref.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files[0];
        if (f && f.type.startsWith("image/")) onChange(f);
      }}
    >
      <input
        ref={ref}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onChange(f); }}
      />
      {preview ? (
        <img src={preview} alt="preview" className="w-full h-48 object-cover" />
      ) : (
        <div className="h-48 flex flex-col items-center justify-center gap-2">
          <svg className="w-8 h-8 text-zinc-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span className="text-xs text-zinc-500">{hint}</span>
        </div>
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function CommunityPage() {
  const router = useRouter();
  const { t } = useLang();
  const [loggedIn, setLoggedIn] = useState(false);
  const [prints, setPrints] = useState<CommunityPrint[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [formTitle, setFormTitle] = useState("");
  const [formDesc, setFormDesc]   = useState("");
  const [formFilament, setFormFilament] = useState("");
  const [formPrinter, setFormPrinter]   = useState("");
  const [formFile, setFormFile]   = useState<File | null>(null);
  const [formPhoto, setFormPhoto] = useState<File | null>(null);
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
    apiCommunityList()
      .then(setPrints)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formFile)  { setFormError("Please select a .3mf file."); return; }
    if (!formPhoto) { setFormError("Please add a photo of your print."); return; }
    setFormError("");
    setSubmitting(true);
    try {
      await apiCommunityUpload(formTitle, formDesc, formFilament, formPrinter, formFile, formPhoto);
      setShowForm(false);
      setFormTitle(""); setFormDesc(""); setFormFilament(""); setFormPrinter("");
      setFormFile(null); setFormPhoto(null);
      const updated = await apiCommunityList();
      setPrints(updated);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRate(printId: number, stars: number) {
    if (!loggedIn) { router.push("/login"); return; }
    try {
      const res = await apiCommunityRate(printId, stars);
      setPrints((prev) =>
        prev.map((p) =>
          p.id === printId
            ? { ...p, avg_rating: res.avg_rating, rating_count: res.rating_count, user_rating: stars }
            : p,
        ),
      );
    } catch {}
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">{t("comm_title")}</h1>
            <p className="text-sm text-zinc-500 mt-0.5">{t("comm_subtitle")}</p>
          </div>
          {loggedIn ? (
            <button
              onClick={() => setShowForm((v) => !v)}
              className="flex items-center gap-2 px-4 py-2 bg-brand hover:bg-brand-dark text-white text-sm font-semibold rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              {showForm ? t("comm_close") : t("comm_share")}
            </button>
          ) : (
            <button
              onClick={() => router.push("/login")}
              className="px-4 py-2 border border-surface-border text-zinc-400 hover:text-white text-sm rounded-lg transition-colors"
            >
              {t("comm_login_to_share")}
            </button>
          )}
        </div>

        {/* Upload form */}
        {showForm && (
          <div className="mb-8 bg-surface-card border border-surface-border rounded-xl p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                    {t("comm_form_title")} *
                  </label>
                  <input
                    type="text"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    required
                    className="w-full"
                    placeholder="My awesome Benchy"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                    {t("comm_form_filament")}
                  </label>
                  <input
                    type="text"
                    value={formFilament}
                    onChange={(e) => setFormFilament(e.target.value)}
                    className="w-full"
                    placeholder="PLA"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                    {t("comm_form_printer")}
                  </label>
                  <input
                    type="text"
                    value={formPrinter}
                    onChange={(e) => setFormPrinter(e.target.value)}
                    className="w-full"
                    placeholder="Anycubic Kobra S1"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                    {t("comm_form_desc")}
                  </label>
                  <input
                    type="text"
                    value={formDesc}
                    onChange={(e) => setFormDesc(e.target.value)}
                    className="w-full"
                    placeholder="…"
                  />
                </div>
              </div>

              {/* Photo dropzone */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                  {t("comm_form_photo")} *
                </label>
                <PhotoDropzone
                  value={formPhoto}
                  onChange={setFormPhoto}
                  hint={t("comm_form_photo_hint")}
                />
              </div>

              {/* 3MF file */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                  {t("comm_form_file")} *
                </label>
                <div
                  className="border border-dashed border-surface-border rounded-lg p-4 flex items-center gap-3 cursor-pointer hover:border-zinc-600 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <svg className="w-5 h-5 text-zinc-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="text-sm text-zinc-400 truncate">
                    {formFile ? formFile.name : "No file selected"}
                  </span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".3mf"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) setFormFile(f); }}
                  />
                </div>
              </div>

              {formError && (
                <p className="text-brand text-sm">{formError}</p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-brand hover:bg-brand-dark disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors text-sm"
              >
                {submitting ? t("comm_form_submitting") : t("comm_form_submit")}
              </button>
            </form>
          </div>
        )}

        {/* Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <div className="w-6 h-6 border-2 border-brand border-t-transparent rounded-full animate-spin" />
          </div>
        ) : prints.length === 0 ? (
          <div className="text-center py-24 text-zinc-600 text-sm">{t("comm_empty")}</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {prints.map((p) => (
              <PrintCard
                key={p.id}
                print={p}
                loggedIn={loggedIn}
                onRate={handleRate}
                t={t}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function PrintCard({
  print: p,
  loggedIn,
  onRate,
  t,
}: {
  print: CommunityPrint;
  loggedIn: boolean;
  onRate: (id: number, stars: number) => void;
  t: (k: TKey) => string;
}) {
  const photoUrl = `/api/community/${p.id}/photo`;
  const downloadUrl = `/api/community/${p.id}/download`;

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden flex flex-col">
      {/* Photo */}
      <div className="relative h-48 bg-surface overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={photoUrl}
          alt={p.title}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      </div>

      <div className="p-4 flex flex-col gap-3 flex-1">
        {/* Title + meta */}
        <div>
          <h3 className="text-white font-semibold text-sm leading-tight line-clamp-2">{p.title}</h3>
          <p className="text-zinc-500 text-xs mt-0.5">
            {t("comm_by")} {p.username} · {timeAgo(p.created_at)}
          </p>
        </div>

        {/* Tags */}
        {(p.filament_type || p.printer_name) && (
          <div className="flex flex-wrap gap-1.5">
            {p.filament_type && (
              <span className="px-2 py-0.5 bg-surface text-zinc-400 text-xs rounded-md border border-surface-border">
                {p.filament_type}
              </span>
            )}
            {p.printer_name && (
              <span className="px-2 py-0.5 bg-surface text-zinc-400 text-xs rounded-md border border-surface-border">
                {p.printer_name}
              </span>
            )}
          </div>
        )}

        {p.description && (
          <p className="text-zinc-500 text-xs line-clamp-2">{p.description}</p>
        )}

        {/* Rating */}
        <div className="flex items-center gap-2">
          {loggedIn ? (
            <>
              <StarRating value={p.user_rating} onChange={(s) => onRate(p.id, s)} />
              <span className="text-xs text-zinc-600">
                {p.avg_rating ? `${p.avg_rating} (${p.rating_count})` : t("comm_no_rating")}
              </span>
            </>
          ) : (
            <span className="text-xs text-zinc-600">{t("comm_login_to_rate")}</span>
          )}
        </div>

        {/* Footer */}
        <div className="mt-auto flex items-center justify-between pt-2 border-t border-surface-border">
          <span className="text-xs text-zinc-600">
            {p.download_count} {t("comm_downloads")}
          </span>
          <a
            href={downloadUrl}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand/10 hover:bg-brand/20 text-brand text-xs font-medium rounded-lg transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {t("comm_download")}
          </a>
        </div>
      </div>
    </div>
  );
}
