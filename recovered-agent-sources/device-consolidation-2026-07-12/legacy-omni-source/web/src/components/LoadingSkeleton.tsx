import type { FC } from "react";

type SkeletonVariant = "card" | "text" | "list";

interface LoadingSkeletonProps {
  variant: SkeletonVariant;
  count?: number;
  className?: string;
}

const LoadingSkeleton: FC<LoadingSkeletonProps> = ({
  variant,
  count = 3,
  className = "",
}) => {
  const baseClasses = 'animate-pulse bg-white/[0.04]';

  const renderSkeleton = () => {
    switch (variant) {
      case 'card':
        return (
          <div
            className={`${baseClasses} rounded-xl border border-white/5 ${className}`}
          />
        );
      case 'text':
        return (
          <div className="space-y-2">
            <div className={`${baseClasses} h-4 rounded w-3/4 ${className}`} />
            <div className={`${baseClasses} h-4 rounded w-full ${className}`} />
            <div className={`${baseClasses} h-4 rounded w-5/6 ${className}`} />
          </div>
        );
      case 'list':
        return (
          <div className={`space-y-3 ${className}`}>
            {Array.from({ length: count }).map((_, i) => {
                const widthClass = ['w-full', 'w-11/12', 'w-10/12'][i % 3];
                return (
                    <div key={i} className={`${baseClasses} h-6 rounded ${widthClass}`} />
                );
            })}
          </div>
        );
      default:
        return null;
    }
  };

  return <>{renderSkeleton()}</>;
};

export default LoadingSkeleton;
