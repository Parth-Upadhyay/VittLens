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
  let changeColor = 'text-tx-secondary';
  if (isPositive) changeColor = 'text-semantic-green';
  if (isNegative) changeColor = 'text-semantic-red';

  return (
    <div className="surface-card p-6 space-y-2 font-sans card-interactive">
      <div className="metric-label">{label}</div>
      <div className="flex items-baseline space-x-2">
        <span className="metric-value">{value}</span>
        {change !== undefined && (
          <span className={`text-sm font-normal font-mono ${changeColor}`}>
            {change}
          </span>
        )}
      </div>
      {subtext && <div className="text-[11px] text-tx-tertiary font-sans">{subtext}</div>}
    </div>
  );
};
