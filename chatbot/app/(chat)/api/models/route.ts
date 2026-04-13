import { getActiveModels, getCapabilities } from "@/lib/ai/models";

export async function GET() {
  const models = getActiveModels();
  const capabilities = getCapabilities();

  return Response.json(
    { models, capabilities },
    {
      headers: {
        "Cache-Control": "no-cache",
      },
    }
  );
}
