import React from 'react';

interface AgentChipProps {
  name: string;
}

export const AgentChip: React.FC<AgentChipProps> = ({ name }) => {
  // Normalize display name: strip 'Agent' suffix if present
  const cleanName = name.replace(/Agent$/i, '').trim();

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-sans font-normal tracking-wider uppercase bg-[#14251B] text-cream border border-hairline select-none shadow-sm">
      {cleanName}
    </span>
  );
};
