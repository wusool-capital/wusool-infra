/** `VITE_DATA=live` reads and writes the Toolkit for the Buyers and Sellers pages; anything else is the demo. */
export const isLive = import.meta.env.VITE_DATA === "live";
