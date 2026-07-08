(function () {
  var body = document.body;
  var dataRoot = body.dataset.dataRoot || "";
  var canvas = document.querySelector("[data-map-canvas]");
  var ctx = canvas ? canvas.getContext("2d") : null;
  var state = {
    manifest: null,
    timeline: [],
    commands: [],
    profiles: [],
    mapInfo: null,
    locationNames: {},
    tiledMap: null,
    tilesetImages: [],
    agentSprites: {},
    baseCanvas: null,
    stepIndex: 0,
    frame: null,
    playing: false,
    timer: null
  };
  var colors = ["#0f766e", "#3366a3", "#d45a38", "#b7791f", "#8b5cf6", "#0ea5e9", "#db2777", "#16a34a"];
  var loadRequestId = 0;
  var pageDefaultLocale = (document.documentElement.lang || "en").toLowerCase().indexOf("zh") === 0 ? "zh" : "en";
  var locale = resolveLocale();
  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  var TEXT = {
    en: {
      navReplays: "Replays",
      navMaps: "Map Packs",
      navAgents: "Agent Packs",
      navExperiments: "Experiments",
      replay: "Replay",
      loadingReplay: "Loading replay...",
      map: "Map",
      loading: "Loading",
      downloads: "Downloads",
      agents: "Agents",
      operatorTrace: "Operator Trace",
      note: "Local setup gives the best experience. Online replays are static previews with limited live-control features.",
      play: "Play",
      pause: "Pause",
      step: "Step",
      loadingStep: "Loading step",
      loadFailed: "Replay failed to load",
      download: "Download",
      experimentPack: "Download ExperimentPack",
      noState: "No visible state",
      location: "Location",
      agent: "Agent",
      headingTo: "Heading to",
      moving: "Moving",
      active: "Active",
      ready: "Ready",
      message: "Recorded replay message",
      operatorQuestion: "Operator question",
      operatorResponse: "Recorded operator response",
      noOperator: "No operator record at",
      switchLanguage: "切换到中文",
      switchLabel: "中文",
      typeAsk: "ASK",
      typeIntervene: "INTERVENE",
      replayTitles: {
        "god-town": {
          title: "GOD Town",
          summary: "A compact town where daily routines, messages, movement, ask, and intervention can be replayed step by step.",
          documentTitle: "GOD Town Replay - GOD"
        },
        "pku-public-situation": {
          title: "PKU Public Situation",
          summary: "A campus-scale public event replay for watching attention, gathering, targeted questions, and live interventions.",
          documentTitle: "PKU Public Situation Replay - GOD"
        }
      }
    },
    zh: {
      navReplays: "回放",
      navMaps: "地图包",
      navAgents: "角色包",
      navExperiments: "实验",
      replay: "回放",
      loadingReplay: "正在加载回放...",
      map: "地图",
      loading: "加载中",
      downloads: "下载",
      agents: "角色",
      operatorTrace: "操作者记录",
      note: "本地运行体验更完整；在线回放是静态预览，实时控制能力有限。",
      play: "播放",
      pause: "暂停",
      step: "第",
      loadingStep: "正在加载步骤",
      loadFailed: "回放加载失败",
      download: "下载",
      experimentPack: "下载实验包",
      noState: "暂无可见状态",
      location: "地点",
      agent: "角色",
      headingTo: "前往",
      moving: "移动中",
      active: "活跃",
      ready: "就绪",
      message: "已记录的回放消息",
      operatorQuestion: "操作者问题",
      operatorResponse: "已记录的操作者回复",
      noOperator: "此步骤没有操作者记录：",
      switchLanguage: "Switch to English",
      switchLabel: "English",
      typeAsk: "提问",
      typeIntervene: "干预",
      replayTitles: {
        "god-town": {
          title: "GOD 小镇",
          summary: "一个紧凑小镇，可逐步回放日常行动、消息、移动、提问和干预。",
          documentTitle: "GOD 小镇回放 - GOD"
        },
        "pku-public-situation": {
          title: "北大公共情境",
          summary: "校园尺度公共事件回放，用于观察注意力、聚集、定向提问和实时干预。",
          documentTitle: "北大公共情境回放 - GOD"
        }
      }
    }
  };
  var COMMAND_TEXT = {
    ask_live_step_1_20260511_085000: {
      prompt: "Ask Jiuwen Alice where she is and what she plans to do next.",
      result: "Jiuwen Alice is in Johnson Park, starting her morning round and checking on Jiuwen George nearby."
    },
    intervene_live_step_1_20260511_085000: {
      prompt: "Move Jiuwen Alice to the cafe.",
      result: "Movement intervention queued: Jiuwen Alice is heading to Hobbs Cafe and will advance along the path on the next replay step."
    },
    ask_live_step_2_20260511_092000: {
      prompt: "Ask Jiuwen Alice what she is doing today.",
      result: "Jiuwen Alice is continuing her morning round from Johnson Park toward Hobbs Cafe, checking in with neighbors and Jiuwen George."
    },
    "95a56655dd5b44aeb6f94a9948ac215c": {
      prompt: "Ask Student Zheng what they want to do next.",
      result: "Student Zheng plans to leave Centennial Hall and walk back to the Teaching Building for an international relations class."
    }
  };
  var AGENT_NAMES = {
    "pku-public-situation": {
      "1": "Student Luo",
      "2": "Teaching Assistant Wang",
      "3": "Student Li",
      "4": "Teacher Chen",
      "5": "Professor Zhang",
      "6": "Professor Zhou",
      "7": "Alumnus Zhao",
      "8": "Auntie Liu",
      "9": "Student Wang",
      "10": "Student Sun",
      "11": "Student He",
      "12": "Reporter Lin",
      "13": "Student Zheng",
      "14": "Student Shen",
      "15": "Student Chen",
      "16": "Student Liang",
      "17": "Student Ma",
      "18": "Student Liu",
      "22": "Coordinator Wang"
    }
  };

  if (!canvas || !ctx || !dataRoot) {
    return;
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

  function $(selector) {
    return document.querySelector(selector);
  }

  function setText(selector, value) {
    var node = $(selector);
    if (node) {
      node.textContent = value == null ? "" : String(value);
    }
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function hasHan(value) {
    return /[\u3400-\u9fff]/.test(String(value || ""));
  }

  function displayText(value, fallback) {
    if (value == null || value === "") {
      return "";
    }
    var text = String(value);
    if (locale === "zh") {
      return text;
    }
    return hasHan(text) ? fallback : text;
  }

  function localizedName(item, field) {
    var key = field || "name";
    return item && item.localized && item.localized[locale] && item.localized[locale][key]
      || item && item.localized && item.localized.en && item.localized.en[key]
      || "";
  }

  function text(key) {
    return TEXT[locale][key] || TEXT.en[key] || "";
  }

  function replayCopy(field) {
    var copies = text("replayTitles") || {};
    return copies[replaySlug()] && copies[replaySlug()][field] || "";
  }

  function stepText(step) {
    return locale === "zh" ? text("step") + " " + step + " 步" : text("step") + " " + step;
  }

  function noOperatorText(step) {
    return locale === "zh" ? stepText(step) + "没有操作者记录。" : text("noOperator") + " " + stepText(step) + ".";
  }

  function applyStaticText() {
    var nav = [
      ["replays", text("navReplays")],
      ["map-packs", text("navMaps")],
      ["agent-packs", text("navAgents")],
      ["experiments", text("navExperiments")]
    ];
    document.querySelectorAll(".nav-links [data-nav]").forEach(function (link) {
      var href = link.getAttribute("href") || "";
      nav.forEach(function (item) {
        if (href.indexOf(item[0]) !== -1) {
          link.textContent = item[1];
        }
      });
    });
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var value = text(node.getAttribute("data-i18n"));
      if (value) {
        node.textContent = value;
      }
    });
    renderLanguageToggle();
  }

  function renderLanguageToggle() {
    var link = $("[data-language-toggle]");
    if (!link) {
      return;
    }
    var params = new URLSearchParams(window.location.search);
    params.set("lang", locale === "zh" ? "en" : "zh");
    link.href = window.location.pathname + "?" + params.toString() + window.location.hash;
    link.textContent = text("switchLabel");
    link.setAttribute("aria-label", text("switchLanguage"));
  }

  function buildLocationNames() {
    state.locationNames = {};
    (state.mapInfo.locations || []).forEach(function (location) {
      state.locationNames[String(location.id)] = localizedName(location) || displayText(location.name, text("location"));
    });
  }

  function replaySlug() {
    return body.dataset.replaySlug || "";
  }

  function agentName(agent) {
    var names = AGENT_NAMES[replaySlug()] || {};
    if (locale === "en" && names[String(agent && agent.id || "")]) {
      return names[String(agent && agent.id || "")];
    }
    return displayText(agent && agent.name, text("agent") + " " + (agent && agent.id || ""));
  }

  function locationName(id, fallback) {
    return state.locationNames[String(id || "")] || displayText(fallback, text("location"));
  }

  function actionLabel(agent) {
    if (locale === "zh" && agent && (agent.action || agent.status)) {
      return displayText(agent.action || agent.status, "");
    }
    if (agent && agent.action && !hasHan(agent.action)) {
      return displayText(agent.action, "");
    }
    if (agent && agent.movement_status === "moving") {
      return agent.target_location_id ? text("headingTo") + " " + locationName(agent.target_location_id, "destination") : text("moving");
    }
    if (agent && agent.status && !hasHan(agent.status)) {
      return displayText(agent.status, "");
    }
    return agent && Number(agent.message_count || 0) > 0 ? text("active") : text("ready");
  }

  function messageLabel(value) {
    return displayText(value, text("message"));
  }

  function commandsForCurrentStep() {
    var point = state.timeline[state.stepIndex] || {};
    var currentStep = Number(point.step || 0);
    var lastPoint = state.timeline[state.timeline.length - 1] || {};
    var maxStep = Number(lastPoint.step || currentStep);
    return state.commands.filter(function (command) {
      var commandStep = Number(command.step || 0);
      return commandStep === currentStep || (commandStep > maxStep && currentStep === maxStep);
    });
  }

  function dataUrl(path) {
    return dataRoot + path;
  }

  function downloadUrl(path) {
    if (/^https?:\/\//.test(path || "")) {
      return path;
    }
    return dataUrl(path);
  }

  function dataUrlBase(path) {
    var full = dataUrl(path);
    return full.slice(0, full.lastIndexOf("/") + 1);
  }

  function mapUrl(path) {
    return dataRoot + "map/" + path;
  }

  function fetchJson(path) {
    return fetch(dataUrl(path)).then(function (response) {
      if (!response.ok) {
        throw new Error("Unable to load " + path);
      }
      return response.json();
    });
  }

  function loadImage(src) {
    return new Promise(function (resolve) {
      var image = new Image();
      image.onload = function () {
        resolve(image);
      };
      image.onerror = function () {
        resolve(null);
      };
      image.src = src;
    });
  }

  function loadAgentSprites() {
    var agentPackPath = state.manifest && state.manifest.urls && state.manifest.urls.agent_pack;
    if (!agentPackPath) {
      return Promise.resolve();
    }
    return fetch(dataUrl(agentPackPath))
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (pack) {
        if (!pack || !Array.isArray(pack.agents)) {
          return;
        }
        var base = dataUrlBase(agentPackPath);
        return Promise.all(pack.agents.map(function (agent) {
          if (!agent.sprite || !agent.sprite.path) {
            return Promise.resolve();
          }
          return loadImage(base + agent.sprite.path).then(function (image) {
            if (!image) {
              return;
            }
            var sprite = {
              image: image,
              frameWidth: Number(agent.sprite.frame_width || 32),
              frameHeight: Number(agent.sprite.frame_height || 32)
            };
            state.agentSprites[String(agent.id)] = sprite;
            if (agent.name) {
              state.agentSprites[String(agent.name)] = sprite;
            }
          });
        }));
      })
      .catch(function () {});
  }

  function skipLayer(layer) {
    var name = String(layer.name || "").toLowerCase();
    return !layer.visible || name.indexOf("collision") >= 0 || name.indexOf("block") >= 0 || layer.type !== "tilelayer";
  }

  function findTileset(gid) {
    var tilesets = state.tiledMap.tilesets || [];
    for (var index = tilesets.length - 1; index >= 0; index -= 1) {
      if (gid >= Number(tilesets[index].firstgid || 1)) {
        return { tileset: tilesets[index], image: state.tilesetImages[index] };
      }
    }
    return null;
  }

  function renderBaseMap() {
    var map = state.tiledMap;
    var tileWidth = Number(map.tilewidth || state.mapInfo.tile_size || 32);
    var tileHeight = Number(map.tileheight || state.mapInfo.tile_size || 32);
    var width = Number(map.width || 1);
    var height = Number(map.height || 1);
    var base = document.createElement("canvas");
    base.width = width * tileWidth;
    base.height = height * tileHeight;
    var baseCtx = base.getContext("2d");
    baseCtx.imageSmoothingEnabled = false;
    baseCtx.fillStyle = "#eaf3ee";
    baseCtx.fillRect(0, 0, base.width, base.height);

    (map.layers || []).forEach(function (layer) {
      if (skipLayer(layer) || !Array.isArray(layer.data)) {
        return;
      }
      layer.data.forEach(function (rawGid, index) {
        var gid = Number(rawGid || 0);
        if (!gid) {
          return;
        }
        var match = findTileset(gid);
        if (!match || !match.image) {
          return;
        }
        var tileset = match.tileset;
        var localId = gid - Number(tileset.firstgid || 1);
        var columns = Number(tileset.columns || Math.floor(match.image.width / tileWidth) || 1);
        var sx = (localId % columns) * tileWidth;
        var sy = Math.floor(localId / columns) * tileHeight;
        var dx = (index % width) * tileWidth;
        var dy = Math.floor(index / width) * tileHeight;
        baseCtx.drawImage(match.image, sx, sy, tileWidth, tileHeight, dx, dy, tileWidth, tileHeight);
      });
    });
    state.baseCanvas = base;
    canvas.width = base.width;
    canvas.height = base.height;
  }

  function drawFrame() {
    if (!state.baseCanvas || !state.frame) {
      return;
    }
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(state.baseCanvas, 0, 0);
    drawLocations();
    drawAgents(state.frame.agents || []);
  }

  function drawLocations() {
    var tile = Number(state.mapInfo.tile_size || 32);
    ctx.save();
    ctx.font = "700 12px Inter, system-ui, sans-serif";
    (state.mapInfo.locations || []).forEach(function (location) {
      if (!location.anchor_tile) {
        return;
      }
      var x = Number(location.anchor_tile.x || 0) * tile + tile / 2;
      var y = Number(location.anchor_tile.y || 0) * tile + tile / 2;
      ctx.fillStyle = "rgba(255, 255, 255, 0.76)";
      var label = String(locationName(location.id, location.name || location.id || ""));
      var width = ctx.measureText(label).width + 14;
      ctx.fillRect(x - width / 2, y - 26, width, 18);
      ctx.fillStyle = "rgba(20, 32, 51, 0.72)";
      ctx.fillText(label, x - width / 2 + 7, y - 12);
    });
    ctx.restore();
  }

  function drawAgents(agents) {
    var tile = Number(state.mapInfo.tile_size || 32);
    ctx.save();
    ctx.font = "800 13px Inter, system-ui, sans-serif";
    agents.forEach(function (agent, index) {
      var x = Number(agent.tile_x);
      var y = Number(agent.tile_y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        x = 3 + (index % 10) * 4;
        y = 3 + Math.floor(index / 10) * 4;
      }
      var px = x * tile + tile / 2;
      var py = y * tile + tile / 2;
      var color = colors[index % colors.length];
      var sprite = state.agentSprites[String(agent.id)] || state.agentSprites[String(agent.name || "")];
      if (sprite && sprite.image) {
        var width = Math.min(tile * 1.2, sprite.frameWidth * 1.4);
        var height = Math.min(tile * 1.6, sprite.frameHeight * 1.6);
        ctx.drawImage(
          sprite.image,
          0,
          0,
          sprite.frameWidth,
          sprite.frameHeight,
          px - width / 2,
          py - height + tile / 2,
          width,
          height
        );
      } else {
        ctx.beginPath();
        ctx.arc(px, py, 9, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
      }

      var label = agentName(agent);
      var width = Math.min(180, ctx.measureText(label).width + 16);
      ctx.fillStyle = "rgba(255, 255, 255, 0.88)";
      ctx.fillRect(px + 10, py - 19, width, 20);
      ctx.fillStyle = "#142033";
      ctx.fillText(label, px + 18, py - 5, width - 12);
    });
    ctx.restore();
  }

  function renderDownloads() {
    var list = $("[data-download-list]");
    if (!list || !state.manifest) {
      return;
    }
    var visibleDownloads = (state.manifest.downloads || []).filter(function (item) {
      return !item.hidden && item.type !== "replay";
    });
    list.innerHTML = visibleDownloads.map(function (item) {
      var zhLabels = { map: "地图包", agent: "角色包", experiment: "可运行实验包" };
      var label = locale === "zh" ? zhLabels[item.type] || item.label : item.label;
      var descriptionText = locale === "zh" && item.type === "experiment"
        ? "仅包含场景 setup，不包含回放历史和本地运行状态。"
        : item.description || item.type;
      var description = '<span>' + escapeHtml(descriptionText) + '</span>';
      var action = item.type === "experiment" ? text("experimentPack") : text("download");
      return [
        '<a class="download-row" href="' + downloadUrl(item.href) + '">',
        '  <span><strong>' + escapeHtml(label) + '</strong>' + description + '</span>',
        '  <span>' + escapeHtml(action) + '</span>',
        '</a>'
      ].join("");
    }).join("");
  }

  function renderAgents() {
    var list = $("[data-agent-list]");
    if (!list || !state.frame) {
      return;
    }
    list.innerHTML = (state.frame.agents || []).map(function (agent, index) {
      var line = [locationName(agent.location_id, agent.location), actionLabel(agent), messageLabel(agent.last_message)].filter(Boolean).join(" · ");
      return [
        '<div class="agent-row">',
        '  <span class="agent-dot" style="background:' + colors[index % colors.length] + '"></span>',
        '  <span><strong>' + escapeHtml(agentName(agent)) + '</strong><span>' + escapeHtml(line || text("noState")) + '</span></span>',
        '</div>'
      ].join("");
    }).join("");
  }

  function renderCommands() {
    var list = $("[data-command-list]");
    if (!list) {
      return;
    }
    var point = state.timeline[state.stepIndex] || {};
    var commands = commandsForCurrentStep().sort(function (a, b) {
      return Number(a.step) - Number(b.step) || String(a.command_id).localeCompare(String(b.command_id));
    });
    list.innerHTML = commands.map(function (command) {
      var copy = locale === "en" ? COMMAND_TEXT[String(command.command_id)] || {} : {};
      var prompt = copy.prompt || displayText(command.prompt, text("operatorQuestion"));
      var result = copy.result || displayText(String(command.result || "").replace(/\s+/g, " ").slice(0, 170), text("operatorResponse"));
      var type = command.type === "intervene" ? text("typeIntervene") : text("typeAsk");
      return [
        '<div class="command-row">',
        '  <strong>' + escapeHtml(type + " · " + stepText(command.step)) + '</strong>',
        '  <span>' + escapeHtml(prompt) + '</span>',
        result ? '  <span>' + escapeHtml(result) + '</span>' : "",
        '</div>'
      ].join("");
    }).join("") || '<div class="command-row"><span>' + escapeHtml(noOperatorText(point.step || 0)) + '</span></div>';
  }

  function updateControls() {
    var range = $("[data-step-range]");
    var play = $("[data-play-toggle]");
    if (range) {
      range.max = String(Math.max(0, state.timeline.length - 1));
      range.step = "1";
      range.value = String(state.stepIndex);
    }
    if (play) {
      play.textContent = state.playing ? text("pause") : text("play");
    }
    var point = state.timeline[state.stepIndex];
    setText("[data-step-label]", point ? stepText(point.step) : stepText(0));
  }

  function loadStepByIndex(index) {
    var requestId = ++loadRequestId;
    state.stepIndex = Math.max(0, Math.min(index, state.timeline.length - 1));
    updateControls();
    var point = state.timeline[state.stepIndex];
    if (!point) {
      return Promise.resolve();
    }
    setText("[data-replay-status]", text("loadingStep") + " " + point.step);
    return fetch(dataUrl(point.frame_url || ("steps/" + String(point.step).padStart(6, "0") + ".json")))
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Missing frame");
        }
        return response.json();
      })
      .then(function (frame) {
        if (requestId !== loadRequestId) {
          return;
        }
        state.frame = frame;
        updateControls();
        renderAgents();
        renderCommands();
        drawFrame();
        setText("[data-replay-status]", stepText(frame.step) + " · " + (frame.t || ""));
      });
  }

  function bindControls() {
    var range = $("[data-step-range]");
    var play = $("[data-play-toggle]");
    function loadStepFromPointer(event) {
      var bounds = range.getBoundingClientRect();
      var ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
      pause();
      loadStepByIndex(Math.round(ratio * Math.max(0, state.timeline.length - 1)));
    }
    if (range) {
      range.addEventListener("input", function () {
        var index = Number(range.value || 0);
        pause();
        loadStepByIndex(index);
      });
      range.addEventListener("pointerdown", function (event) {
        event.preventDefault();
        if (range.setPointerCapture) {
          range.setPointerCapture(event.pointerId);
        }
        loadStepFromPointer(event);
      });
      range.addEventListener("pointermove", function (event) {
        if (event.buttons === 1) {
          loadStepFromPointer(event);
        }
      });
    }
    if (play) {
      play.addEventListener("click", function () {
        if (state.playing) {
          pause();
        } else {
          playLoop();
        }
      });
    }
  }

  function playLoop() {
    state.playing = true;
    updateControls();
    state.timer = window.setInterval(function () {
      var next = state.stepIndex + 1;
      if (next >= state.timeline.length) {
        next = 0;
      }
      loadStepByIndex(next);
    }, 1200);
  }

  function pause() {
    state.playing = false;
    if (state.timer) {
      window.clearInterval(state.timer);
      state.timer = null;
    }
    updateControls();
  }

  function init() {
    applyStaticText();
    Promise.all([
      fetchJson("manifest.json"),
      fetchJson("timeline.json"),
      fetchJson("commands.json"),
      fetchJson("agents/profiles.json"),
      fetchJson("map/map.json")
    ])
      .then(function (values) {
        state.manifest = values[0];
        state.timeline = values[1] || [];
        state.commands = values[2] || [];
        state.profiles = values[3] || [];
        state.mapInfo = values[4];
        buildLocationNames();
        document.title = replayCopy("documentTitle") || document.title;
        setText("[data-replay-title]", replayCopy("title") || displayText(state.manifest.title, "Replay"));
        setText("[data-replay-summary]", replayCopy("summary") || displayText(state.manifest.summary, text("loadingReplay")));
        setText("[data-map-title]", localizedName(state.mapInfo, "display_name") || displayText(state.mapInfo.display_name, text("map")) || text("map"));
        renderDownloads();
        return loadAgentSprites().then(function () {
          return fetchJson("map/" + state.mapInfo.tiled_map_url);
        });
      })
      .then(function (tiledMap) {
        state.tiledMap = tiledMap;
        return Promise.all((tiledMap.tilesets || []).map(function (tileset) {
          return loadImage(mapUrl(tileset.image));
        }));
      })
      .then(function (images) {
        state.tilesetImages = images;
        renderBaseMap();
        bindControls();
        return loadStepByIndex(0);
      })
      .catch(function (error) {
        setText("[data-replay-status]", text("loadFailed"));
        console.error(error);
      });
  }

  init();
})();
