#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";

const DEFAULT_BASE = "docs/site";

function usage() {
  console.log(
    [
      "Usage: node scripts/validate-public-site.mjs [docs/site|https://example.github.io/GOD/]",
      "",
      "Validates GOD public-site package preview pages and their key assets."
    ].join("\n")
  );
}

function isRemoteBase(base) {
  return /^https?:\/\//i.test(base);
}

function joinUrl(base, target) {
  return new URL(target, base.endsWith("/") ? base : base + "/").toString();
}

async function readText(base, target) {
  if (isRemoteBase(base)) {
    const response = await fetch(joinUrl(base, target), { redirect: "follow" });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return response.text();
  }
  return fs.readFile(path.join(base, target), "utf8");
}

async function checkExists(base, target) {
  if (!target || target === "#") return false;
  if (/^https?:\/\//i.test(target)) {
    const response = await fetch(target, { method: "HEAD", redirect: "follow" });
    return response.ok;
  }
  if (isRemoteBase(base)) {
    const response = await fetch(joinUrl(base, target), { method: "HEAD", redirect: "follow" });
    return response.ok;
  }
  try {
    await fs.access(path.join(base, target));
    return true;
  } catch {
    return false;
  }
}

function parseCatalog(source) {
  const sandbox = { window: {} };
  vm.runInNewContext(source, sandbox, { filename: "catalog.js" });
  if (!sandbox.window.GOD_CATALOG) {
    throw new Error("catalog.js did not define window.GOD_CATALOG");
  }
  return sandbox.window.GOD_CATALOG;
}

function assertContains(errors, html, needle, label, page) {
  if (!html.includes(needle)) {
    errors.push(`${page}: missing ${label}`);
  }
}

function assetPathFromManifest(slug, manifest) {
  if (!manifest || !manifest.preview_url) return "";
  return `public-data/map-packs/${slug}/${manifest.preview_url}`;
}

async function validateMapPack(base, entry) {
  const errors = [];
  const slug = entry.slug;
  const page = `map-packs/${slug}/index.html`;
  const html = await readText(base, page).catch((error) => {
    errors.push(`${page}: ${error.message}`);
    return "";
  });

  if (html) {
    assertContains(errors, html, `data-map-pack="${slug}"`, "data-map-pack marker", page);
    assertContains(errors, html, 'class="page-hero"', "page hero", page);
    assertContains(errors, html, "data-map-image", "map preview image", page);
    assertContains(errors, html, "data-map-stats", "map stats target", page);
    assertContains(errors, html, "data-map-locations", "map locations target", page);
    assertContains(errors, html, "map-pack-viewer.js", "map viewer script", page);
    assertContains(errors, html, "nav-links", "navigation links", page);
  }

  const manifestPath = `public-data/map-packs/${slug}/map_pack.json`;
  const manifest = await readText(base, manifestPath)
    .then(JSON.parse)
    .catch((error) => {
      errors.push(`${manifestPath}: ${error.message}`);
      return null;
    });

  const preview = entry.image || assetPathFromManifest(slug, manifest);
  if (preview && !(await checkExists(base, preview))) {
    errors.push(`${page}: missing preview asset ${preview}`);
  }

  return errors;
}

async function validateAgentPack(base, entry) {
  const errors = [];
  const slug = entry.slug;
  const page = `agent-packs/${slug}/index.html`;
  const html = await readText(base, page).catch((error) => {
    errors.push(`${page}: ${error.message}`);
    return "";
  });

  if (html) {
    assertContains(errors, html, `data-agent-pack="${slug}"`, "data-agent-pack marker", page);
    assertContains(errors, html, 'class="page-hero"', "page hero", page);
    assertContains(errors, html, "data-agent-stats", "agent stats target", page);
    assertContains(errors, html, "data-agent-grid", "agent grid target", page);
    assertContains(errors, html, "agent-pack-viewer.js", "agent viewer script", page);
    assertContains(errors, html, "nav-links", "navigation links", page);
  }

  const manifestPath = `public-data/agent-packs/${slug}/agent_pack.json`;
  const manifest = await readText(base, manifestPath)
    .then(JSON.parse)
    .catch((error) => {
      errors.push(`${manifestPath}: ${error.message}`);
      return null;
    });

  const firstSprite = manifest?.agents?.find((agent) => agent.sprite?.path)?.sprite?.path;
  if (firstSprite) {
    const spritePath = `public-data/agent-packs/${slug}/${firstSprite}`;
    if (!(await checkExists(base, spritePath))) {
      errors.push(`${page}: missing sprite asset ${spritePath}`);
    }
  }

  return errors;
}

async function validateReplay(base, entry) {
  const errors = [];
  const slug = entry.slug;
  const page = `replays/${slug}/index.html`;
  const html = await readText(base, page).catch((error) => {
    errors.push(`${page}: ${error.message}`);
    return "";
  });

  if (html) {
    assertContains(errors, html, `data-replay-slug="${slug}"`, "data-replay-slug marker", page);
    assertContains(errors, html, "data-step-range", "timeline range", page);
    assertContains(
      errors,
      html,
      "Local setup gives the best experience. Online replays are static previews with limited live-control features.",
      "local-experience note",
      page
    );
  }

  const timelinePath = `public-data/replays/${slug}/timeline.json`;
  const timeline = await readText(base, timelinePath)
    .then(JSON.parse)
    .catch((error) => {
      errors.push(`${timelinePath}: ${error.message}`);
      return [];
    });

  if (!Array.isArray(timeline) || timeline.length === 0) {
    errors.push(`${timelinePath}: expected at least one timeline frame`);
    return errors;
  }

  const firstFrame = timeline[0]?.frame_url;
  if (firstFrame && !(await checkExists(base, `public-data/replays/${slug}/${firstFrame}`))) {
    errors.push(`${timelinePath}: missing first frame ${firstFrame}`);
  }

  return errors;
}

async function main() {
  const arg = process.argv[2] || DEFAULT_BASE;
  if (arg === "-h" || arg === "--help") {
    usage();
    return;
  }

  const base = arg;
  const catalog = parseCatalog(await readText(base, "data/catalog.js"));
  const allErrors = [];

  for (const entry of catalog.mapPacks || []) {
    allErrors.push(...(await validateMapPack(base, entry)));
  }
  for (const entry of catalog.agentPacks || []) {
    allErrors.push(...(await validateAgentPack(base, entry)));
  }
  for (const entry of catalog.replays || []) {
    allErrors.push(...(await validateReplay(base, entry)));
  }

  if (allErrors.length) {
    console.error(`Public site validation failed for ${base}`);
    for (const error of allErrors) {
      console.error(`- ${error}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log(`Public site validation passed for ${base}`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
