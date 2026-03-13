// Custom Jitsi Meet client tuning for private 1:1 calling.

config.p2p = {
  ...(config.p2p || {}),
  enabled: true,
  // Favor hardware-friendly mobile codecs for phones/tablets.
  mobileCodecPreferenceOrder: ["H264", "VP8", "VP9", "AV1"],
};

config.webrtcIceUdpDisable = false;
config.disableDeepLinking = false;

config.resolution = 1080;
config.constraints = {
  video: {
    height: { ideal: 1080, max: 1080, min: 240 },
    width: { ideal: 1920, max: 1920, min: 320 },
  },
};

config.maxFullResolutionParticipants = 2;

// Prefer quality over aggressive client-side downshifting for 1:1 calls.
config.videoQuality = {
  ...(config.videoQuality || {}),
  codecPreferenceOrder: ["AV1", "VP9", "VP8", "H264"],
  mobileCodecPreferenceOrder: ["H264", "VP8", "VP9", "AV1"],
  enableAdaptiveMode: false,
};

// For a 1:1 quality-first setup, send one strong stream instead of layers.
config.disableSimulcast = true;

config.lobby = {
  ...(config.lobby || {}),
  autoKnock: true,
};
