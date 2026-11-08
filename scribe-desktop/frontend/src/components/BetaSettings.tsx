"use client"

import { Switch } from "./ui/switch"
import { useConfig } from "@/contexts/ConfigContext"
import {
  BetaFeatureKey,
  BETA_FEATURE_NAMES,
  BETA_FEATURE_DESCRIPTIONS
} from "@/types/betaFeatures"
import { SettingsRow, SettingsSection } from "./settings/SettingsSection"

export function BetaSettings() {
  const { betaFeatures, toggleBetaFeature } = useConfig();

  // Define feature order for display (allows custom ordering)
  const featureOrder: BetaFeatureKey[] = ['importAndRetranscribe'];

  return (
    <SettingsSection
      title="Beta Features"
      description="Still being tested, so expect rough edges and tell us what breaks. Turning one off only hides it; your meetings are not affected."
    >
      {featureOrder.map((featureKey) => (
        <SettingsRow
          key={featureKey}
          title={BETA_FEATURE_NAMES[featureKey]}
          description={BETA_FEATURE_DESCRIPTIONS[featureKey]}
          control={
            <Switch
              aria-label={BETA_FEATURE_NAMES[featureKey]}
              checked={betaFeatures[featureKey]}
              onCheckedChange={(checked) => toggleBetaFeature(featureKey, checked)}
            />
          }
        />
      ))}
    </SettingsSection>
  );
}
