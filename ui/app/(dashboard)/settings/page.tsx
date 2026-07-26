"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Settings, Save, AlertCircle, CheckCircle, Sliders } from "lucide-react";

interface LLMSettings {
  llm_backend: string;
  ollama_host: string;
  ollama_model: string;
  openai_api_base: string;
  openai_api_key: string;
  openai_model: string;
  anthropic_api_key: string;
  anthropic_model: string;
}

export default function SettingsPage() {
  const { data: settingsData, error: loadError, mutate } = useSWR<LLMSettings>(
    "/api/proxy/settings",
    swrFetcher
  );

  const [settings, setSettings] = useState<LLMSettings>({
    llm_backend: "template",
    ollama_host: "http://localhost:11434",
    ollama_model: "llama3.1",
    openai_api_base: "",
    openai_api_key: "",
    openai_model: "gpt-4o-mini",
    anthropic_api_key: "",
    anthropic_model: "claude-3-5-sonnet-20241022",
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (settingsData) {
      setSettings(settingsData);
    }
  }, [settingsData]);

  const handleChange = (key: keyof LLMSettings, val: string) => {
    setSettings((prev) => ({ ...prev, [key]: val }));
  };

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      const res = await fetch("/api/proxy/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(settings),
      });

      if (!res.ok) {
        throw new Error(`Failed to save settings: ${res.statusText}`);
      }

      setSuccess("Settings successfully saved and applied!");
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Global Settings</h2>
        <p className="text-sm text-fg-muted">
          Configure active LLM models, API keys, and connection hosts for creative director agents.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-xs text-destructive flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="p-3 bg-success/10 border border-success/20 rounded-md text-xs text-success flex items-start gap-2">
            <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{success}</span>
          </div>
        )}

        {loadError && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-xs text-destructive">
            Failed to load settings. Please verify the API server connection.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Select Card */}
          <Card className="md:col-span-1">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Settings className="h-5 w-5 text-brand-500" />
                Active Backend
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Select LLM Provider</Label>
                <Select
                  value={settings.llm_backend}
                  onChange={(e) => handleChange("llm_backend", e.target.value)}
                >
                  <option value="template">Mock / Offline Template</option>
                  <option value="ollama">Ollama (Local LLM)</option>
                  <option value="openai">OpenAI / LM Studio (REST)</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                </Select>
              </div>

              <div className="text-xs text-fg-muted bg-bg-muted/30 p-3 rounded border border-border">
                {settings.llm_backend === "ollama" && (
                  <p>Using Ollama backend. Ensures all creative instructions and storyboard parsing are executed entirely on your local GPU.</p>
                )}
                {settings.llm_backend === "openai" && (
                  <p>Using OpenAI-compatible REST API. Can be linked to public OpenAI endpoints or local providers like LM Studio.</p>
                )}
                {settings.llm_backend === "anthropic" && (
                  <p>Using Anthropic Claude models. Requires an Anthropic API Key and an active internet connection.</p>
                )}
                {settings.llm_backend === "template" && (
                  <p>Using offline mock template. Prompts are echoed back immediately. No GPU or API keys needed.</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Configuration Parameters Card */}
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Sliders className="h-5 w-5 text-brand-500" />
                Backend Configuration
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Ollama settings */}
              {settings.llm_backend === "ollama" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label>Ollama Host Connection URL</Label>
                    <Input
                      value={settings.ollama_host}
                      onChange={(e) => handleChange("ollama_host", e.target.value)}
                      placeholder="e.g. http://localhost:11434"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Ollama Model Name</Label>
                    <Input
                      value={settings.ollama_model}
                      onChange={(e) => handleChange("ollama_model", e.target.value)}
                      placeholder="e.g. llama3.1, mistral, gemma2"
                    />
                    <p className="text-xs text-fg-muted mt-1">
                      Ensure you have run <code>ollama pull &lt;model-name&gt;</code> in your terminal before using it.
                    </p>
                  </div>
                </div>
              )}

              {/* OpenAI / LM Studio settings */}
              {settings.llm_backend === "openai" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label>OpenAI API Base URL (Optional for Local LM Studio)</Label>
                    <Input
                      value={settings.openai_api_base}
                      onChange={(e) => handleChange("openai_api_base", e.target.value)}
                      placeholder="e.g. http://localhost:1234/v1 for LM Studio"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>OpenAI API Key (Leave blank for LM Studio)</Label>
                    <Input
                      type="password"
                      value={settings.openai_api_key}
                      onChange={(e) => handleChange("openai_api_key", e.target.value)}
                      placeholder="sk-..."
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>OpenAI Model Name</Label>
                    <Input
                      value={settings.openai_model}
                      onChange={(e) => handleChange("openai_model", e.target.value)}
                      placeholder="e.g. gpt-4o-mini or your local model string"
                    />
                  </div>
                </div>
              )}

              {/* Anthropic settings */}
              {settings.llm_backend === "anthropic" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label>Anthropic API Key</Label>
                    <Input
                      type="password"
                      value={settings.anthropic_api_key}
                      onChange={(e) => handleChange("anthropic_api_key", e.target.value)}
                      placeholder="sk-ant-..."
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Claude Model Name</Label>
                    <Input
                      value={settings.anthropic_model}
                      onChange={(e) => handleChange("anthropic_model", e.target.value)}
                      placeholder="e.g. claude-3-5-sonnet-20241022"
                    />
                  </div>
                </div>
              )}

              {/* Template settings */}
              {settings.llm_backend === "template" && (
                <div className="text-center py-12 text-fg-muted">
                  <Badge variant="brand" className="mb-2">Offline Mock Mode</Badge>
                  <p className="text-sm">No additional settings are needed for the Template backend.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="flex justify-end">
          <Button type="submit" disabled={saving}>
            <Save className="h-4 w-4 mr-2" />
            {saving ? "Saving Changes..." : "Save Settings"}
          </Button>
        </div>
      </form>
    </div>
  );
}
