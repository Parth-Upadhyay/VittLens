import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: string | number;
  isPositive?: boolean;
  isNegative?: boolean;
  subtext?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  change,
  isPositive,
  isNegative,
  subtext,
}) => {
  let changeColor = 'text-cream-muted';
  if (isPositive) changeColor = 'text-semantic-green';
  if (isNegative) changeColor = 'text-semantic-red';

  return (
    <div className="bg-[#0D1912] border border-hairline rounded-lg p-4 space-y-1 font-sans">
      <div className="text-xs text-cream-muted font-normal uppercase tracking-wider">{label}</div>
      <div className="flex items-baseline space-x-2">
        <span className="text-xl font-medium text-cream tracking-tight font-mono tabular-nums">{value}</span>
        {change !== undefined && (
          <span className={`text-xs font-normal font-mono tabular-nums ${changeColor}`}>
            {change}
          </span>
        )}
      </div>
      {subtext && <div className="text-[11px] text-cream-dim font-sans">{subtext}</div>}
    </div>
  );
};
