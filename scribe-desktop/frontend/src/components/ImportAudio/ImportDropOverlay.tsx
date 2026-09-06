import React from 'react';
import { Upload } from 'lucide-react';
import { getAudioFormatsDisplayList } from '@/constants/audioFormats';

interface ImportDropOverlayProps {
  visible: boolean;
}

export function ImportDropOverlay({ visible }: ImportDropOverlayProps) {
  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm
                 flex items-center justify-center pointer-events-none
                 transition-opacity duration-200"
    >
      <div className="border-2 border-dashed border-primary/50 rounded-2xl
                      p-12 text-center bg-primary/20 shadow-2xl
                      transform scale-100 transition-transform">
        <Upload className="h-16 w-16 text-primary/70 mx-auto mb-4" />
        <p className="text-xl font-medium text-white">Drop audio file to import</p>
        <p className="text-sm text-primary/60 mt-2">{getAudioFormatsDisplayList()}</p>
      </div>
    </div>
  );
}
