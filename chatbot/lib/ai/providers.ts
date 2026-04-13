import { createAnthropic } from "@ai-sdk/anthropic";
import { createOpenAI } from "@ai-sdk/openai";
import { customProvider } from "ai";
import { isTestEnvironment } from "../constants";
import { titleModel } from "./models";

const anthropicApiKey = process.env.ANTHROPIC_API_KEY;
const openaiApiKey = process.env.OPENAI_API_KEY;

const anthropic = createAnthropic({
  apiKey: anthropicApiKey,
});

const openai = createOpenAI({
  apiKey: openaiApiKey,
});

export const myProvider = isTestEnvironment
  ? (() => {
      const { chatModel, titleModel } = require("./models.mock");
      return customProvider({
        languageModels: {
          "chat-model": chatModel,
          "title-model": titleModel,
        },
      });
    })()
  : null;

export function getLanguageModel(modelId: string) {
  if (isTestEnvironment && myProvider) {
    return myProvider.languageModel(modelId);
  }

  const [provider, modelName] = modelId.includes("/")
    ? modelId.split("/", 2)
    : ["openai", modelId];

  switch (provider) {
    case "anthropic": {
      if (!anthropicApiKey) {
        throw new Error(
          "ANTHROPIC_API_KEY is required to use Anthropic models"
        );
      }
      return anthropic(modelName);
    }
    case "openai": {
      if (!openaiApiKey) {
        throw new Error("OPENAI_API_KEY is required to use OpenAI models");
      }
      return openai(modelName);
    }
    default:
      throw new Error(`Unsupported model provider: ${provider}`);
  }
}

export function getTitleModel() {
  if (isTestEnvironment && myProvider) {
    return myProvider.languageModel("title-model");
  }
  return getLanguageModel(titleModel.id);
}
