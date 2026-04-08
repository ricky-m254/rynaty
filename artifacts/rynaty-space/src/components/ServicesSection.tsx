import { Code, Settings, GraduationCap, Headphones, Lightbulb } from "lucide-react";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";
import { assetUrl } from "@/lib/assets";

const services = [
  {
    icon: Code,
    name: "Custom Software Development",
    description: "Bespoke software solutions tailored to your unique business or institutional requirements, delivered by expert African developers.",
    image: "assets/service-custom-dev.png",
  },
  {
    icon: Settings,
    name: "Installation & Setup",
    description: "Professional on-site installation and configuration of hardware and software systems with full testing and handover.",
    image: "assets/service-installation.png",
  },
  {
    icon: GraduationCap,
    name: "Training",
    description: "Comprehensive user training programmes for administrators, teachers and staff to maximise adoption and productivity.",
    image: "assets/service-training.png",
  },
  {
    icon: Headphones,
    name: "Technical Support",
    description: "Dedicated technical support team available to troubleshoot issues, answer questions and keep your systems running smoothly.",
    image: "assets/service-support.png",
  },
  {
    icon: Lightbulb,
    name: "IT Consultancy",
    description: "Strategic IT consulting to help schools and organisations plan, optimise and future-proof their technology infrastructure.",
    image: "assets/service-consultancy.png",
  },
];

export default function ServicesSection() {
  return (
    <section
      id="services"
      className="py-20 px-4 sm:px-6 lg:px-8"
      style={{ background: "linear-gradient(180deg, #0d1117 0%, #091218 100%)" }}
    >
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Professional Services"
            title="Expert Support"
            highlight="At Every Step"
            subtitle="From initial consultation to ongoing support — we're with you every step of the digital transformation journey."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map((service, i) => {
            const Icon = service.icon;
            return (
              <AnimatedSection key={service.name} delay={i * 0.1}>
                <div className="rounded-xl overflow-hidden border border-[#1e2d3d] bg-[#0f1823] hover:border-[#22c55e]/40 transition-all duration-300 hover:shadow-lg hover:shadow-green-500/10 group h-full flex flex-col">
                  <div className="relative h-44 overflow-hidden">
                    <img
                      src={assetUrl(service.image)}
                      alt={service.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0f1823] via-[#0f182355] to-transparent" />
                    <div className="absolute top-3 left-3 bg-[#22c55e]/15 border border-[#22c55e]/30 rounded-lg p-2">
                      <Icon size={18} className="text-[#22c55e]" />
                    </div>
                  </div>
                  <div className="p-5 flex-1">
                    <h3 className="text-white font-bold text-sm mb-2 group-hover:text-[#22c55e] transition-colors">
                      {service.name}
                    </h3>
                    <p className="text-slate-400 text-xs leading-relaxed">{service.description}</p>
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
