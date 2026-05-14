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
}

const DEFAULT_DAEMON_URL = 'http://127.0.0.1:7432';

export class PersonalLayerSDK {
  private daemonURL: string;
  private fallbackEnabled: boolean;

  constructor(config: SDKConfig = {}) {
    this.daemonURL = config.daemonURL || DEFAULT_DAEMON_URL;
    this.fallbackEnabled = config.fallbackEnabled || false;
  }

  async isAvailable(): Promise<boolean> {
    try {
      const res = await fetch(`${this.daemonURL}/health`, { method: 'GET', mode: 'cors' });
      return res.ok;
    } catch {
      return false;
    }
  }

  async getBundle(): Promise<PersonalLayerBundle | null> {
    try {
      const res = await fetch(`${this.daemonURL}/v1/context/bundle`, { mode: 'cors' });
      if (!res.ok) return null;
      return (await res.json()) as PersonalLayerBundle;
    } catch {
      return null;
    }
  }

  async track(event: TrackEvent): Promise<boolean> {
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
