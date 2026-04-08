import { ShieldCheck, Camera, CreditCard, Wifi } from "lucide-react";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";
import { assetUrl } from "@/lib/assets";

const hardware = [
  {
    icon: ShieldCheck,
    name: "Biometric Systems",
    description: "ZKTeco fingerprint and facial recognition devices for secure, reliable attendance tracking in schools and organisations.",
    image: "assets/hardware-biometric.png",
  },
  {
    icon: Camera,
    name: "CCTV Integration",
    description: "Full campus CCTV surveillance setup and integration with the school management platform for enhanced security.",
    image: "assets/hardware-cctv.png",
  },
  {
    icon: CreditCard,
    name: "RFID Systems",
    description: "Contactless RFID card technology for student access control, library management and asset tracking.",
    image: "assets/hardware-rfid.png",
  },
  {
    icon: Wifi,
    name: "Network Setup",
    description: "End-to-end network infrastructure design, installation and configuration for schools and corporate environments.",
    image: "assets/hardware-network.png",
  },
];

export default function HardwareSection() {
  return (
    <section
      id="hardware"
      className="py-20 px-4 sm:px-6 lg:px-8"
      style={{ background: "linear-gradient(180deg, #0d1117 0%, #091218 100%)" }}
    >
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Hardware & Integration"
            title="Physical Tech That"
            highlight="Works Seamlessly"
            subtitle="Professional hardware supply, installation and integration with our software ecosystem."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {hardware.map((item, i) => {
            const Icon = item.icon;
            return (
              <AnimatedSection key={item.name} delay={i * 0.1}>
                <div className="rounded-xl overflow-hidden border border-[#1e2d3d] bg-[#0f1823] hover:border-[#22c55e]/40 transition-all duration-300 hover:shadow-lg hover:shadow-green-500/10 group h-full flex flex-col">
                  <div className="relative h-44 overflow-hidden">
                    <img
                      src={assetUrl(item.image)}
                      alt={item.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0f1823] via-[#0f182355] to-transparent" />
                    <div className="absolute top-3 right-3 bg-[#22c55e]/15 border border-[#22c55e]/30 rounded-lg p-2">
                      <Icon size={18} className="text-[#22c55e]" />
                    </div>
                  </div>
                  <div className="p-5 flex-1">
                    <h3 className="text-white font-bold text-sm mb-2 group-hover:text-[#22c55e] transition-colors">
                      {item.name}
                    </h3>
                    <p className="text-slate-400 text-xs leading-relaxed">{item.description}</p>
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
