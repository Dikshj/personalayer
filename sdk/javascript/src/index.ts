export interface PersonalLayerBundle {
  hot_context: Array<{ id: string; label: string; strength: number }>;
  warm_context: Array<{ id: string; label: string; strength: number }>;
  cool_context: Array<{ id: string; label: string; strength: number }>;
  generated_at: string;
  version: string;
}

export interface TrackEvent {
  event_type: string;
  [key: string]: unknown;
}

export interface SDKConfig {
  daemonURL?: string;
  fallbackEnabled?: boolean;
  timeoutMs?: number;
}

const DEFAULT_DAEMON_URL = 'http://127.0.0.1:7432';
const DEFAULT_TIMEOUT = 5000;

/** Detect if the Personal Layer browser extension is installed. */
function isExtensionPresent(): boolean {
  return document.documentElement.getAttribute('data-cl-ext') === '1';
}

/** Send a message to the extension via chrome.runtime. */
function sendExtensionMessage<T>(type: string, payload?: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    if (typeof chrome === 'undefined' || !chrome.runtime) {
      reject(new Error('Chrome runtime not available'));
      return;
    }
    chrome.runtime.sendMessage(
      { type, payload, origin: window.location.origin },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else if (response && response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response as T);
        }
      }
    );
  });
}

export class PersonalLayerSDK {
  private daemonURL: string;
  private fallbackEnabled: boolean;
  private timeoutMs: number;

  constructor(config: SDKConfig = {}) {
    this.daemonURL = config.daemonURL || DEFAULT_DAEMON_URL;
    this.fallbackEnabled = config.fallbackEnabled ?? false;
    this.timeoutMs = config.timeoutMs || DEFAULT_TIMEOUT;
  }

  async isAvailable(): Promise<boolean> {
    // Try extension first
    if (isExtensionPresent()) {
      try {
        const result = await sendExtensionMessage<{ available: boolean }>('CL_CHECK_AVAILABLE');
        return result.available;
      } catch {
        // Extension present but unresponsive, fall through to localhost
      }
    }
    // Fallback to localhost
    try {
      const res = await fetch(`${this.daemonURL}/health`, { method: 'GET', mode: 'cors' });
      return res.ok;
    } catch {
      return false;
    }
  }

  async getBundle(): Promise<PersonalLayerBundle | null> {
    // Try extension first
    if (isExtensionPresent()) {
      try {
        const result = await sendExtensionMessage<PersonalLayerBundle>('GET_BUNDLE');
        return result;
      } catch {
        // Fall through
      }
    }

    // Only fall back to localhost if explicitly enabled
    if (!this.fallbackEnabled) {
      console.warn('[PersonalLayerSDK] Extension not available and localhost fallback disabled. Set fallbackEnabled: true to use localhost.');
      return null;
    }

    try {
      const res = await fetch(`${this.daemonURL}/v1/context/bundle`, { mode: 'cors' });
      if (!res.ok) return null;
      return (await res.json()) as PersonalLayerBundle;
    } catch {
      return null;
    }
  }

  async track(event: TrackEvent): Promise<boolean> {
    if (isExtensionPresent()) {
      try {
        await sendExtensionMessage('TRACK', event);
        return true;
      } catch {
        // Fall through
      }
    }

    if (!this.fallbackEnabled) {
      console.warn('[PersonalLayerSDK] Extension not available and localhost fallback disabled.');
      return false;
    }

    try {
      const res = await fetch(`${this.daemonURL}/v1/ingest/extension`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        mode: 'cors',
        body: JSON.stringify(event)
      });
      return res.ok;
    } catch {
      return false;
    }
  }
}

export async function getBundle(config?: SDKConfig): Promise<PersonalLayerBundle | null> {
  return new PersonalLayerSDK(config).getBundle();
}

export async function track(event: TrackEvent, config?: SDKConfig): Promise<boolean> {
  return new PersonalLayerSDK(config).track(event);
}

export async function isAvailable(config?: SDKConfig): Promise<boolean> {
  return new PersonalLayerSDK(config).isAvailable();
}
