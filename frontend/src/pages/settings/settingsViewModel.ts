import type {
  SettingsConfigSummary,
  SettingsProvider,
} from "../../shared/api/platoApi";
import type { ApiError } from "../../shared/api/types";
import { settingsProviderLabel } from "./settingsCopy";

export type SettingsFormState = {
  apiKey: string;
  model: string;
  provider: SettingsProvider;
  selectedProfile: string;
};

export type SettingsFieldError = {
  message: string;
  path: string;
};

const fallbackProviders: SettingsProvider[] = [
  "deepseek",
  "litellm",
  "openrouter",
];

export function formStateFromConfig(
  config: SettingsConfigSummary,
): SettingsFormState {
  return {
    apiKey: "",
    model: config.llm.model,
    provider: normalizeSettingsProvider(config.llm.provider),
    selectedProfile: config.logging.selectedProfile ?? "",
  };
}

export function normalizeSettingsProvider(value: string): SettingsProvider {
  return isSettingsProvider(value) ? value : "deepseek";
}

export function providerOptions(config: SettingsConfigSummary | null) {
  const options = config?.llm.providerOptions.length
    ? config.llm.providerOptions
    : fallbackProviders.map((provider) => ({
        id: provider,
        label: settingsProviderLabel(provider),
        preferredApiKeyEnvVar: preferredApiKeyEnvVar(provider),
        requiredApiKeyEnvVars: requiredApiKeyEnvVars(provider),
      }));

  return options.map((option) => ({
    ...option,
    label: option.label || settingsProviderLabel(option.id),
  }));
}

export function apiKeyHint(
  provider: SettingsProvider,
  config: SettingsConfigSummary | null,
): string {
  const matched = providerOptions(config).find((option) => option.id === provider);
  const envVars =
    matched?.requiredApiKeyEnvVars.length !== 0
      ? matched?.requiredApiKeyEnvVars
      : requiredApiKeyEnvVars(provider);
  return (envVars ?? requiredApiKeyEnvVars(provider)).join(" or ");
}

export function fieldErrorsFromApiError(
  error: ApiError | null | undefined,
): SettingsFieldError[] {
  const raw = error?.details.fieldErrors;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (!isFieldErrorItem(item)) {
      return [];
    }
    return [
      {
        message: item.message,
        path: item.path,
      },
    ];
  });
}

export function fieldErrorFor(
  errors: SettingsFieldError[],
  path: string,
): string | null {
  return errors.find((error) => error.path === path)?.message ?? null;
}

function isSettingsProvider(value: string): value is SettingsProvider {
  return fallbackProviders.includes(value as SettingsProvider);
}

function preferredApiKeyEnvVar(provider: SettingsProvider): string {
  return requiredApiKeyEnvVars(provider)[0];
}

function requiredApiKeyEnvVars(provider: SettingsProvider): string[] {
  if (provider === "deepseek") {
    return ["DEEPSEEK_API_KEY", "LLM_API_KEY"];
  }
  if (provider === "openrouter") {
    return ["OPENROUTER_API_KEY", "LLM_API_KEY"];
  }
  return ["LLM_API_KEY"];
}

function isFieldErrorItem(
  item: unknown,
): item is { message: string; path: string } {
  return (
    typeof item === "object" &&
    item !== null &&
    typeof (item as { message?: unknown }).message === "string" &&
    typeof (item as { path?: unknown }).path === "string"
  );
}
