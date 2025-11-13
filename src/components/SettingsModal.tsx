import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Settings } from "../types";
import {
  discoverModels,
  testModelEndpoint,
  findWorkingEndpoint,
} from "../services/aiService";

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
  const [serverModels, setServerModels] = useState<string[]>([]);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isDiscovering, setIsDiscovering] = useState(false);
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
    if (!isOpen) return;
    (async () => {
      setIsDiscovering(true);
      try {
        const probe = await findWorkingEndpoint(settings.llmEndpoint);
        if (probe) {
          // apply detected endpoint and model immediately and persist
          const updated = {
            ...settings,
            llmEndpoint: probe.endpoint,
            llmModel: (probe.models && probe.models[0]) || settings.llmModel,
          };
          setLocalSettings(updated);
          setServerModels(probe.models || []);
          try {
            onSave(updated);
          } catch {}
          try {
            window.dispatchEvent(
              new CustomEvent("llm-model-applied", {
                detail: { model: updated.llmModel },
              })
            );
          } catch {}
        } else {
          const list = await discoverModels(settings.llmEndpoint);
          setServerModels(list);
        }
        } catch {
        // ignore discovery errors
      }
      setIsDiscovering(false);
    })();
  }, [settings, isOpen, onSave]);

  const handleSelectModel = (m: string) => {
    setLocalSettings({ ...localSettings, llmModel: m });
    try {
      window.dispatchEvent(
        new CustomEvent("llm-model-applied", { detail: { model: m } })
      );
    } catch {}
  };

  const handleDetect = async () => {
    setIsDiscovering(true);
    try {
      const probe = await findWorkingEndpoint(localSettings.llmEndpoint);
      if (probe) {
        const updated = {
          ...localSettings,
          llmEndpoint: probe.endpoint,
          llmModel: (probe.models && probe.models[0]) || localSettings.llmModel,
        };
        setLocalSettings(updated);
        setServerModels(probe.models || []);
          try {
            onSave(updated);
          } catch {}
          try {
            window.dispatchEvent(
              new CustomEvent("llm-model-applied", {
                detail: { model: updated.llmModel },
              })
            );
          } catch {}
      } else {
        const list = await discoverModels(localSettings.llmEndpoint);
        setServerModels(list);
      }
    } catch {
      // ignore
    }
    setIsDiscovering(false);
  };

  const handleTestModel = async () => {
    setTestResult("Testing...");
    try {
      const res = await testModelEndpoint(
        localSettings.llmEndpoint,
        localSettings.llmModel
      );
      if (res.ok)
        setTestResult(
          `OK ${res.status}: ${
            typeof res.body === "string"
              ? res.body
              : JSON.stringify(res.body).slice(0, 200)
          }`
        );
      else
        setTestResult(
          `Error ${res.status}: ${
            typeof res.body === "string"
              ? res.body
              : JSON.stringify(res.body).slice(0, 200)
          }`
        );
    } catch (err: any) {
      setTestResult(`Error: ${String(err?.message || err)}`);
    }
    setTimeout(() => setTestResult(null), 8000);
  };

  const handleSave = () => {
    const s = {
      ...localSettings,
      requireExternalData: requireExternal,
      reviewThreshold,
      modelHeuristicDelta,
    } as Settings;
    if (!saveAsDefault) s.llmModel = settings.llmModel;
    onSave(s);
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
              placeholder="http://localhost:11434"
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
                placeholder="llama3.2:latest"
                className="flex-1 px-4 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
              />
              <button
                onClick={handleTestModel}
                className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600"
              >
                Test Model
              </button>
            </div>
            {testResult && (
              <div className="mt-2 text-sm text-gray-700 dark:text-gray-300 break-words">
                {testResult}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Available On Server
            </label>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDetect}
                disabled={isDiscovering}
                className="px-2 py-1 text-sm bg-gray-100 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600"
              >
                {isDiscovering ? "Detecting..." : "Detect"}
              </button>
              <select
                value={localSettings.llmModel}
                onChange={(e) => handleSelectModel(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700"
              >
                <option value="">-- Select model --</option>
                {serverModels.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <button
                onClick={async () => {
                  if (localSettings.llmModel)
                    await navigator.clipboard.writeText(
                      `ollama pull ${localSettings.llmModel}`
                    );
                }}
                className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600"
              >
                Copy Pull Cmd
              </button>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Detected server endpoint:{" "}
              <span className="font-mono">{localSettings.llmEndpoint}</span>
            </div>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
            <p className="text-xs text-blue-800 dark:text-blue-200">
              💡 Make sure your local LLM server (like Ollama) is running and
              accessible at the endpoint above.
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
