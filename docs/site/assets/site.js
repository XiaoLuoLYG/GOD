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
      '      <span>Example replay</span><span>' + escapeHtml(item.mapPack) + '</span><span>' + escapeHtml(item.agentPack) + '</span>',
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
    var previewLabel = kind === "experiment" ? "View example replay" : "Preview";
    var downloadLabel = item.downloadLabel || (kind === "experiment" ? "Download ExperimentPack" : "Download");
    var showPreview = Boolean(previewHref);
    if (kind === "experiment" && !item.previewHref && !item.replayHref && !item.href) {
      showPreview = false;
    }
    var media = item.image
      ? '<a class="library-card__media library-card__media--' + escapeHtml(kind) + '" href="' + url(showPreview ? previewHref : item.download) + '"><img src="' + url(item.image) + '" alt="' + escapeHtml(item.title) + ' preview" loading="lazy"></a>'
      : '<div class="library-card__glyph" aria-hidden="true">' + productIcon(kind) + '</div>';
    var buttons = [];
    if (showPreview) {
      buttons.push('<a class="button button--small" href="' + url(previewHref) + '">' + escapeHtml(previewLabel) + '</a>');
    }
    if (item.download) {
      buttons.push('<a class="button button--small button--ghost" href="' + url(item.download) + '">' + escapeHtml(downloadLabel) + '</a>');
    }
    return [
      '<article class="library-card">',
      media,
      '  <div class="library-card__body">',
      '    <p class="mini-label">' + escapeHtml(kind === "map" ? "Map Pack" : kind === "agent" ? "Agent Pack" : "Experiment") + '</p>',
      '    <h3>' + escapeHtml(item.title) + '</h3>',
      '    <p>' + escapeHtml(item.summary) + '</p>',
      metricLine(item),
      '    <div class="button-row">',
      buttons.join(""),
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

  function experimentManifestToCard(item) {
    var packId = item.pack_id || item.slug;
    var download = "";
    (item.downloads || []).forEach(function (entry) {
      if (!download && entry.type === "experiment") {
        download = "public-data/experiments/" + packId + "/" + entry.href;
      }
    });
    var replayHref = item.replay_slug ? "replays/" + item.replay_slug + "/" : "";
    return {
      title: item.display_name || packId,
      slug: packId,
      summary: item.summary || "",
      image: item.image || "",
      replayHref: replayHref,
      download: download,
      downloadLabel: "Download ExperimentPack",
      stats: [
        item.map_pack ? item.map_pack + " map" : "",
        item.agent_count ? item.agent_count + " agents" : "",
        item.total_steps ? item.total_steps + " steps" : ""
      ].filter(Boolean)
    };
  }

  function renderExperimentLibrary() {
    var grid = document.querySelector("[data-experiment-pack-grid]");
    if (!grid) {
      return;
    }
    var fallback = function () {
      renderLibrary("[data-experiment-pack-grid]", catalog.experiments, "experiment");
    };
    if (!window.fetch) {
      fallback();
      return;
    }
    fetch(url("public-data/experiments/index.json"))
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (items) {
        if (!Array.isArray(items) || !items.length) {
          fallback();
          return;
        }
        renderLibrary("[data-experiment-pack-grid]", items.map(experimentManifestToCard), "experiment");
      })
      .catch(fallback);
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
  renderExperimentLibrary();
  markActiveNav();
})();
