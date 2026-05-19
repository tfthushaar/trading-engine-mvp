import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gray: {
          850: "#1a2035",
          950: "#0d1117",
        },
      },
    },
  },
  plugins: [],
};

export default config;
