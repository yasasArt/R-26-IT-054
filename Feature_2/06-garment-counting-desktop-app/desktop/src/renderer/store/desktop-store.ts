import { create } from "zustand";

export type NavigationItem = "setup" | "session" | "dashboard" | "analytics" | "settings";

interface DesktopStore {
  activeNavigation: NavigationItem;
  refreshing: boolean;
  setActiveNavigation: (item: NavigationItem) => void;
  setRefreshing: (refreshing: boolean) => void;
}

export const useDesktopStore = create<DesktopStore>((set) => ({
  activeNavigation: "setup",
  refreshing: false,
  setActiveNavigation: (activeNavigation) => set({ activeNavigation }),
  setRefreshing: (refreshing) => set({ refreshing }),
}));
