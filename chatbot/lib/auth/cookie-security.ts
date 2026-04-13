export function shouldUseSecureCookies(
  request: Pick<Request, "headers" | "url">
): boolean {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedProto) {
    const firstProto = forwardedProto.split(",")[0]?.trim().toLowerCase();
    return firstProto === "https";
  }

  try {
    return new URL(request.url).protocol === "https:";
  } catch {
    return false;
  }
}
