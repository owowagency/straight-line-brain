export function register() {
  // OpenTelemetry is only available when deployed on Vercel
  if (process.env.VERCEL) {
    import("@vercel/otel").then(({ registerOTel }) => {
      registerOTel({ serviceName: "chatbot" });
    });
  }
}
