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

  if (!canvas || !ctx || !dataRoot) {
    return;
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
      var label = String(location.name || location.id || "");
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

      var label = String(agent.name || "Agent " + agent.id);
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
      var description = item.description ? '<span>' + escapeHtml(item.description) + '</span>' : '<span>' + escapeHtml(item.type) + '</span>';
      var action = item.type === "experiment" ? "Download ExperimentPack" : "Download";
      return [
        '<a class="download-row" href="' + downloadUrl(item.href) + '">',
        '  <span><strong>' + escapeHtml(item.label) + '</strong>' + description + '</span>',
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
      var line = [agent.location, agent.action || agent.status, agent.last_message].filter(Boolean).join(" · ");
      return [
        '<div class="agent-row">',
        '  <span class="agent-dot" style="background:' + colors[index % colors.length] + '"></span>',
        '  <span><strong>' + escapeHtml(agent.name) + '</strong><span>' + escapeHtml(line || "No visible state") + '</span></span>',
        '</div>'
      ].join("");
    }).join("");
  }

  function renderCommands() {
    var list = $("[data-command-list]");
    if (!list) {
      return;
    }
    var commands = state.commands.slice().sort(function (a, b) {
      return Number(a.step) - Number(b.step) || String(a.command_id).localeCompare(String(b.command_id));
    });
    list.innerHTML = commands.map(function (command) {
      var result = String(command.result || "").replace(/\s+/g, " ").slice(0, 170);
      return [
        '<div class="command-row">',
        '  <strong>' + escapeHtml(command.type.toUpperCase() + " · step " + command.step) + '</strong>',
        '  <span>' + escapeHtml(command.prompt) + '</span>',
        result ? '  <span>' + escapeHtml(result) + '</span>' : "",
        '</div>'
      ].join("");
    }).join("") || '<div class="command-row"><span>No operator records in this replay.</span></div>';
  }

  function updateControls() {
    var range = $("[data-step-range]");
    var play = $("[data-play-toggle]");
    if (range) {
      range.max = String(Math.max(0, state.timeline.length - 1));
      range.value = String(state.stepIndex);
    }
    if (play) {
      play.textContent = state.playing ? "Pause" : "Play";
    }
    var point = state.timeline[state.stepIndex];
    setText("[data-step-label]", point ? "Step " + point.step : "Step 0");
  }

  function loadStepByIndex(index) {
    state.stepIndex = Math.max(0, Math.min(index, state.timeline.length - 1));
    var point = state.timeline[state.stepIndex];
    if (!point) {
      return Promise.resolve();
    }
    setText("[data-replay-status]", "Loading step " + point.step);
    return fetch(dataUrl(point.frame_url || ("steps/" + String(point.step).padStart(6, "0") + ".json")))
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Missing frame");
        }
        return response.json();
      })
      .then(function (frame) {
        state.frame = frame;
        updateControls();
        renderAgents();
        renderCommands();
        drawFrame();
        setText("[data-replay-status]", "Step " + frame.step + " · " + (frame.t || ""));
      });
  }

  function bindControls() {
    var range = $("[data-step-range]");
    var play = $("[data-play-toggle]");
    if (range) {
      range.addEventListener("input", function () {
        pause();
        loadStepByIndex(Number(range.value || 0));
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
        setText("[data-replay-title]", state.manifest.title);
        setText("[data-replay-summary]", state.manifest.summary);
        setText("[data-map-title]", state.mapInfo.display_name || "Map");
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
        setText("[data-replay-status]", "Replay failed to load");
        console.error(error);
      });
  }

  init();
})();
