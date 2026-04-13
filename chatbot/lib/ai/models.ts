export const titleModel = {
  id: "openai/gpt-5.4-mini",
  name: "GPT 5.4 Mini",
  provider: "openai",
  description: "Fast model for title generation",
};

export type ModelCapabilities = {
  tools: boolean;
  vision: boolean;
  reasoning: boolean;
};

export type ChatModel = {
  id: string;
  name: string;
  provider: string;
  description: string;
  gatewayOrder?: string[];
  reasoningEffort?: "none" | "minimal" | "low" | "medium" | "high";
};

const curatedChatModels: ChatModel[] = [
  {
    id: "openai/gpt-5.4-mini",
    name: "GPT 5.4 Mini",
    provider: "openai",
    description: "Fast, capable, and cost-efficient",
  },
  {
    id: "openai/gpt-5.4",
    name: "GPT 5.4",
    provider: "openai",
    description: "Highest quality for complex tasks",
  },
  {
    id: "anthropic/claude-sonnet-4-6",
    name: "Claude Sonnet 4.6",
    provider: "anthropic",
    description: "Fast and intelligent",
  },
  {
    id: "anthropic/claude-opus-4-6",
    name: "Claude Opus 4.6",
    provider: "anthropic",
    description: "Most capable model for complex tasks",
  },
];

const hasOpenAIKey = Boolean(process.env.OPENAI_API_KEY);
const hasAnthropicKey = Boolean(process.env.ANTHROPIC_API_KEY);

function isModelEnabledByKey(model: ChatModel) {
  if (model.provider === "openai") {
    return hasOpenAIKey;
  }
  if (model.provider === "anthropic") {
    return hasAnthropicKey;
  }
  return true;
}

export const chatModels: ChatModel[] =
  hasOpenAIKey || hasAnthropicKey
    ? curatedChatModels.filter(isModelEnabledByKey)
    : curatedChatModels;

export const DEFAULT_CHAT_MODEL =
  chatModels.find((m) => m.id === "openai/gpt-5.4-mini")?.id ??
  chatModels[0].id;

// Known capabilities for our curated models (no Gateway fetch needed)
const knownCapabilities: Record<string, ModelCapabilities> = {
  "openai/gpt-5.4-mini": { tools: true, vision: true, reasoning: false },
  "openai/gpt-5.4": { tools: true, vision: true, reasoning: true },
  "anthropic/claude-sonnet-4-6": { tools: true, vision: true, reasoning: true },
  "anthropic/claude-opus-4-6": { tools: true, vision: true, reasoning: true },
};

export function getCapabilities(): Record<string, ModelCapabilities> {
  return Object.fromEntries(
    getActiveModels().map((model) => [
      model.id,
      knownCapabilities[model.id] ?? {
        tools: false,
        vision: false,
        reasoning: false,
      },
    ])
  );
}

export const isDemo = process.env.IS_DEMO === "1";

export function getActiveModels(): ChatModel[] {
  return chatModels;
}

export const allowedModelIds = new Set(chatModels.map((m) => m.id));

export const modelsByProvider = chatModels.reduce(
  (acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  },
  {} as Record<string, ChatModel[]>
);
