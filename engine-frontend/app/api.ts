// Routes import data from here. VITE_DATA=live swaps the Phase 1 functions for Toolkit versions.
import * as live from "./live/api";
import * as demo from "./demo/api";
import { isLive } from "./lib/data-mode";

export * from "./demo/api";

export const getBuyersUniverse: typeof demo.getBuyersUniverse = isLive ? live.getBuyersUniverse : demo.getBuyersUniverse;
export const addBuyer: typeof demo.addBuyer = isLive ? live.addBuyer : demo.addBuyer;
export const updateBuyer: typeof demo.updateBuyer = isLive ? live.updateBuyer : demo.updateBuyer;
export const getSellersUniverse: typeof demo.getSellersUniverse = isLive ? live.getSellersUniverse : demo.getSellersUniverse;
export const addSeller: typeof demo.addSeller = isLive ? live.addSeller : demo.addSeller;
export const updateSeller: typeof demo.updateSeller = isLive ? live.updateSeller : demo.updateSeller;
export const getCurrentUser: typeof demo.getCurrentUser = isLive ? live.getCurrentUser : demo.getCurrentUser;
