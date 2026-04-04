const SETTINGS_KEY = "duckdome:settings";

const DEFAULT_SETTINGS = {
  name: "James",
  font: "Sans",
  contrast: "Normal",
  loopGuard: "4",
  ruleRefresh: "Every 10 triggers",
  desktopNotifications: false,
  soundsEnabled: true,
  defaultSound: "Soft Chime",
};

function getRootElement() {
  return typeof document !== "undefined" ? document.documentElement : null;
}

export function loadUiSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    /* ignore corrupt data */
  }
  return { ...DEFAULT_SETTINGS };
}

export function saveUiSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function applyFontPreference(font) {
  const root = getRootElement();
  if (!root) return;

  if (font === "Mono") {
    root.dataset.uiFont = "mono";
    return;
  }

  delete root.dataset.uiFont;
}

export function applyUiSettings(settings) {
  applyFontPreference(settings?.font ?? DEFAULT_SETTINGS.font);
}

export { DEFAULT_SETTINGS, SETTINGS_KEY };
