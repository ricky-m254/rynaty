import { Building2, Globe, Zap } from "lucide-react";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";
import { assetUrl } from "@/lib/assets";

const pillars = [
  {
    icon: Building2,
    title: "Smart School Ecosystem",
    description: "Creating fully integrated digital ecosystems where every aspect of school life — from learning to administration — is connected, automated and intelligent.",
    image: "assets/vision-smart-school.png",
    stat: "500+",
    statLabel: "Schools Empowered",
  },
  {
    icon: Globe,
    title: "Expansion Across Africa",
    description: "Our vision is pan-African. We are scaling our technology footprint across East, West and Southern Africa, bringing world-class EdTech to every classroom.",
    image: "assets/vision-africa.png",
    stat: "10+",
    statLabel: "Countries Targeted",
  },
  {
    icon: Zap,
    title: "Innovation in EdTech",
    description: "Continuously pushing the boundaries of education technology with AI-powered insights, predictive analytics and next-generation learning platforms.",
    image: "assets/vision-edtech.png",
    stat: "5+",
    statLabel: "Products Launched",
  },
];

export default function VisionSection() {
  return (
    <section id="vision" className="py-20 px-4 sm:px-6 lg:px-8 bg-[#0d1117]">
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Our Vision"
            title="Building the Future of"
            highlight="African Education"
            subtitle="We believe every African student deserves world-class technology tools. Our mission is to make that a reality."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {pillars.map((pillar, i) => {
            const Icon = pillar.icon;
            return (
              <AnimatedSection key={pillar.title} delay={i * 0.15}>
                <div className="rounded-2xl overflow-hidden border border-[#1e2d3d] bg-[#0f1823] hover:border-[#22c55e]/50 transition-all duration-300 group">
                  <div className="relative h-52 overflow-hidden">
                    <img
                      src={assetUrl(pillar.image)}
                      alt={pillar.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0f1823] via-[#0f182388] to-transparent" />
                    <div className="absolute bottom-4 left-4 flex items-center gap-3">
                      <div className="bg-[#22c55e]/20 border border-[#22c55e]/40 rounded-xl p-2.5">
                        <Icon size={22} className="text-[#22c55e]" />
                      </div>
                      <div>
                        <p
                          className="text-2xl font-extrabold"
                          style={{
                            background: "linear-gradient(135deg, #22c55e, #4ade80)",
                            WebkitBackgroundClip: "text",
                            WebkitTextFillColor: "transparent",
                            backgroundClip: "text",
                          }}
                        >
                          {pillar.stat}
                        </p>
                        <p className="text-slate-400 text-xs">{pillar.statLabel}</p>
                      </div>
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-white font-bold text-lg mb-3 group-hover:text-[#22c55e] transition-colors">
                      {pillar.title}
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed">{pillar.description}</p>
                  </div>
                </div>
              </AnimatedSection>
            );
          })}
        </div>
      </div>
    </section>
  );
}
