
import { registerOTel } from "@vercel/otel";

export function register() {
  registerOTel({
    serviceName: "docuai-frontend",
  });
}
