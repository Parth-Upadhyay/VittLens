import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAppStore } from '../../store/useAppStore';
import {
  Plus,
  MessageSquare,
  Trash2,
  X,
  Search,
  LayoutDashboard,
  Newspaper,
  PieChart,
  Settings,
  Microscope,
  FileText,
} from 'lucide-react';
import { ChatService } from '../../services/api';
import { ChatThread } from '../../types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { threads, activeThreadId, setActiveThreadId, fetchThreads, user } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');

  const navLinks = [
    { path: '/chat', label: 'Chat', icon: MessageSquare },
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/news', label: 'News', icon: Newspaper },
    { path: '/portfolio-analyzer', label: 'Portfolio Analyzer', icon: PieChart },
    { path: '/deep-analyze', label: 'Deep Analyze', icon: Microscope },
    { path: '/filing-agent', label: 'Filing Agent', icon: FileText },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  const handleNewChat = () => {
    setActiveThreadId(null);
    navigate('/chat');
    onClose();
  };

  const handleSelectThread = (id: string) => {
    setActiveThreadId(id);
    navigate('/chat');
    onClose();
  };

  const handleDeleteThread = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await ChatService.deleteThread(id);
      if (activeThreadId === id) {
        setActiveThreadId(null);
      }
      await fetchThreads();
    } catch (err) {
      console.error('Failed to delete thread:', err);
    }
  };

  // Filter threads by search query
  const filteredThreads = threads.filter((t) =>
    t.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group threads by recency
  const groupThreadsByRecency = (list: ChatThread[]) => {
    const now = new Date();
    const todayMs = 24 * 60 * 60 * 1000;
    const sevenDaysMs = 7 * todayMs;
    const thirtyDaysMs = 30 * todayMs;

    const groups: { label: string; items: ChatThread[] }[] = [
      { label: 'Today', items: [] },
      { label: 'Previous 7 days', items: [] },
      { label: 'Previous 30 days', items: [] },
      { label: 'Older', items: [] },
    ];

    list.forEach((thread) => {
      const threadDate = new Date(thread.updated_at || thread.created_at || Date.now());
      const diff = now.getTime() - threadDate.getTime();

      if (diff <= todayMs) {
        groups[0].items.push(thread);
      } else if (diff <= sevenDaysMs) {
        groups[1].items.push(thread);
      } else if (diff <= thirtyDaysMs) {
        groups[2].items.push(thread);
      } else {
        groups[3].items.push(thread);
      }
    });

    return groups.filter((g) => g.items.length > 0);
  };

  const recencyGroups = groupThreadsByRecency(filteredThreads);

  const getInitials = () => {
    if (user?.name) {
      const parts = user.name.split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return user.name.slice(0, 2).toUpperCase();
    }
    return 'PU';
  };

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/70 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Fixed Sidebar Container - Never scrolls down when main content scrolls */}
      <aside
        className={`fixed md:static top-14 bottom-0 left-0 z-40 w-64 bg-[#0D1912] border-r border-hairline flex flex-col h-[calc(100vh-3.5rem)] flex-shrink-0 transition-transform duration-200 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Top App Navigation Menu */}
        <div className="p-3 border-b border-hairline space-y-1">
          <div className="flex items-center justify-between md:hidden mb-2">
            <span className="text-xs font-medium text-cream uppercase tracking-wider">Navigation</span>
            <button onClick={onClose} className="p-1 text-cream-muted hover:text-cream">
              <X className="w-4 h-4" />
            </button>
          </div>

          <nav className="space-y-0.5">
            {navLinks.map((item) => {
              const Icon = item.icon;
              const active = location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={onClose}
                  className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-sans transition-colors ${
                    active
                      ? 'bg-[#14251B] text-cream font-medium border border-hairline shadow-sm'
                      : 'text-cream-muted hover:text-cream hover:bg-[#14251B]/50'
                  }`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* New Chat & Search Header */}
        <div className="p-3 border-b border-hairline space-y-2">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center space-x-2 bg-[#14251B] hover:bg-[#1A2E22] border border-hairline text-cream text-xs font-sans font-medium py-2 px-3 rounded-lg transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4 text-accent" />
            <span>New Chat</span>
          </button>

          {/* Search Input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-cream-muted absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats..."
              className="w-full bg-[#060E0A] border border-hairline rounded-md pl-8 pr-3 py-1.5 text-xs text-cream placeholder-cream-dim focus:outline-none focus:border-accent/60 transition-colors font-sans"
            />
          </div>
        </div>

        {/* Thread History List with Internal Scroll */}
        <div className="flex-1 overflow-y-auto p-2 space-y-3 min-h-0">
          {threads.length === 0 ? (
            <div className="px-3 py-8 text-center text-xs text-cream-muted font-sans">
              No recent chats.
            </div>
          ) : filteredThreads.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-cream-muted font-sans">
              No chats matching "{searchQuery}".
            </div>
          ) : (
            recencyGroups.map((group) => (
              <div key={group.label} className="space-y-1">
                <div className="px-2 py-1 text-[10px] font-sans font-medium text-cream-dim uppercase tracking-wider">
                  {group.label}
                </div>

                {group.items.map((t) => {
                  const active = activeThreadId === t.id;
                  return (
                    <div
                      key={t.id}
                      onClick={() => handleSelectThread(t.id)}
                      className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-xs transition-colors font-sans ${
                        active
                          ? 'bg-[#14251B] text-cream font-medium border border-hairline shadow-sm'
                          : 'text-cream-muted hover:text-cream hover:bg-[#14251B]/50'
                      }`}
                    >
                      <div className="flex items-center space-x-2 truncate pr-2">
                        <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-cream-dim group-hover:text-accent" />
                        <span className="truncate">{t.title}</span>
                      </div>
                      <button
                        onClick={(e) => handleDeleteThread(e, t.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-cream-dim hover:text-semantic-red transition-opacity"
                        title="Delete thread"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Pinned User Account Footer */}
        <div className="p-3 border-t border-hairline bg-[#060E0A]/60 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center space-x-2.5 overflow-hidden">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name || 'User'}
                className="w-7 h-7 rounded-full border border-hairline flex-shrink-0"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-[#14251B] border border-hairline flex items-center justify-center text-accent font-sans font-medium text-xs flex-shrink-0">
                {getInitials()}
              </div>
            )}

            <div className="min-w-0 flex-1">
              <div className="text-xs font-sans font-medium text-cream truncate">
                {user?.name || 'Parth Upadhyay'}
              </div>
              <div className="text-[10px] font-sans text-cream-muted truncate">
                {user ? 'Pro Analyst' : 'Free Guest Tier'}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
