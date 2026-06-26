// @ts-check
import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
  // Set this to the deployed origin so canonical URLs and OG tags resolve.
  site: "https://techpeeps.example.com",
  // Static output is the default; spelled out here for clarity.
  output: "static",
});
