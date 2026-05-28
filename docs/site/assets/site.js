(function () {
  function currentLanguage() {
    return document.documentElement.lang && document.documentElement.lang.startsWith("zh") ? "zh" : "en";
  }

  function imageFor(experiment) {
    return (document.body.dataset.assetPrefix || "") + experiment.image;
  }

  function detailFor(experiment) {
    return (document.body.dataset.detailBase || "") + experiment.slug + ".html";
  }

  function renderExperimentCards() {
    var grid = document.querySelector("[data-experiment-grid]");
    if (!grid || !window.GOD_EXPERIMENTS) {
      return;
    }
    var lang = currentLanguage();
    grid.innerHTML = window.GOD_EXPERIMENTS.map(function (experiment) {
      var bullets = experiment.try[lang].map(function (item) {
        return "<li>" + item + "</li>";
      }).join("");
      return [
        '<article class="experiment-card">',
        '  <a class="experiment-card__image" href="' + detailFor(experiment) + '">',
        '    <img src="' + imageFor(experiment) + '" alt="' + experiment.title[lang] + ' map preview" loading="lazy">',
        "  </a>",
        '  <div class="experiment-card__body">',
        '    <p class="eyebrow">' + experiment.kicker[lang] + "</p>",
        "    <h3>" + experiment.title[lang] + "</h3>",
        "    <p>" + experiment.summary[lang] + "</p>",
        '    <ul class="compact-list">' + bullets + "</ul>",
        '    <a class="text-link" href="' + detailFor(experiment) + '">' + (lang === "zh" ? "查看实验" : "View experiment") + "</a>",
        "  </div>",
        "</article>"
      ].join("");
    }).join("");
  }

  function markActiveNav() {
    var path = window.location.pathname;
    document.querySelectorAll("[data-nav]").forEach(function (link) {
      if (path.endsWith(link.getAttribute("href"))) {
        link.setAttribute("aria-current", "page");
      }
    });
  }

  renderExperimentCards();
  markActiveNav();
})();
