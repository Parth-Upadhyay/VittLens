import { create } from 'zustand';
import { ChatThread, GuestSession, User, UserPreferences, WatchlistItem } from '../types';
import { AuthService, ChatService, PreferencesService, WatchlistService } from '../services/api';

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

  // Actions
  initSession: () => Promise<void>;
  setActiveThreadId: (id: string | null) => void;
  fetchThreads: () => Promise<void>;
  fetchWatchlist: () => Promise<void>;
  fetchPreferences: () => Promise<void>;
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
    theme: 'Dark',
  },
  marketSymbols: {},
  isGuestLimitModalOpen: false,
  isGuestPurposeModalOpen: false,

  initSession: async () => {
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

      await get().fetchThreads();
      await get().fetchPreferences();
      await get().fetchWatchlist();
      await get().fetchMarketSymbols();
    } catch (e) {
      console.error('Failed to init session:', e);
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

  fetchMarketSymbols: async () => {
    try {
      const { MarketService } = await import('../services/api');
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
