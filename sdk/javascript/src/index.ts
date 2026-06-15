export interface PersonalLayerBundle {
  hot_context: Array<{ id: string; label: string; strength: number }>;
  warm_context: Array<{ id: string; label: string; strength: number }>;
  cool_context: Array<{ id: string; label: string; strength: number }>;
  generated_at: string;
  version: string;
}

declare const chrome: any;

export interface TrackEvent {
  event_type: string;
  [key: string]: unknown;
}

export interface SDKConfig {
  daemonURL?: string;
  fallbackEnabled?: boolean;
  timeoutMs?: number;
  maxRetries?: number;
  apiKey?: string;
  userToken?: string;
}

const DEFAULT_DAEMON_URL = 'http://127.0.0.1:7823';
const DEFAULT_TIMEOUT = 5000;
const DEFAULT_RETRIES = 2;

export class PCLAuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PCLAuthError';
  }
}

export class PCLConsentError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PCLConsentError';
  }
}

export class PCLPrivacyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PCLPrivacyError';
  }
}

export class PCLTimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PCLTimeoutError';
  }
}

export class PCLServerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PCLServerError';
  }
}

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
      (response: any) => {
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
  private maxRetries: number;
  private apiKey: string;
  private userToken: string;

  constructor(config: SDKConfig = {}) {
    this.daemonURL = config.daemonURL || DEFAULT_DAEMON_URL;
    this.fallbackEnabled = config.fallbackEnabled ?? false;
    this.timeoutMs = config.timeoutMs || DEFAULT_TIMEOUT;
    this.maxRetries = config.maxRetries ?? DEFAULT_RETRIES;
    this.apiKey = config.apiKey || '';
    this.userToken = config.userToken || '';
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      h['Authorization'] = `Bearer ${this.apiKey}`;
    }
    if (this.userToken) {
      h['x-user-token'] = this.userToken;
    }
    return h;
  }

  private async fetchWithRetry(
    url: string,
    init: RequestInit
  ): Promise<Response> {
    let lastError: Error | null = null;
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);
        const resp = await fetch(url, {
          ...init,
          signal: controller.signal,
          headers: { ...this.headers(), ...(init.headers || {}) },
        });
        clearTimeout(timeoutId);
        return resp;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (lastError.name === 'AbortError') {
          lastError = new PCLTimeoutError(`Request to ${url} timed out after ${this.timeoutMs}ms`);
        }
        // Exponential backoff
        await new Promise((r) => setTimeout(r, 300 * Math.pow(2, attempt)));
      }
    }
    throw lastError || new PCLTimeoutError(`Request to ${url} failed after ${this.maxRetries} retries`);
  }

  private async handleResponse(resp: Response): Promise<any> {
    let body: any;
    try {
      body = await resp.json();
    } catch {
      body = { raw: await resp.text() };
    }
    if (resp.status === 401) {
      throw new PCLAuthError(body.detail || 'Unauthorized');
    }
    if (resp.status === 403) {
      throw new PCLPrivacyError(body.detail || 'Forbidden');
    }
    if (resp.status === 409 && /consent/i.test(body.detail || '')) {
      throw new PCLConsentError(body.detail || 'Consent required');
    }
    if (resp.status >= 500) {
      throw new PCLServerError(body.detail || `Server error ${resp.status}`);
    }
    if (!resp.ok) {
      throw new Error(body.detail || `HTTP ${resp.status}`);
    }
    return body;
  }

  async isAvailable(): Promise<boolean> {
    if (isExtensionPresent()) {
      try {
        const result = await sendExtensionMessage<{ available: boolean }>('CL_CHECK_AVAILABLE');
        return result.available;
      } catch {
        // Extension present but unresponsive, fall through to localhost
      }
    }
    try {
      const res = await this.fetchWithRetry(`${this.daemonURL}/health`, { method: 'GET', mode: 'cors' });
      return res.ok;
    } catch {
      return false;
    }
  }

  async getBundle(): Promise<PersonalLayerBundle | null> {
    if (isExtensionPresent()) {
      try {
        const result = await sendExtensionMessage<PersonalLayerBundle>('GET_BUNDLE');
        return result;
      } catch {
        // Fall through
      }
    }
    if (!this.fallbackEnabled) {
      console.warn('[PersonalLayerSDK] Extension not available and localhost fallback disabled.');
      return null;
    }
    const res = await this.fetchWithRetry(`${this.daemonURL}/v1/context/bundle`, { method: 'GET', mode: 'cors' });
    return this.handleResponse(res);
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
    const res = await this.fetchWithRetry(`${this.daemonURL}/v1/ingest/extension`, {
      method: 'POST',
      body: JSON.stringify(event),
    });
    await this.handleResponse(res);
    return true;
  }

  /** Request consent for scopes if not already granted. */
  async ensureConsent(scopes: string[]): Promise<void> {
    if (!this.fallbackEnabled) {
      throw new PCLConsentError('Cannot ensure consent: localhost fallback disabled');
    }
    const res = await this.fetchWithRetry(`${this.daemonURL}/pcl/permissions`, {
      method: 'POST',
      body: JSON.stringify({ scopes }),
    });
    const body = await this.handleResponse(res);
    if (body.status !== 'granted') {
      throw new PCLConsentError(body.reason || 'Consent not granted');
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
