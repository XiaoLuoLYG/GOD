(function () {
  var root = document.body.dataset.siteRoot || "";
  var slug = document.body.dataset.agentPack || "";
  var catalog = window.GOD_CATALOG || {};
  var item = (catalog.agentPacks || []).find(function (entry) {
    return entry.slug === slug;
  }) || {};

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

  function profileLine(profile) {
    if (!profile || typeof profile !== "object") return "";
    return profile.persona || profile.role || profile.occupation || profile.goal || "";
  }

  setText("[data-pack-title]", item.title || slug);
  setText("[data-pack-summary]", item.summary || "");
  document.querySelectorAll("[data-pack-download]").forEach(function (node) {
    node.setAttribute("href", url(item.download));
  });

  fetch(url("public-data/agent-packs/" + slug + "/agent_pack.json"))
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (manifest) {
      if (!manifest) return;
      setText("[data-pack-title]", item.title || manifest.display_name || slug);
      var stats = document.querySelector("[data-agent-stats]");
      if (stats) {
        stats.innerHTML = [
          "<span>" + escapeHtml((manifest.agents || []).length + " agents") + "</span>",
          "<span>profiles</span>",
          "<span>sprites</span>"
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
        return [
          '<article class="agent-preview-card">',
          spriteUrl
            ? '  <img src="' + spriteUrl + '" alt="' + escapeHtml(agent.name || agent.id) + ' sprite" loading="lazy">'
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
