export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-surface py-5 px-6">
      <p className="text-center text-xs text-zinc-600">
        © {new Date().getFullYear()} AutoSlice —{" "}
        Designed by{" "}
        <span className="text-zinc-500">Quiandro Segier</span>
        {" "}in cooperation with{" "}
        <span className="text-zinc-500">Yoni Smets</span>
      </p>
    </footer>
  );
}
