(function () {
  var root = document.body.dataset.siteRoot || "";
  var slug = document.body.dataset.agentPack || "";
  var catalog = window.GOD_CATALOG || {};
  var item = (catalog.agentPacks || []).find(function (entry) {
    return entry.slug === slug;
  }) || {};
  var locale = window.GOD_LOCALE || "en";
  var spriteVersion = "20260603-hires-role-sprites";
  var text = window.GOD_TEXT || function (key) {
    var fallback = {
      "common.agentPack": "Agent Pack",
      "common.library": "Library",
      "common.agents": "agents",
      "common.profiles": "profiles",
      "common.sprites": "sprites"
    };
    return fallback[key] || "";
  };

  function url(path) {
    if (!path) return "#";
    if (/^https?:\/\//.test(path)) return path;
    return root + path;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach(function (node) {
      node.textContent = value || "";
    });
  }

  function localizedItem(source) {
    if (window.GOD_LOCALIZED_CATALOG_ITEM) {
      return window.GOD_LOCALIZED_CATALOG_ITEM(source);
    }
    var localized = source.localized || {};
    return localized[locale] || localized.en || localized.zh || {};
  }

  function localizedManifest(manifest) {
    var localized = manifest.localized || {};
    return localized[locale] || localized.en || localized.zh || {};
  }

  function profileLine(profile) {
    if (!profile || typeof profile !== "object") return "";
    return profile.persona || profile.role || profile.occupation || profile.goal || "";
  }

  function bindDownloadButton() {
    if (!item.download) return;
    var buttons = document.querySelectorAll("[data-pack-download]");
    if (!buttons.length) {
      var detail = document.querySelector(".pack-detail");
      var stats = document.querySelector("[data-agent-stats]");
      if (detail) {
        var row = document.createElement("div");
        row.className = "button-row";
        row.innerHTML = '<a class="button" data-pack-download href="' + escapeHtml(url(item.download)) + '">' + escapeHtml(text("common.downloadAgentPack") || "Download Agent Pack") + '</a>';
        if (stats && stats.parentNode === detail) {
          detail.insertBefore(row, stats.nextSibling);
        } else {
          detail.insertBefore(row, detail.firstChild);
        }
        buttons = document.querySelectorAll("[data-pack-download]");
      }
    }
    buttons.forEach(function (node) {
      node.setAttribute("href", url(item.download));
    });
  }

  var display = localizedItem(item);
  var title = display.title || item.title || "";
  var summary = display.summary || item.summary || "";

  setText("[data-pack-title]", title || slug);
  setText("[data-pack-summary]", summary);
  setText(".page-hero .mini-label", text("common.agentPack"));
  setText(".footer-inner > span:first-child", "GOD " + text("common.agentPack"));
  setText(".footer-inner a[href='../']", text("common.library"));
  bindDownloadButton();

  fetch(url("public-data/agent-packs/" + slug + "/agent_pack.json"))
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (manifest) {
      if (!manifest) return;
      var manifestDisplay = localizedManifest(manifest);
      var manifestTitle = title || manifestDisplay.display_name || manifest.display_name || slug;
      setText("[data-pack-title]", manifestTitle);
      if (!summary) {
        setText("[data-pack-summary]", manifestDisplay.summary || manifest.summary || "");
      }
      document.title = manifestTitle + " - GOD";
      var stats = document.querySelector("[data-agent-stats]");
      if (stats) {
        stats.innerHTML = [
          "<span>" + escapeHtml((manifest.agents || []).length + " " + text("common.agents")) + "</span>",
          "<span>" + escapeHtml(text("common.profiles")) + "</span>",
          "<span>" + escapeHtml(text("common.sprites")) + "</span>"
        ].join("");
      }
      return Promise.all((manifest.agents || []).map(function (agent) {
        return fetch(url("public-data/agent-packs/" + slug + "/" + agent.profile_path))
          .then(function (response) {
            return response.ok ? response.json() : {};
          })
          .catch(function () {
            return {};
          })
          .then(function (profile) {
            return { agent: agent, profile: profile };
          });
      }));
    })
    .then(function (entries) {
      if (!entries) return;
      var grid = document.querySelector("[data-agent-grid]");
      if (!grid) return;
      grid.innerHTML = entries.map(function (entry) {
        var agent = entry.agent || {};
        var profile = entry.profile || {};
        var sprite = agent.sprite || {};
        var spriteUrl = sprite.path ? url("public-data/agent-packs/" + slug + "/" + sprite.path) : "";
        if (spriteUrl && spriteUrl.indexOf("?") === -1) {
          spriteUrl += "?v=" + spriteVersion;
        }
        var spriteSrc = spriteUrl ? encodeURI(spriteUrl) : "";
        return [
          '<article class="agent-preview-card">',
          spriteSrc
            ? '  <img src="' + escapeHtml(spriteSrc) + '" alt="' + escapeHtml(agent.name || agent.id) + ' sprite" loading="eager" decoding="async">'
            : '  <div class="agent-preview-placeholder" aria-hidden="true">G</div>',
          '  <div>',
          '    <strong>' + escapeHtml(profile.name || agent.name || agent.id) + '</strong>',
          '    <p>' + escapeHtml(profileLine(profile)) + '</p>',
          '  </div>',
          '</article>'
        ].join("");
      }).join("");
    })
    .catch(function () {});
})();
