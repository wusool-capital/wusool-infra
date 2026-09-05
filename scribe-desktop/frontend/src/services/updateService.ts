/**
 * Update Service
 *
 * Handles automatic software updates using Tauri updater plugin.
 * Provides update checking, downloading, and installation functionality.
 */

import { check, Update } from '@tauri-apps/plugin-updater';
import { getVersion } from '@tauri-apps/api/app';

export interface UpdateInfo {
  available: boolean;
  currentVersion: string;
  version?: string;
  date?: string;
  body?: string;
  downloadUrl?: string;
}

export interface UpdateProgress {
  downloaded: number;
  total: number;
  percentage: number;
}

/**
 * Update Service
 * Singleton service for managing app updates
 */
export class UpdateService {
  private updateCheckInProgress = false;
  private lastCheckTime: number | null = null;
  private pendingUpdate: Update | null = null;
  private readonly CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000; // 24 hours

  /**
   * Check for available updates
   * @param force Force check even if recently checked
   * @returns Promise with update information
   */
  async checkForUpdates(force = false): Promise<UpdateInfo> {
    // Prevent concurrent update checks
    if (this.updateCheckInProgress) {
      throw new Error('Update check already in progress');
    }

    // Skip if checked recently (unless forced)
    if (!force && this.lastCheckTime) {
      const timeSinceLastCheck = Date.now() - this.lastCheckTime;
      if (timeSinceLastCheck < this.CHECK_INTERVAL_MS) {
        console.log('Skipping update check - checked recently');
        return {
          available: false,
          currentVersion: await getVersion(),
        };
      }
    }

    this.updateCheckInProgress = true;
    this.lastCheckTime = Date.now();

    try {
      const currentVersion = await getVersion();
      const update = await check();

      if (update?.available) {
        this.pendingUpdate = update;
        return {
          available: true,
          currentVersion,
          version: update.version,
          date: update.date,
          body: update.body,
        };
      }

      this.pendingUpdate = null;
      return {
        available: false,
        currentVersion,
      };
    } catch (error) {
      console.error('Failed to check for updates:', error);
      throw error;
    } finally {
      this.updateCheckInProgress = false;
    }
  }

  /**
   * The `Update` handle from the most recent successful `checkForUpdates()`
   * call, if one is available. Lets callers act on it without re-checking.
   */
  getPendingUpdate(): Update | null {
    return this.pendingUpdate;
  }

  /**
   * Get the current app version
   * @returns Promise with version string
   */
  async getCurrentVersion(): Promise<string> {
    return getVersion();
  }

  /**
   * Check if an update check was performed recently
   * @returns true if checked within the interval
   */
  wasCheckedRecently(): boolean {
    if (!this.lastCheckTime) return false;
    const timeSinceLastCheck = Date.now() - this.lastCheckTime;
    return timeSinceLastCheck < this.CHECK_INTERVAL_MS;
  }
}

// Export singleton instance
export const updateService = new UpdateService();
