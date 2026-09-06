// Usage analytics has been removed from this app -- no data is collected,
// no consent toggle exists, and nothing here reaches the network or the
// Tauri backend. These methods are kept as no-ops purely so call sites
// throughout the app don't need individual changes.
export class Analytics {
  static async track(_eventName: string, _properties?: Record<string, string>): Promise<void> {}

  static async trackPageView(_pageName: string): Promise<void> {}
  static async trackButtonClick(_buttonName: string, _location?: string): Promise<void> {}
  static async trackError(_errorType: string, _errorMessage: string): Promise<void> {}
  static async trackFeatureUsed(_featureName: string): Promise<void> {}
  static async trackSettingsChanged(_settingType: string, _newValue: string): Promise<void> {}
  static async trackMeetingDeleted(_meetingId: string): Promise<void> {}
  static async trackCopy(_copyType: 'transcript' | 'summary', _properties?: Record<string, any>): Promise<void> {}
  static async trackBackendConnection(_success: boolean, _error?: string): Promise<void> {}
  static async trackTranscriptionError(_errorMessage: string): Promise<void> {}
  static async trackTranscriptionSuccess(_duration?: number): Promise<void> {}
  static async trackCustomPromptUsed(_promptLength: number): Promise<void> {}
  static async trackModelChanged(
    _oldProvider: string,
    _oldModel: string,
    _newProvider: string,
    _newModel: string
  ): Promise<void> {}
  static async trackSummaryGenerationStarted(
    _modelProvider: string,
    _modelName: string,
    _transcriptLength: number,
    _timeSinceRecordingMinutes?: number
  ): Promise<void> {}
  static async trackSummaryGenerationCompleted(
    _modelProvider: string,
    _modelName: string,
    _success: boolean,
    _durationSeconds?: number,
    _errorMessage?: string
  ): Promise<void> {}
  static async trackMeetingCompleted(
    _meetingId: string,
    _metrics: {
      duration_seconds: number;
      transcript_segments: number;
      transcript_word_count: number;
      words_per_minute: number;
      meetings_today: number;
    }
  ): Promise<void> {}

  static async updateMeetingCount(): Promise<void> {}
  static async getMeetingsCountToday(): Promise<number> {
    return 0;
  }
  static async calculateDaysSince(_dateKey: string): Promise<number | null> {
    return null;
  }
}

export default Analytics;
