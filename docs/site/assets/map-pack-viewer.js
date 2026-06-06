(function () {
  var root = document.body.dataset.siteRoot || "";
  var slug = document.body.dataset.mapPack || "";
  var catalog = window.GOD_CATALOG || {};
  var item = (catalog.mapPacks || []).find(function (entry) {
    return entry.slug === slug;
  }) || {};
  var locale = window.GOD_LOCALE || "en";
  var text = window.GOD_TEXT || function (key) {
    var fallback = {
      "common.mapPack": "Map Pack",
      "common.locations": "Locations",
      "common.downloadMapPack": "Download Map Pack",
      "common.library": "Library",
      "common.tiles": "tiles",
      "common.locationsCount": "locations",
      "common.interactions": "interactions"
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

  function countLabel(count, key) {
    return count + " " + text(key);
  }

  var display = localizedItem(item);
  var title = display.title || item.title || "";
  var summary = display.summary || item.summary || "";

  setText("[data-pack-title]", title || slug);
  setText("[data-pack-summary]", summary);
  setText(".page-hero .mini-label", text("common.mapPack"));
  setText(".footer-inner > span:first-child", "GOD " + text("common.mapPack"));
  setText(".footer-inner a[href='../']", text("common.library"));
  document.querySelectorAll("[data-pack-download]").forEach(function (node) {
    node.setAttribute("href", url(item.download));
    node.textContent = text("common.downloadMapPack");
  });

  var imageNode = document.querySelector("[data-map-image]");
  if (imageNode && item.image) {
    imageNode.setAttribute("src", url(item.image));
    imageNode.setAttribute("alt", title + " map preview");
  }

  fetch(url("public-data/map-packs/" + slug + "/map_pack.json"))
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (manifest) {
      if (!manifest) return;
      var manifestDisplay = localizedManifest(manifest);
      var manifestTitle = title || manifestDisplay.display_name || manifest.display_name || slug;
      setText(
        "[data-pack-title]",
        manifestTitle
      );
      if (!summary) {
        setText("[data-pack-summary]", manifestDisplay.summary || manifest.summary || "");
      }
      document.title = manifestTitle + " - GOD";
      if (manifest.preview_url && imageNode) {
        imageNode.setAttribute("src", url("public-data/map-packs/" + slug + "/" + manifest.preview_url));
        imageNode.setAttribute("alt", manifestTitle + " map preview");
      }
      var stats = document.querySelector("[data-map-stats]");
      if (stats) {
        stats.innerHTML = [
          "<span>" + escapeHtml((manifest.width || 0) + " x " + (manifest.height || 0) + " " + text("common.tiles")) + "</span>",
          "<span>" + escapeHtml(countLabel((manifest.locations || []).length, "common.locationsCount")) + "</span>",
          "<span>" + escapeHtml(countLabel((manifest.interactions || []).length, "common.interactions")) + "</span>"
        ].join("");
      }
      setText(".pack-side .mini-label", text("common.locations"));
      var list = document.querySelector("[data-map-locations]");
      if (list) {
        list.innerHTML = (manifest.locations || []).slice(0, 32).map(function (location) {
          var anchor = location.anchor_tile || {};
          return [
            '<article class="detail-mini-card">',
            '  <strong>' + escapeHtml(location.name || location.id) + '</strong>',
            '  <span>' + escapeHtml(location.id || "") + '</span>',
            '  <small>' + escapeHtml((locale === "zh" ? "格 " : "tile ") + (anchor.x == null ? "?" : anchor.x) + ", " + (anchor.y == null ? "?" : anchor.y)) + '</small>',
            '</article>'
          ].join("");
        }).join("");
      }
    })
    .catch(function () {});
})();
