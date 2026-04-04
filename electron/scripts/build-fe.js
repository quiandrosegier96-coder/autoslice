#!/usr/bin/env node
/**
 * Rebuilds the Next.js frontend (standalone) and copies the output into
 * electron/resources/frontend/ so electron-builder packages the latest code.
 *
 * Usage (from the electron/ directory):
 *   node scripts/build-fe.js
 *   npm run build:fe
 */

"use strict";

const { execSync } = require("child_process");
const path = require("path");
const fs   = require("fs");

const electronDir = path.join(__dirname, "..");
const feDir       = path.join(electronDir, "..", "frontend");
const resDst      = path.join(electronDir, "resources", "frontend");

const standaloneSrc = path.join(feDir, ".next", "standalone");
const staticSrc     = path.join(feDir, ".next", "static");
const publicSrc     = path.join(feDir, "public");

// ── 1. Build Next.js ─────────────────────────────────────────────────────────
console.log("\n[1/2] Building Next.js frontend (standalone)…");
execSync("npm run build", { cwd: feDir, stdio: "inherit" });

if (!fs.existsSync(standaloneSrc)) {
  console.error(`\nERROR: standalone output not found at:\n  ${standaloneSrc}`);
  console.error("Make sure next.config has  output: 'standalone'");
  process.exit(1);
}

// ── 2. Copy to electron/resources/frontend ───────────────────────────────────
console.log("\n[2/2] Copying standalone output → electron/resources/frontend…");

if (fs.existsSync(resDst)) fs.rmSync(resDst, { recursive: true, force: true });
fs.cpSync(standaloneSrc, resDst, { recursive: true });

// .next/static — standalone does NOT bundle this; copy it manually
const staticDst = path.join(resDst, ".next", "static");
if (fs.existsSync(staticSrc)) {
  fs.cpSync(staticSrc, staticDst, { recursive: true });
}

// public/ — same story
const publicDst = path.join(resDst, "public");
if (fs.existsSync(publicSrc)) {
  fs.cpSync(publicSrc, publicDst, { recursive: true });
}

console.log("\n✓ electron/resources/frontend is up to date.\n");
