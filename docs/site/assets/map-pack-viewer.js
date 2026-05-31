(function () {
  var root = document.body.dataset.siteRoot || "";
  var slug = document.body.dataset.mapPack || "";
  var catalog = window.GOD_CATALOG || {};
  var item = (catalog.mapPacks || []).find(function (entry) {
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

  setText("[data-pack-title]", item.title || slug);
  setText("[data-pack-summary]", item.summary || "");
  document.querySelectorAll("[data-pack-download]").forEach(function (node) {
    node.setAttribute("href", url(item.download));
  });

  var imageNode = document.querySelector("[data-map-image]");
  if (imageNode && item.image) {
    imageNode.setAttribute("src", url(item.image));
    imageNode.setAttribute("alt", (item.title || slug) + " map preview");
  }

  fetch(url("public-data/map-packs/" + slug + "/map_pack.json"))
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (manifest) {
      if (!manifest) return;
      setText(
        "[data-pack-title]",
        item.title ||
          (manifest.localized && manifest.localized.en && manifest.localized.en.display_name) ||
          manifest.display_name ||
          slug
      );
      if (manifest.preview_url && imageNode) {
        imageNode.setAttribute("src", url("public-data/map-packs/" + slug + "/" + manifest.preview_url));
      }
      var stats = document.querySelector("[data-map-stats]");
      if (stats) {
        stats.innerHTML = [
          "<span>" + escapeHtml((manifest.width || 0) + " x " + (manifest.height || 0) + " tiles") + "</span>",
          "<span>" + escapeHtml((manifest.locations || []).length + " locations") + "</span>",
          "<span>" + escapeHtml((manifest.interactions || []).length + " interactions") + "</span>"
        ].join("");
      }
      var list = document.querySelector("[data-map-locations]");
      if (list) {
        list.innerHTML = (manifest.locations || []).slice(0, 32).map(function (location) {
          var anchor = location.anchor_tile || {};
          return [
            '<article class="detail-mini-card">',
            '  <strong>' + escapeHtml(location.name || location.id) + '</strong>',
            '  <span>' + escapeHtml(location.id || "") + '</span>',
            '  <small>' + escapeHtml("tile " + (anchor.x == null ? "?" : anchor.x) + ", " + (anchor.y == null ? "?" : anchor.y)) + '</small>',
            '</article>'
          ].join("");
        }).join("");
      }
    })
    .catch(function () {});
})();
