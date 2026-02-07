import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    // Use loopback to avoid network/proxy flakiness in CI.
    baseUrl: "http://127.0.0.1:3000",
    video: false,
    screenshotOnRunFailure: true,
    specPattern: "cypress/e2e/**/*.cy.{ts,tsx,js,jsx}",
    supportFile: "cypress/support/e2e.ts",
  },
});
