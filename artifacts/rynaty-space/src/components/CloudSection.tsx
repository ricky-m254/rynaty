import { Cloud, Users, Globe, DatabaseBackup } from "lucide-react";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";
import { assetUrl } from "@/lib/assets";

const cloudItems = [
  {
    icon: Cloud,
    name: "SaaS Platform",
    description: "Fully hosted, scalable Software-as-a-Service platform. No on-premise infrastructure required — access everything from the browser.",
    image: "assets/cloud-saas.png",
  },
  {
    icon: Users,
    name: "Parent & Student Portals",
    description: "Dedicated web portals for parents to monitor fees, attendance and performance, and for students to access learning resources.",
    image: "assets/cloud-portals.png",
  },
  {
    icon: Globe,
    name: "Website & Hosting",
    description: "Professional school website design and hosting solutions — fast, secure, and optimised for African internet connectivity.",
    image: "assets/cloud-hosting.png",
  },
  {
    icon: DatabaseBackup,
    name: "Cloud Backup",
    description: "Automated, encrypted cloud backups of all school data. Never lose critical records with scheduled off-site redundancy.",
    image: "assets/cloud-backup.png",
  },
];

export default function CloudSection() {
  return (
    <section id="cloud" className="py-20 px-4 sm:px-6 lg:px-8 bg-[#0d1117]">
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Cloud & Web Solutions"
            title="Always Connected,"
            highlight="Always Secure"
            subtitle="Cloud-first infrastructure built for reliability, scalability and the unique demands of African connectivity."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {cloudItems.map((item, i) => {
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
