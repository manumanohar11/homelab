// Custom Jitsi Meet client tuning for private 1:1 calling.

config.p2p = {
  ...(config.p2p || {}),
  enabled: true,
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

config.lobby = {
  ...(config.lobby || {}),
  autoKnock: true,
};
