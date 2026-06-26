import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#17211f",
        canopy: "#123a36",
        fern: "#2f6f5f",
        mint: "#6dd9bd",
        sun: "#f4b64a",
        clay: "#bf6b4d",
        cloud: "#f7fbf9",
      },
      boxShadow: {
        panel: "0 18px 60px rgba(23, 33, 31, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
