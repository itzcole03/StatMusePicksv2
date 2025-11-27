import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Settings } from "../types";
import {
  getSettings as getAutoSettings,
  updateSettings as updateAutoSettings,
  startAutoRefresh,
  stopAutoRefresh,
} from "../services/autoRefreshService";

interface SettingsModalProps {
  isOpen: boolean;
  settings: Settings;
  onClose: () => void;
  onSave: (_settings: Settings) => void;
}

export default function SettingsModal({
  isOpen,
  settings: _settings,
  onClose,
  onSave,
}: SettingsModalProps) {
  // map underscore-prefixed prop to `settings` local name for readability
  const settings = _settings;
  const [localSettings, setLocalSettings] = useState<Settings>(settings);

  const [saveAsDefault, setSaveAsDefault] = useState(true);
  const [requireExternal, setRequireExternal] = useState<boolean>(
    !!settings.requireExternalData
  );
  const [reviewThreshold, setReviewThreshold] = useState<number>(
    settings.reviewThreshold ?? 60
  );
  const [modelHeuristicDelta, setModelHeuristicDelta] = useState<number>(
    settings.modelHeuristicDelta ?? 20
  );

  useEffect(() => {
    setLocalSettings(settings);
    setReviewThreshold(settings.reviewThreshold ?? 60);
    setModelHeuristicDelta(settings.modelHeuristicDelta ?? 20);
    // load auto-refresh settings
    try {
      const s = getAutoSettings();
      setAutoEnabled(!!s.enabled);
      setAutoInterval(s.intervalMinutes || 60);
    } catch {}
  }, [settings, isOpen, onSave]);

  const [autoEnabled, setAutoEnabled] = useState(false);
  const [autoInterval, setAutoInterval] = useState<number>(60);

  // Discovery and direct local LLM testing disabled in UI. Use the backend proxy instead.

  const handleSave = () => {
    const s = {
      ...localSettings,
      requireExternalData: requireExternal,
      reviewThreshold,
      modelHeuristicDelta,
    } as Settings;
    if (!saveAsDefault) s.llmModel = settings.llmModel;
    onSave(s);
    // persist auto-refresh settings into the autoRefresh service
    try {
      updateAutoSettings({
        enabled: autoEnabled,
        intervalMinutes: autoInterval,
      });
      if (autoEnabled) startAutoRefresh();
      else stopAutoRefresh();
    } catch {}
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg max-w-md w-full mx-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-semibold">Settings</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              API Endpoint
            </label>
            <input
              type="text"
              value={localSettings.llmEndpoint}
              onChange={(e) =>
                setLocalSettings({
                  ...localSettings,
                  llmEndpoint: e.target.value,
                })
              }
              placeholder="(leave blank to use backend proxy)"
              className="w-full px-4 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:ring-2 focus:ring-[#5D5CDE] focus:border-transparent"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Base URL or full OpenAI-compatible endpoint (detection will prefer
              generation endpoints)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Model Name</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={localSettings.llmModel}
                onChange={(e) =>
                  setLocalSettings({
                    ...localSettings,
                    llmModel: e.target.value,
                  })
                }
                placeholder="(configured via backend proxy)"
                className="flex-1 px-4 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              The frontend no longer connects directly to local LLM servers.
              Configure and run an LLM on the server-side and use the backend
              proxy (recommended) to handle model selection and streaming.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="saveDefault"
              type="checkbox"
              checked={saveAsDefault}
              onChange={(e) => setSaveAsDefault(e.target.checked)}
              className="w-4 h-4"
            />
            <label
              htmlFor="saveDefault"
              className="text-sm text-gray-600 dark:text-gray-300"
            >
              Save selected model as default when saving settings
            </label>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="requireExternal"
              type="checkbox"
              checked={requireExternal}
              onChange={(e) => setRequireExternal(e.target.checked)}
              className="w-4 h-4"
            />
            <label
              htmlFor="requireExternal"
              className="text-sm text-gray-600 dark:text-gray-300"
            >
              Require external numeric data for analysis
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">
                Review Threshold (%)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={reviewThreshold}
                onChange={(e) => setReviewThreshold(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700"
              />
              <p className="text-xs text-gray-500 mt-1">
                If model vs heuristic agreement is below this percent, flag for
                review.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Model-Heuristic Delta
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={modelHeuristicDelta}
                onChange={(e) => setModelHeuristicDelta(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700"
              />
              <p className="text-xs text-gray-500 mt-1">
                Allowed difference (0-100) before marking strong disagreement.
              </p>
            </div>
          </div>

          <div className="border-t pt-4">
            <h4 className="font-semibold mb-2">Auto Refresh</h4>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="checkbox"
                checked={autoEnabled}
                onChange={(e) => setAutoEnabled(e.target.checked)}
                className="w-4 h-4"
              />
              <label className="text-sm">Enable Auto Refresh</label>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <label className="text-sm">Interval (min)</label>
              <input
                type="number"
                min={1}
                value={autoInterval}
                onChange={(e) => setAutoInterval(Number(e.target.value))}
                className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-[#5D5CDE] focus:border-transparent"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-[#5D5CDE] text-white hover:bg-[#4a49c9] rounded transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
