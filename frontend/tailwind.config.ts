import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#15171a",
        paper: "#f8f7f3",
        line: "#d8d5ca",
        mint: "#2f8f83",
        plum: "#7d4e8a",
        amber: "#c07a21"
      }
    }
  },
  plugins: []
};

export default config;
