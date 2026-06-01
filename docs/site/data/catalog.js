window.GOD_CATALOG = {
  products: [
    {
      key: "experiment",
      label: "Experiment",
      title: "Play setup seeds",
      summary: "Download a playable setup with map, cast, scenario, and steps.",
      href: "experiments/"
    },
    {
      key: "replay",
      label: "Replay",
      title: "Watch example outcomes",
      summary: "Open curated replay archives in the browser.",
      href: "replays/"
    },
    {
      key: "map",
      label: "Map Pack",
      title: "Publish places",
      summary: "Download maps, locations, and interactions.",
      href: "map-packs/"
    },
    {
      key: "agent",
      label: "Agent Pack",
      title: "Publish casts",
      summary: "Download reusable profiles and sprites.",
      href: "agent-packs/"
    }
  ],
  replays: [
    {
      slug: "god-town",
      title: "GOD Town",
      eyebrow: "Daily life baseline",
      summary: "A compact town where routines, direct messages, movement, ask, and intervention can be replayed step by step.",
      image: "assets/screenshots/map-the-ville.png",
      href: "replays/god-town/",
      manifest: "public-data/replays/god-town/manifest.json",
      mapPack: "The Ville Pixel Map",
      agentPack: "Jiuwen Town Residents"
    },
    {
      slug: "pku-public-situation",
      title: "PKU Public Situation",
      eyebrow: "Campus public event",
      summary: "A campus-scale public situation replay for watching attention, gathering, targeted questions, and live interventions.",
      image: "assets/screenshots/map-pku.png",
      href: "replays/pku-public-situation/",
      manifest: "public-data/replays/pku-public-situation/manifest.json",
      mapPack: "PKU Yanyuan",
      agentPack: "PKU Campus Cast"
    }
  ],
  mapPacks: [
    {
      title: "The Ville Pixel Map",
      slug: "the_ville",
      summary: "A warm small-town map with homes, school, cafe, park, market, pharmacy, pub, and location-scoped interactions.",
      image: "assets/screenshots/map-the-ville.png",
      download: "public-data/map-packs/the_ville/downloads/the_ville-map-pack.zip",
      previewHref: "map-packs/the_ville/",
      stats: ["10 locations", "65 interactions", "Tiled layers"]
    },
    {
      title: "PKU Yanyuan",
      slug: "pku",
      summary: "A stylized campus map with gates, lake, library, teaching buildings, dormitory, canteen, and public-event anchors.",
      image: "assets/screenshots/map-pku.png",
      download: "public-data/map-packs/pku/downloads/pku-map-pack.zip",
      previewHref: "map-packs/pku/",
      stats: ["14 locations", "campus route graph", "location art"]
    }
  ],
  agentPacks: [
    {
      title: "Jiuwen Town Residents",
      slug: "jiuwen-town-residents",
      summary: "Ten town personas with routines, relationships, needs, worries, inventories, messages, and map positions.",
      image: "public-data/agent-packs/jiuwen-town-residents/characters/Abigail_Chen.png",
      download: "public-data/agent-packs/jiuwen-town-residents/downloads/jiuwen-town-residents-agent-pack.zip",
      previewHref: "agent-packs/jiuwen-town-residents/",
      stats: ["10 agents", "daily routines", "social ties"]
    },
    {
      title: "PKU Campus Cast",
      slug: "pku-campus-cast",
      summary: "Twenty-two campus personas spanning students, faculty, visitors, press, and event coordinators.",
      image: "public-data/agent-packs/pku-campus-cast/characters/PKU_Agent_01.png",
      download: "public-data/agent-packs/pku-campus-cast/downloads/pku-campus-cast-agent-pack.zip",
      previewHref: "agent-packs/pku-campus-cast/",
      stats: ["22 agents", "campus roles", "public-event reactions"]
    }
  ],
  experiments: [
    {
      title: "GOD Town Daily Life",
      slug: "god-town-daily-life",
      summary: "A reproducible town scenario for ordinary routines, targeted ask, and small operator interventions.",
      image: "assets/screenshots/map-the-ville.png",
      replayHref: "replays/god-town/",
      download: "public-data/experiments/god-town-daily-life/downloads/god-town-daily-life-experiment-pack.zip",
      downloadLabel: "Download ExperimentPack",
      stats: ["The Ville map", "10 residents", "playable setup"]
    },
    {
      title: "PKU Public Situation",
      slug: "pku-public-situation",
      summary: "A reproducible campus setup for public notices, crowd movement, interviews, and interventions.",
      image: "assets/screenshots/map-pku.png",
      replayHref: "replays/pku-public-situation/",
      download: "public-data/experiments/pku-public-situation/downloads/pku-public-situation-experiment-pack.zip",
      downloadLabel: "Download ExperimentPack",
      stats: ["PKU map", "22 agents", "playable setup"]
    }
  ]
};
