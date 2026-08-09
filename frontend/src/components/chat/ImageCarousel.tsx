import React, { useState } from 'react';
import { Image as ImageIcon, X } from 'lucide-react';

interface ImageCarouselProps {
  images?: string[];
}

export const ImageCarousel: React.FC<ImageCarouselProps> = ({ images }) => {
  const [activeImage, setActiveImage] = useState<string | null>(null);

  if (!images || images.length === 0) return null;

  return (
    <div className="space-y-2 pt-2 font-sans">
      <div className="text-xs text-cream-muted font-normal flex items-center space-x-1">
        <ImageIcon className="w-3.5 h-3.5 text-accent" />
        <span>Filing Visual Charts & Figures ({images.length})</span>
      </div>

      <div className="flex space-x-3 overflow-x-auto pb-2 scrollbar-thin">
        {images.map((url, idx) => (
          <div
            key={idx}
            onClick={() => setActiveImage(url)}
            className="flex-shrink-0 w-48 h-32 bg-[#0D1912] border border-hairline rounded-lg overflow-hidden cursor-pointer group hover:border-accent transition-colors relative"
          >
            <img
              src={url}
              alt={`SEC Visual Chart ${idx + 1}`}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
              onError={(e) => {
                // Fallback placeholder if image load fails
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center text-cream text-xs font-medium transition-opacity">
              View Chart
            </div>
          </div>
        ))}
      </div>

      {/* Modal Image Zoom Preview */}
      {activeImage && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
          onClick={() => setActiveImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] bg-[#0D1912] border border-hairline rounded-xl p-2 overflow-hidden shadow-2xl">
            <button
              onClick={() => setActiveImage(null)}
              className="absolute top-3 right-3 p-1.5 bg-black/60 rounded-full text-cream-muted hover:text-cream transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <img
              src={activeImage}
              alt="SEC Visual Chart Preview"
              className="w-full h-full object-contain rounded-lg max-h-[85vh]"
            />
          </div>
        </div>
      )}
    </div>
  );
};
