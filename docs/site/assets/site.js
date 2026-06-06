(function () {
  var catalog = window.GOD_CATALOG || {};
  var root = document.body.dataset.siteRoot || "";
  var assetPrefix = document.body.dataset.assetPrefix || root;
  var detailBase = document.body.dataset.detailBase || "experiments/";
  var pageDefaultLocale = (document.documentElement.lang || "en").toLowerCase().indexOf("zh") === 0 ? "zh" : "en";
  var locale = resolveLocale();
  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";

  var STATIC_TEXT = {
    en: {
      "nav.replays": "Replays",
      "nav.maps": "Map Packs",
      "nav.agents": "Agent Packs",
      "nav.experiments": "Experiments",
      "nav.github": "GitHub",
      "experiments.metaTitle": "Experiments - GOD",
      "experiments.eyebrow": "Experiment library",
      "experiments.title": "Create your own world.",
      "experiments.summary": "Experiments are playable setup seeds: map, cast, scenario, steps, and operator notes. Example replays stay separate as watchable results before you run your own version locally.",
      "experiments.footer": "GOD Experiments",
      "experiments.footerReplays": "Replays",
      "mapPacks.metaTitle": "Map Packs - GOD",
      "mapPacks.eyebrow": "Map Pack library",
      "mapPacks.title": "Places agents can inhabit.",
      "mapPacks.summary": "Map packs publish the location graph, Tiled map, pixel assets, interactions, anchors, and sprites needed to run or replay a world.",
      "mapPacks.footer": "GOD Map Packs",
      "agentPacks.metaTitle": "Agent Packs - GOD",
      "agentPacks.eyebrow": "Agent Pack library",
      "agentPacks.title": "Casts with memory, routines, and motives.",
      "agentPacks.summary": "Agent packs expose reusable populations for maps and experiments: personas, daily rhythms, relationships, roles, needs, and replay-visible state.",
      "agentPacks.footer": "GOD Agent Packs",
      "replays.metaTitle": "Replays - GOD",
      "replays.eyebrow": "Example replay",
      "replays.title": "Open a finished world.",
      "replays.summary": "These replays are static example results: timeline frames, map assets, agent profiles, and the recorded operator flow. Use ExperimentPacks when you want a playable setup.",
      "replays.footer": "GOD Replays",
      "replays.home": "Home",
      "replays.developerDocs": "Developer docs",
      "replay.example": "Example replay",
      "replay.open": "Open replay",
      "replay.manifest": "Manifest",
      "replay.operatorRecords": "operator records",
      "home.metaTitle": "GOD - Govern, Observe, Direct",
      "home.badge": "Govern - Observe - Direct",
      "home.subtitle": "Make your agents dance in a virtual Eden.",
      "home.line": "Create your own world.",
      "home.primaryCta": "Create your own world",
      "home.githubCta": "View on GitHub",
      "home.scrollCue": "Scroll down to enter the world",
      "home.productsEyebrow": "Public product surfaces",
      "home.productsTitle": "Four public hubs.",
      "home.productsSummary": "ExperimentPacks are playable setup seeds. Example replays are watchable results. MapPacks and AgentPacks remain reusable dependencies.",
      "home.replaysEyebrow": "Featured replays",
      "home.replaysTitle": "Open a world that already happened.",
      "home.replaysSummary": "Timeline, map assets, agent profiles, and operator traces are browser-readable; download the ExperimentPack when you want to play from the same setup.",
      "home.footer": "GOD - Govern, Observe, Direct",
      "home.contact": "Contact:",
      "common.github": "GitHub",
      "common.library": "Library",
      "common.mapPack": "Map Pack",
      "common.agentPack": "Agent Pack",
      "common.locations": "Locations",
      "common.downloadMapPack": "Download Map Pack",
      "common.downloadAgentPack": "Download Agent Pack",
      "common.tiles": "tiles",
      "common.locationsCount": "locations",
      "common.interactions": "interactions",
      "common.agents": "agents",
      "common.profiles": "profiles",
      "common.sprites": "sprites"
    },
    zh: {
      "nav.replays": "回放",
      "nav.maps": "地图包",
      "nav.agents": "角色包",
      "nav.experiments": "实验",
      "nav.github": "GitHub",
      "experiments.metaTitle": "实验 - GOD",
      "experiments.eyebrow": "实验库",
      "experiments.title": "创建你自己的世界。",
      "experiments.summary": "实验是可运行的 setup seed：地图、角色、场景、步骤和操作说明。示例回放作为可观看结果单独发布，方便你本地运行自己的版本。",
      "experiments.footer": "GOD 实验",
      "experiments.footerReplays": "回放",
      "mapPacks.metaTitle": "地图包 - GOD",
      "mapPacks.eyebrow": "地图包库",
      "mapPacks.title": "Agent 可以居住和行动的地方。",
      "mapPacks.summary": "地图包发布运行或回放一个世界所需的地点图、Tiled 地图、像素资产、交互、锚点和角色 sprites。",
      "mapPacks.footer": "GOD 地图包",
      "agentPacks.metaTitle": "角色包 - GOD",
      "agentPacks.eyebrow": "角色包库",
      "agentPacks.title": "带记忆、日程和动机的角色群。",
      "agentPacks.summary": "角色包提供可复用的人群：persona、日常节奏、关系、角色、需求以及回放可见状态。",
      "agentPacks.footer": "GOD 角色包",
      "replays.metaTitle": "回放 - GOD",
      "replays.eyebrow": "示例回放",
      "replays.title": "打开一个已经发生过的世界。",
      "replays.summary": "这些回放是静态示例结果：时间线帧、地图资产、角色档案和已记录的操作流程。想自己运行同一套设定时，请下载 ExperimentPack。",
      "replays.footer": "GOD 回放",
      "replays.home": "首页",
      "replays.developerDocs": "开发者文档",
      "replay.example": "示例回放",
      "replay.open": "打开回放",
      "replay.manifest": "清单",
      "replay.operatorRecords": "条操作记录",
      "home.metaTitle": "GOD - 治理、观察、引导",
      "home.badge": "Govern - Observe - Direct",
      "home.subtitle": "让你的 agents 在虚拟伊甸中起舞。",
      "home.line": "创建你自己的世界。",
      "home.primaryCta": "创建你自己的世界",
      "home.githubCta": "在 GitHub 查看",
      "home.scrollCue": "向下滚动进入世界",
      "home.productsEyebrow": "公开产品入口",
      "home.productsTitle": "四个公开枢纽。",
      "home.productsSummary": "ExperimentPack 是可运行的 setup seed。示例回放是可观看结果。MapPack 和 AgentPack 则是可复用依赖。",
      "home.replaysEyebrow": "精选回放",
      "home.replaysTitle": "打开一个已经发生过的世界。",
      "home.replaysSummary": "时间线、地图资产、角色档案和操作者记录都可在浏览器中读取；想从同一套设定开始运行时，可以下载 ExperimentPack。",
      "home.footer": "GOD - 治理、观察、引导",
      "home.contact": "联系：",
      "common.github": "GitHub",
      "common.library": "库",
      "common.mapPack": "地图包",
      "common.agentPack": "角色包",
      "common.locations": "地点",
      "common.downloadMapPack": "下载地图包",
      "common.downloadAgentPack": "下载角色包",
      "common.tiles": "格",
      "common.locationsCount": "个地点",
      "common.interactions": "个交互",
      "common.agents": "个角色",
      "common.profiles": "档案",
      "common.sprites": "sprites"
    }
  };

  function url(path) {
    if (!path) {
      return "#";
    }
    if (/^https?:\/\//.test(path)) {
      return path;
    }
    return root + path;
  }

  function isAbsoluteUrl(path) {
    return /^https?:\/\//.test(path || "");
  }

  function resolveLocale() {
    var param = new URLSearchParams(window.location.search).get("lang");
    if (param === "en" || param === "zh") {
      try {
        window.localStorage.setItem("godSiteLanguage", param);
      } catch (error) {}
      return param;
    }
    try {
      var stored = window.localStorage.getItem("godSiteLanguage");
      if (stored === "en" || stored === "zh") {
        return stored;
      }
    } catch (error) {}
    return pageDefaultLocale;
  }

  function assetUrl(path) {
    if (!path) {
      return "";
    }
    if (/^https?:\/\//.test(path)) {
      return path;
    }
    return assetPrefix + path;
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

  function kindLabel(kind) {
    if (locale === "zh") {
      return kind === "map" ? "地图包" : kind === "agent" ? "角色包" : "实验";
    }
    return kind === "map" ? "Map Pack" : kind === "agent" ? "Agent Pack" : "Experiment";
  }

  function text(key) {
    return (STATIC_TEXT[locale] && STATIC_TEXT[locale][key]) || STATIC_TEXT.en[key] || "";
  }

  function applyStaticText() {
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var value = text(node.getAttribute("data-i18n"));
      if (value) {
        node.textContent = value;
      }
    });
    document.querySelectorAll(".nav-links [data-nav]").forEach(function (link) {
      var href = link.getAttribute("href") || "";
      var key = "";
      if (href.indexOf("replays") !== -1) key = "nav.replays";
      if (href.indexOf("map-packs") !== -1) key = "nav.maps";
      if (href.indexOf("agent-packs") !== -1) key = "nav.agents";
      if (href.indexOf("experiments") !== -1) key = "nav.experiments";
      if (key) {
        link.textContent = text(key);
      }
    });
    var titleKey = document.body.dataset.titleI18n;
    if (titleKey) {
      document.title = text(titleKey) || document.title;
    }
  }

  function renderLanguageToggle() {
    var nav = document.querySelector(".nav-links");
    if (!nav || nav.querySelector("[data-language-toggle]")) {
      return;
    }
    var nextLocale = locale === "zh" ? "en" : "zh";
    var label = locale === "zh" ? "English" : "中文";
    var params = new URLSearchParams(window.location.search);
    params.set("lang", nextLocale);
    params.set("v", "20260603-lang-toggle");
    var href = window.location.pathname + "?" + params.toString() + window.location.hash;
    var link = document.createElement("a");
    link.className = "language-toggle";
    link.href = href;
    link.setAttribute("data-language-toggle", "");
    link.setAttribute("aria-label", locale === "zh" ? "Switch to English" : "切换到中文");
    link.textContent = label;
    nav.appendChild(link);
  }

  function renderProducts() {
    var grid = document.querySelector("[data-product-grid]");
    if (!grid || !catalog.products) {
      return;
    }
    grid.innerHTML = catalog.products.map(function (item) {
      var display = localizedCatalogItem(item);
      var label = display.label || item.label;
      var title = display.title || item.title;
      var summary = display.summary || item.summary;
      return [
        '<a class="product-card product-card--' + escapeHtml(item.key) + '" href="' + url(item.href) + '">',
        '  <span class="product-card__icon" aria-hidden="true">' + productIcon(item.key) + '</span>',
        '  <span class="product-card__label">' + escapeHtml(label) + '</span>',
        '  <strong>' + escapeHtml(title) + '</strong>',
        '  <span>' + escapeHtml(summary) + '</span>',
        '</a>'
      ].join("");
    }).join("");
  }

  function replayCard(item) {
    var display = localizedCatalogItem(item);
    var title = display.title || item.title;
    var summary = display.summary || item.summary;
    var eyebrow = display.eyebrow || item.eyebrow || text("replay.example");
    var mapPack = display.mapPack || item.mapPack;
    var agentPack = display.agentPack || item.agentPack;
    return [
      '<article class="feature-card">',
      '  <a class="feature-card__media" href="' + url(item.href) + '">',
      '    <img src="' + url(item.image) + '" alt="' + escapeHtml(title) + ' map preview" loading="lazy">',
      '  </a>',
      '  <div class="feature-card__body">',
      '    <p class="mini-label">' + escapeHtml(eyebrow) + '</p>',
      '    <h3>' + escapeHtml(title) + '</h3>',
      '    <p>' + escapeHtml(summary) + '</p>',
      '    <div class="feature-card__meta" data-replay-stats="' + escapeHtml(item.slug) + '">',
      '      <span>' + escapeHtml(text("replay.example")) + '</span><span>' + escapeHtml(mapPack) + '</span><span>' + escapeHtml(agentPack) + '</span>',
      '    </div>',
      '    <div class="button-row">',
      '      <a class="button button--small" href="' + url(item.href) + '">' + escapeHtml(text("replay.open")) + '</a>',
      '      <a class="button button--small button--ghost" href="' + url(item.manifest) + '">' + escapeHtml(text("replay.manifest")) + '</a>',
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
    var display = localizedCatalogItem(item);
    var title = display.title || item.title;
    var summary = display.summary || item.summary;
    var stats = display.stats || item.stats;
    var previewHref = item.previewHref || item.replayHref || item.href || item.download;
    var previewLabel = kind === "experiment"
      ? (locale === "zh" ? "查看示例回放" : "View example replay")
      : (locale === "zh" ? "预览" : "Preview");
    var defaultDownloadLabel = (
      kind === "experiment"
        ? (locale === "zh" ? "下载 ExperimentPack" : "Download ExperimentPack")
        : kind === "map"
          ? (locale === "zh" ? text("common.downloadMapPack") : text("common.downloadMapPack"))
          : (locale === "zh" ? text("common.downloadAgentPack") : text("common.downloadAgentPack"))
    );
    var downloadLabel = locale === "zh" ? defaultDownloadLabel : (item.downloadLabel || defaultDownloadLabel);
    var showPreview = Boolean(previewHref);
    if (kind === "experiment" && !item.previewHref && !item.replayHref && !item.href) {
      showPreview = false;
    }
    var image = item.image || (kind === "experiment" ? experimentImage(item) : "");
    var media = image
      ? '<a class="library-card__media library-card__media--' + escapeHtml(kind) + '" href="' + url(showPreview ? previewHref : item.download) + '"><img src="' + url(image) + '" alt="' + escapeHtml(title) + ' preview" loading="lazy"></a>'
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
      '    <p class="mini-label">' + escapeHtml(kindLabel(kind)) + '</p>',
      '    <h3>' + escapeHtml(title) + '</h3>',
      '    <p>' + escapeHtml(summary) + '</p>',
      metricLine({ stats: stats }),
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
        download = isAbsoluteUrl(entry.href) ? entry.href : "public-data/experiments/" + packId + "/" + entry.href;
      }
    });
    var replayHref = item.replay_slug ? "replays/" + item.replay_slug + "/" : "";
    var display = localizedCatalogItem(item);
    return {
      title: display.title || item.display_name || packId,
      slug: packId,
      summary: display.summary || item.summary || "",
      image: experimentImage(item),
      map_pack: item.map_pack || "",
      replayHref: replayHref,
      download: download,
      downloadLabel: "Download ExperimentPack",
      stats: [
        display.mapLabel || (item.map_pack ? (locale === "zh" ? item.map_pack + " 地图" : item.map_pack + " map") : ""),
        item.agent_count ? (locale === "zh" ? item.agent_count + " 个角色" : item.agent_count + " agents") : "",
        item.total_steps ? (locale === "zh" ? item.total_steps + " 步" : item.total_steps + " steps") : ""
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
    fetch(url("public-data/experiments/index.json?v=20260603-lang-toggle"))
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

  function experimentImage(item) {
    if (item.image) {
      return item.image;
    }
    var mapId = item.map_pack || item.mapPack || "";
    if (mapId === "the_ville" || item.slug === "god-town-daily-life") {
      return "assets/screenshots/map-the-ville.png";
    }
    if (mapId === "pku" || item.slug === "pku-public-situation") {
      return "assets/screenshots/map-pku.png";
    }
    if (mapId) {
      return "public-data/map-packs/" + mapId + "/preview.png";
    }
    return "";
  }

  function localizedCatalogItem(item) {
    var localized = item.localized || {};
    var entry = localized[locale] || localized.en || localized.zh || {};
    return {
      label: entry.label || "",
      title: entry.display_name || entry.title || "",
      eyebrow: entry.eyebrow || "",
      summary: entry.summary || "",
      mapLabel: entry.map_label || "",
      mapPack: entry.mapPack || entry.map_pack || "",
      agentPack: entry.agentPack || entry.agent_pack || "",
      stats: entry.stats || null
    };
  }

  function localized(value) {
    if (!value || typeof value !== "object") {
      return value || "";
    }
    return value[locale] || value.en || value.zh || "";
  }

  function renderLegacyExperiments() {
    var grid = document.querySelector("[data-experiment-grid]");
    var experiments = window.GOD_EXPERIMENTS || [];
    if (!grid || !experiments.length) {
      return;
    }
    var labels = locale === "zh" ? {
      open: "打开实验",
      folder: "仓库目录",
      repo: "仓库路径"
    } : {
      open: "Open experiment",
      folder: "Repository folder",
      repo: "Repository path"
    };
    grid.innerHTML = experiments.map(function (item) {
      var title = localized(item.title);
      var kicker = localized(item.kicker);
      var summary = localized(item.summary);
      var tryItems = localized(item.try) || [];
      var detailHref = detailBase + item.slug + ".html";
      var repoHref = "https://github.com/XiaoLuoLYG/GOD/tree/main/" + item.repoPath;
      return [
        '<article class="experiment-card">',
        '  <a class="experiment-card__media" href="' + escapeHtml(detailHref) + '">',
        '    <img src="' + escapeHtml(assetUrl(item.image)) + '" alt="' + escapeHtml(title) + ' map preview" loading="lazy">',
        '  </a>',
        '  <div class="experiment-card__body">',
        '    <p class="eyebrow">' + escapeHtml(kicker) + '</p>',
        '    <h3>' + escapeHtml(title) + '</h3>',
        '    <p>' + escapeHtml(summary) + '</p>',
        '    <ul class="experiment-card__list">',
        tryItems.map(function (entry) {
          return '<li>' + escapeHtml(entry) + '</li>';
        }).join(""),
        '    </ul>',
        '    <code class="repo-path" aria-label="' + escapeHtml(labels.repo) + '">' + escapeHtml(item.repoPath) + '</code>',
        '    <div class="button-row">',
        '      <a class="button button--small" href="' + escapeHtml(detailHref) + '">' + labels.open + '</a>',
        '      <a class="button button--small button--ghost" href="' + escapeHtml(repoHref) + '">' + labels.folder + '</a>',
        '    </div>',
        '  </div>',
        '</article>'
      ].join("");
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
              "<span>" + manifest.total_steps + (locale === "zh" ? " 步" : " steps") + "</span>",
              "<span>" + manifest.agent_count + (locale === "zh" ? " 个角色" : " agents") + "</span>",
              "<span>" + manifest.command_count + " " + text("replay.operatorRecords") + "</span>"
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
  renderLegacyExperiments();
  applyStaticText();
  renderLanguageToggle();
  markActiveNav();
  window.GOD_LOCALE = locale;
  window.GOD_TEXT = text;
  window.GOD_LOCALIZED_CATALOG_ITEM = localizedCatalogItem;
})();
