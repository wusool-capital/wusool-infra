// @ts-nocheck

export const discoveryReadStatusEnum = {
  not_needed: 'not_needed',
  available: 'available',
  running: 'running',
  done: 'done',
  skipped: 'skipped',
  unavailable: 'unavailable',
  failed: 'failed',
} as const;

export type DiscoveryReadStatusEnumKey = (typeof discoveryReadStatusEnum)[keyof typeof discoveryReadStatusEnum];

export type DiscoveryRead = {
  message: string | null;
  /**
   * @default []
   * @type array
   */
  notes: string[];
  status: DiscoveryReadStatusEnumKey;
};
