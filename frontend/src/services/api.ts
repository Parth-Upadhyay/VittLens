import axios from 'axios';
import {
  ChatRequest,
  ChatResponse,
  ChatMessage,
  ChatThread,
  CompanyDetail,
  HistoricalData,
  NewsArticle,
  PortfolioHolding,
  PortfolioSummary,
  StockQuote,
  User,
  UserPreferences,
  WatchlistItem,
  PortfolioAnalysisResponse,
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Auto-attach Bearer JWT token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response Interceptor: Handle 403 Guest Limit Reached gracefully
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 403) {
      const detail = error.response.data?.detail || '';
      if (detail.includes('Guest query limit reached') || detail.includes('sign in')) {
        window.dispatchEvent(new CustomEvent('guest_limit_reached'));
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// API Endpoints Services
export const AuthService = {
  getMe: async () => {
    const res = await api.get('/auth/me');
    return res.data;
  },
  submitGuestPurpose: async (purpose_of_visit: string) => {
    const res = await api.post('/auth/guest/purpose', { purpose_of_visit });
    return res.data;
  },
};

export const ChatService = {
  sendQuery: async (req: ChatRequest): Promise<ChatResponse> => {
    const res = await api.post('/chat', req);
    return res.data;
  },
  getThreads: async (): Promise<ChatThread[]> => {
    const res = await api.get('/chats');
    return res.data;
  },
  getThreadMessages: async (threadId: string): Promise<ChatMessage[]> => {
    const res = await api.get(`/chats/${threadId}`);
    return res.data;
  },
  deleteThread: async (threadId: string) => {
    const res = await api.delete(`/chats/${threadId}`);
    return res.data;
  },
};

export const MarketService = {
  getQuote: async (symbol: string): Promise<StockQuote> => {
    const res = await api.get(`/market/quote/${symbol}`);
    return res.data;
  },
  getChart: async (symbol: string, period = '1mo'): Promise<HistoricalData> => {
    const res = await api.get(`/market/chart/${symbol}?period=${period}`);
    return res.data;
  },
  getSymbols: async (): Promise<Record<string, string[]>> => {
    const res = await api.get('/market/symbols');
    return res.data;
  },
  deepAnalyze: async (symbol: string): Promise<{ symbol: string; ticker: string; data: Record<string, any> }> => {
    const res = await api.get(`/market/deep-analyze/${symbol}`);
    return res.data;
  },
};

export const CompanyService = {
  getDetail: async (symbol: string): Promise<CompanyDetail> => {
    const res = await api.get(`/company/${symbol}`);
    return res.data;
  },
};

export const NewsService = {
  getNews: async (symbol?: string, limit = 50): Promise<NewsArticle[]> => {
    const url = symbol ? `/news/${symbol}?limit=${limit}` : `/news/ALL?limit=${limit}`;
    const res = await api.get(url);
    return res.data;
  },
};

export const PortfolioService = {
  getSummary: async (): Promise<PortfolioSummary> => {
    const res = await api.get('/portfolio');
    return res.data;
  },
  addHolding: async (symbol: string, quantity: number, avg_price: number): Promise<PortfolioHolding> => {
    const res = await api.post('/portfolio', { symbol, quantity, avg_price });
    return res.data;
  },
  removeHolding: async (holdingId: number) => {
    const res = await api.delete(`/portfolio/${holdingId}`);
    return res.data;
  },
};

export const PreferencesService = {
  getPreferences: async (): Promise<UserPreferences> => {
    const res = await api.get('/preferences');
    return res.data;
  },
  updatePreferences: async (prefs: Partial<UserPreferences>): Promise<UserPreferences> => {
    const res = await api.put('/preferences', prefs);
    return res.data;
  },
};

export const WatchlistService = {
  getWatchlist: async (): Promise<WatchlistItem[]> => {
    const res = await api.get('/watchlist');
    return res.data;
  },
  addSymbol: async (symbol: string): Promise<WatchlistItem> => {
    const res = await api.post('/watchlist', { symbol });
    return res.data;
  },
  removeSymbol: async (symbol: string) => {
    const res = await api.delete(`/watchlist/${symbol}`);
    return res.data;
  },
};

export const PortfolioAnalyzerService = {
  analyzePortfolio: async (file: File): Promise<PortfolioAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post('/portfolio/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  getSavedAnalyses: async (): Promise<PortfolioAnalysisResponse[]> => {
    const res = await api.get('/portfolio/analyses');
    return res.data;
  },
  getAnalysis: async (id: number): Promise<PortfolioAnalysisResponse> => {
    const res = await api.get(`/portfolio/analyses/${id}`);
    return res.data;
  },
  deleteAnalysis: async (id: number) => {
    const res = await api.delete(`/portfolio/analyses/${id}`);
    return res.data;
  },
};
