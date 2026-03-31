export function Footer() {
  return (
    <footer className="border-t border-surface-border/50 bg-surface py-4 px-6">
      <div className="flex items-center justify-center gap-1.5 flex-wrap">
        <span className="text-[11px] text-zinc-700">
          © {new Date().getFullYear()} AutoSlice
        </span>
        <span className="text-zinc-800">·</span>
        <span className="text-[11px] text-zinc-700">
          Designed by{" "}
          <span className="text-zinc-600">Quiandro Segier</span>
          {" & "}
          <span className="text-zinc-600">Yoni Smets</span>
        </span>
      </div>
    </footer>
  );
}
