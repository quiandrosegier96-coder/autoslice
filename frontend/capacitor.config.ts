import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "be.autoslice.app",
  appName: "AutoSlice",
  webDir: "out",              // required field; unused when server.url is set
  server: {
    // Load the live web app — no static export needed, all routes work normally
    url: "https://autoslice-converter.netlify.app",
    cleartext: false,
  },
};

export default config;
