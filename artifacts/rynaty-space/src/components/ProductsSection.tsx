import { GraduationCap, BookOpen, Calculator, Monitor, Wallet } from "lucide-react";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";
import { assetUrl } from "@/lib/assets";

const products = [
  {
    icon: GraduationCap,
    name: "Rynaty School Management System",
    description: "Complete smart campus platform managing admissions, attendance, fees, payroll and more in one powerful solution.",
    image: "assets/product-school-mgmt.png",
  },
  {
    icon: BookOpen,
    name: "RynatyLibrary Pro",
    description: "Digital library system with catalogue management, book tracking, borrowing records and seamless school integration.",
    image: "assets/product-library.png",
  },
  {
    icon: Calculator,
    name: "RynatyAccounts Pro",
    description: "Full-featured finance and accounting system with invoicing, fee collection, reports and financial analytics.",
    image: "assets/product-accounts.png",
  },
  {
    icon: Monitor,
    name: "Rynaty Device Management System",
    description: "Centralised IT device management for schools and organisations — track, monitor and manage all devices remotely.",
    image: "assets/product-device-mgmt.png",
  },
  {
    icon: Wallet,
    name: "Rynaty E-Wallet",
    description: "M-Pesa integrated digital wallet for school fee payments, canteen transactions and financial services.",
    image: "assets/product-ewallet.png",
  },
];

export default function ProductsSection() {
  return (
    <section
      id="products"
      className="py-20 px-4 sm:px-6 lg:px-8"
      style={{ background: "linear-gradient(180deg, #0d1117 0%, #091218 50%, #0d1117 100%)" }}
    >
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Core Products"
            title="Software Built for"
            highlight="Africa's Schools"
            subtitle="Five powerful products designed to digitise and streamline every aspect of school operations."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {products.map((product, i) => {
            const Icon = product.icon;
            return (
              <AnimatedSection key={product.name} delay={i * 0.1}>
                <div
                  className="rounded-xl overflow-hidden border border-[#1e2d3d] bg-[#0f1823] hover:border-[#22c55e]/40 transition-all duration-300 hover:shadow-lg hover:shadow-green-500/10 group h-full flex flex-col"
                >
                  <div className="relative h-44 overflow-hidden">
                    <img
                      src={assetUrl(product.image)}
                      alt={product.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0f1823] via-transparent to-transparent" />
                    <div className="absolute top-3 left-3 bg-[#22c55e]/15 border border-[#22c55e]/30 rounded-lg p-2">
                      <Icon size={20} className="text-[#22c55e]" />
                    </div>
                  </div>
                  <div className="p-5 flex-1">
                    <h3 className="text-white font-bold text-base mb-2 group-hover:text-[#22c55e] transition-colors">
                      {product.name}
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed">{product.description}</p>
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
