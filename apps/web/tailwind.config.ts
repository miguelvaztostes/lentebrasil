import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#102333",
        teal: "#119E9C",
        gold: "#E3AF42",
        paper: "#F5F3ED",
      },
      boxShadow: {
        card: "0 16px 50px rgba(16,35,51,0.08)",
      },
    },
  },
  plugins: [],
} satisfies Config;

