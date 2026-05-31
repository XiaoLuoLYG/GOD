(function () {
  var catalog = window.GOD_CATALOG || {};
  var root = document.body.dataset.siteRoot || "";

  function url(path) {
    if (!path) {
      return "#";
    }
    if (/^https?:\/\//.test(path)) {
      return path;
    }
    return root + path;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function productIcon(key) {
    var icons = {
      replay: "▶",
      map: "⌖",
      agent: "◉",
      experiment: "□"
    };
    return icons[key] || "·";
  }

  function metricLine(item) {
    if (!item.stats || !item.stats.length) {
      return "";
    }
    return '<div class="stat-row">' + item.stats.map(function (stat) {
      return "<span>" + escapeHtml(stat) + "</span>";
    }).join("") + "</div>";
  }

  function renderProducts() {
    var grid = document.querySelector("[data-product-grid]");
    if (!grid || !catalog.products) {
      return;
    }
    grid.innerHTML = catalog.products.map(function (item) {
      return [
        '<a class="product-card product-card--' + escapeHtml(item.key) + '" href="' + url(item.href) + '">',
        '  <span class="product-card__icon" aria-hidden="true">' + productIcon(item.key) + '</span>',
        '  <span class="product-card__label">' + escapeHtml(item.label) + '</span>',
        '  <strong>' + escapeHtml(item.title) + '</strong>',
        '  <span>' + escapeHtml(item.summary) + '</span>',
        '</a>'
      ].join("");
    }).join("");
  }

  function replayCard(item) {
    return [
      '<article class="feature-card">',
      '  <a class="feature-card__media" href="' + url(item.href) + '">',
      '    <img src="' + url(item.image) + '" alt="' + escapeHtml(item.title) + ' map preview" loading="lazy">',
      '  </a>',
      '  <div class="feature-card__body">',
      '    <p class="mini-label">' + escapeHtml(item.eyebrow || "Replay") + '</p>',
      '    <h3>' + escapeHtml(item.title) + '</h3>',
      '    <p>' + escapeHtml(item.summary) + '</p>',
      '    <div class="feature-card__meta" data-replay-stats="' + escapeHtml(item.slug) + '">',
      '      <span>Replay archive</span><span>' + escapeHtml(item.mapPack) + '</span><span>' + escapeHtml(item.agentPack) + '</span>',
      '    </div>',
      '    <div class="button-row">',
      '      <a class="button button--small" href="' + url(item.href) + '">Open replay</a>',
      '      <a class="button button--small button--ghost" href="' + url(item.manifest) + '">Manifest</a>',
      '    </div>',
      '  </div>',
      '</article>'
    ].join("");
  }

  function renderReplays() {
    var grid = document.querySelector("[data-replay-grid]");
    if (!grid || !catalog.replays) {
      return;
    }
    grid.innerHTML = catalog.replays.map(replayCard).join("");
    hydrateReplayStats();
  }

  function libraryCard(item, kind) {
    var previewHref = item.previewHref || item.replayHref || item.href || item.download;
    var media = item.image
      ? '<a class="library-card__media library-card__media--' + escapeHtml(kind) + '" href="' + url(previewHref) + '"><img src="' + url(item.image) + '" alt="' + escapeHtml(item.title) + ' preview" loading="lazy"></a>'
      : '<div class="library-card__glyph" aria-hidden="true">' + productIcon(kind) + '</div>';
    return [
      '<article class="library-card">',
      media,
      '  <div class="library-card__body">',
      '    <p class="mini-label">' + escapeHtml(kind === "map" ? "Map Pack" : kind === "agent" ? "Agent Pack" : "Experiment") + '</p>',
      '    <h3>' + escapeHtml(item.title) + '</h3>',
      '    <p>' + escapeHtml(item.summary) + '</p>',
      metricLine(item),
      '    <div class="button-row">',
      '      <a class="button button--small" href="' + url(previewHref) + '">Preview</a>',
      '      <a class="button button--small button--ghost" href="' + url(item.download) + '">Download</a>',
      '    </div>',
      '  </div>',
      '</article>'
    ].join("");
  }

  function renderLibrary(selector, items, kind) {
    var grid = document.querySelector(selector);
    if (!grid || !items) {
      return;
    }
    grid.innerHTML = items.map(function (item) {
      return libraryCard(item, kind);
    }).join("");
  }

  function hydrateReplayStats() {
    if (!catalog.replays || !window.fetch) {
      return;
    }
    catalog.replays.forEach(function (item) {
      fetch(url(item.manifest))
        .then(function (response) {
          return response.ok ? response.json() : null;
        })
        .then(function (manifest) {
          if (!manifest) {
            return;
          }
          document.querySelectorAll('[data-replay-stats="' + item.slug + '"]').forEach(function (node) {
            node.innerHTML = [
              "<span>" + manifest.total_steps + " steps</span>",
              "<span>" + manifest.agent_count + " agents</span>",
              "<span>" + manifest.command_count + " operator records</span>"
            ].join("");
          });
        })
        .catch(function () {});
    });
  }

  function markActiveNav() {
    var path = window.location.pathname.replace(/\/index\.html$/, "/");
    document.querySelectorAll("[data-nav]").forEach(function (link) {
      var href = link.getAttribute("href") || "";
      var absolute = new URL(href, window.location.href).pathname.replace(/\/index\.html$/, "/");
      if (path === absolute) {
        link.setAttribute("aria-current", "page");
      }
    });
  }

  renderProducts();
  renderReplays();
  renderLibrary("[data-map-pack-grid]", catalog.mapPacks, "map");
  renderLibrary("[data-agent-pack-grid]", catalog.agentPacks, "agent");
  renderLibrary("[data-experiment-pack-grid]", catalog.experiments, "experiment");
  markActiveNav();
})();
