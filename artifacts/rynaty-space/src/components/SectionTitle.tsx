interface SectionTitleProps {
  label: string;
  title: string;
  highlight?: string;
  subtitle?: string;
}

export default function SectionTitle({ label, title, highlight, subtitle }: SectionTitleProps) {
  return (
    <div className="text-center mb-14">
      <span className="inline-block text-[#22c55e] text-sm font-semibold tracking-widest uppercase mb-3 border border-[#22c55e]/30 bg-[#22c55e]/10 px-4 py-1.5 rounded-full">
        {label}
      </span>
      <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
        {title}{" "}
        {highlight && (
          <span
            style={{
              background: "linear-gradient(135deg, #22c55e 0%, #4ade80 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {highlight}
          </span>
        )}
      </h2>
      {subtitle && (
        <p className="text-slate-400 text-base lg:text-lg max-w-2xl mx-auto">{subtitle}</p>
      )}
    </div>
  );
}
