import { create } from 'zustand';
import { ChatThread, GuestSession, User, UserPreferences, WatchlistItem } from '../types';
import { AuthService, ChatService, PreferencesService, WatchlistService, MarketService } from '../services/api';

interface AppState {
  user: User | null;
  guestSession: GuestSession | null;
  queriesRemaining: number;
  activeThreadId: string | null;
  threads: ChatThread[];
  watchlist: WatchlistItem[];
  preferences: UserPreferences;
  marketSymbols: Record<string, string[]>;
  isGuestLimitModalOpen: boolean;
  isGuestPurposeModalOpen: boolean;
  isInitializing: boolean;

  // Actions
  initSession: () => Promise<void>;
  setActiveThreadId: (id: string | null) => void;
  fetchThreads: () => Promise<void>;
  fetchWatchlist: () => Promise<void>;
  fetchPreferences: () => Promise<void>;
  setPreferences: (prefs: Partial<UserPreferences>) => void;
  fetchMarketSymbols: () => Promise<void>;
  setQueriesRemaining: (count: number) => void;
  setGuestLimitModalOpen: (open: boolean) => void;
  setGuestPurposeModalOpen: (open: boolean) => void;
  logout: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  user: null,
  guestSession: null,
  queriesRemaining: -1,
  activeThreadId: null,
  threads: [],
  watchlist: [],
  preferences: {
    answer_style: 'Detailed',
    default_symbols: ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK'],
    theme: (() => {
      const hasToken = !!localStorage.getItem('auth_token');
      if (!hasToken) {
        return (sessionStorage.getItem('vittlens_theme_guest') as any) || 'Light';
      }
      return (localStorage.getItem('vittlens_theme') as any) || 'Light';
    })(),
  },
  marketSymbols: {},
  isGuestLimitModalOpen: false,
  isGuestPurposeModalOpen: false,
  isInitializing: true,

  initSession: async () => {
    set({ isInitializing: true });
    let success = false;
    let attempts = 0;
    while (!success) {
      try {
        const data = await AuthService.getMe();
        if (data.provider === 'google') {
          set({ user: data, guestSession: null, queriesRemaining: -1 });
        } else {
          set({
            user: null,
            guestSession: data,
            queriesRemaining: data.queries_remaining ?? -1,
          });

          // Prompt guest for purpose of visit if missing
          if (!data.purpose_of_visit) {
            set({ isGuestPurposeModalOpen: true });
          }
        }
        success = true;
      } catch (e: any) {
        const isNetworkOrServerError = !e.response || e.response.status >= 500;
        if (isNetworkOrServerError) {
          attempts++;
          console.log(`Server not ready, retrying in 2s (attempt ${attempts})...`);
          await new Promise((resolve) => setTimeout(resolve, 2000));
        } else {
          console.error('Failed to init session (server is up):', e);
          success = true;
        }
      }
    }

    try {
      await get().fetchThreads();
      await get().fetchPreferences();
      await get().fetchWatchlist();
      await get().fetchMarketSymbols();
    } catch (err) {
      console.error('Failed to fetch post-init resources:', err);
    } finally {
      set({ isInitializing: false });
    }
  },

  setActiveThreadId: (id: string | null) => set({ activeThreadId: id }),

  fetchThreads: async () => {
    try {
      const threads = await ChatService.getThreads();
      set({ threads });
    } catch (e) {
      console.error('Failed to fetch threads:', e);
    }
  },

  fetchWatchlist: async () => {
    const isGuest = get().user === null;
    if (isGuest) {
      try {
        const stored = sessionStorage.getItem('vittlens_guest_watchlist');
        const list = stored ? JSON.parse(stored) : [];
        set({ watchlist: list });
      } catch (e) {
        console.error('Failed to parse guest watchlist from sessionStorage:', e);
      }
      return;
    }

    try {
      const watchlist = await WatchlistService.getWatchlist();
      set({ watchlist });
    } catch (e) {
      console.error('Failed to fetch watchlist:', e);
    }
  },

  fetchPreferences: async () => {
    try {
      const preferences = await PreferencesService.getPreferences();
      set({ preferences });
    } catch (e) {
      console.error('Failed to fetch preferences:', e);
    }
  },

  setPreferences: (prefs) => set((state) => ({ preferences: { ...state.preferences, ...prefs } })),

  fetchMarketSymbols: async () => {
    try {
      const marketSymbols = await MarketService.getSymbols();
      set({ marketSymbols });
    } catch (e) {
      console.error('Failed to fetch market symbols:', e);
    }
  },

  setQueriesRemaining: (count: number) => set({ queriesRemaining: count }),

  setGuestLimitModalOpen: (open: boolean) => set({ isGuestLimitModalOpen: open }),

  setGuestPurposeModalOpen: (open: boolean) => set({ isGuestPurposeModalOpen: open }),

  logout: () => {
    localStorage.removeItem('auth_token');
    set({ user: null, guestSession: null, queriesRemaining: -1, activeThreadId: null, threads: [] });
    window.location.href = '/login';
  },
}));
