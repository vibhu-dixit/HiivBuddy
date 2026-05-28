import type { ReactNode } from "react";

type SplitSectionProps = {
  id?: string;
  eyebrow?: string;
  title?: string;
  description?: string;
  children?: ReactNode;
  visual: ReactNode;
  reverse?: boolean;
  className?: string;
  visualClassName?: string;
};

export function SplitSection({
  id,
  eyebrow,
  title,
  description,
  children,
  visual,
  reverse = false,
  className = "",
  visualClassName = "",
}: SplitSectionProps) {
  const copy = (
    <div className="flex flex-col justify-center text-left">
      {eyebrow ? (
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--accent)]">
          {eyebrow}
        </p>
      ) : null}
      {title ? (
        <h2 className={`font-semibold tracking-tight ${eyebrow ? "mt-3" : ""} text-2xl sm:text-3xl`}>
          {title}
        </h2>
      ) : null}
      {description ? (
        <p className="mt-3 max-w-lg text-base leading-relaxed text-[var(--muted)] [text-wrap:pretty]">
          {description}
        </p>
      ) : null}
      {children ? <div className="mt-6">{children}</div> : null}
    </div>
  );

  const viz = (
    <div className={`flex items-center justify-center ${visualClassName}`}>{visual}</div>
  );

  return (
    <div
      id={id}
      className={`mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 lg:grid-cols-2 lg:gap-16 ${className}`}
    >
      <div className={reverse ? "lg:order-2" : "lg:order-1"}>{copy}</div>
      <div className={reverse ? "lg:order-1" : "lg:order-2"}>{viz}</div>
    </div>
  );
}
