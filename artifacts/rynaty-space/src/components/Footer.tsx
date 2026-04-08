import { Phone, Mail } from "lucide-react";
import { assetUrl } from "@/lib/assets";

export default function Footer() {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <footer className="bg-[#080d14] border-t border-[#1e2d3d]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 mb-10">
          <div className="md:col-span-2">
            <img
              src={assetUrl("assets/rsp-logo.png")}
              alt="Rynaty Space Technologies"
              className="h-12 w-auto mb-4"
            />
            <p className="text-slate-400 text-sm leading-relaxed max-w-xs">
              Powering Africa's Digital Future through smart school management systems,
              cloud solutions and professional IT services.
            </p>
            <div className="mt-5 flex flex-col gap-2">
              <a
                href="tel:0707032911"
                className="flex items-center gap-2 text-slate-400 hover:text-[#22c55e] text-sm transition-colors"
              >
                <Phone size={14} />
                0707032911
              </a>
              <a
                href="mailto:emurithi593@gmail.com"
                className="flex items-center gap-2 text-slate-400 hover:text-[#22c55e] text-sm transition-colors"
              >
                <Mail size={14} />
                emurithi593@gmail.com
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-white font-semibold text-sm mb-4">Products</h4>
            <ul className="flex flex-col gap-2.5">
              {[
                "School Management System",
                "RynatyLibrary Pro",
                "RynatyAccounts Pro",
                "Device Management",
                "E-Wallet",
              ].map((item) => (
                <li key={item}>
                  <button
                    onClick={() => scrollTo("products")}
                    className="text-slate-400 hover:text-[#22c55e] text-sm transition-colors text-left"
                  >
                    {item}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold text-sm mb-4">Services</h4>
            <ul className="flex flex-col gap-2.5">
              {[
                "Custom Software Dev",
                "Installation & Setup",
                "Training",
                "Technical Support",
                "IT Consultancy",
              ].map((item) => (
                <li key={item}>
                  <button
                    onClick={() => scrollTo("services")}
                    className="text-slate-400 hover:text-[#22c55e] text-sm transition-colors text-left"
                  >
                    {item}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-[#1e2d3d] pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-slate-500 text-sm">
            &copy; {new Date().getFullYear()} Rynaty Space Technologies. All rights reserved.
          </p>
          <p className="text-slate-600 text-xs">
            Powering Africa's Digital Future
          </p>
        </div>
      </div>
    </footer>
  );
}
