import { useEffect, useState } from "react";
import { Toaster } from "sonner";
import Navbar from "@/components/Navbar";
import HeroSection from "@/components/HeroSection";
import ProductsSection from "@/components/ProductsSection";
import FeaturesSection from "@/components/FeaturesSection";
import HardwareSection from "@/components/HardwareSection";
import CloudSection from "@/components/CloudSection";
import ServicesSection from "@/components/ServicesSection";
import VisionSection from "@/components/VisionSection";
import ContactSection from "@/components/ContactSection";
import Footer from "@/components/Footer";

export default function App() {
  const [activeSection, setActiveSection] = useState("hero");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      { rootMargin: "-40% 0px -40% 0px" }
    );

    const sections = document.querySelectorAll("section[id]");
    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <div className="min-h-screen bg-[#0d1117] text-white overflow-x-hidden">
        <Navbar activeSection={activeSection} />
        <main>
          <HeroSection />
          <ProductsSection />
          <FeaturesSection />
          <HardwareSection />
          <CloudSection />
          <ServicesSection />
          <VisionSection />
          <ContactSection />
        </main>
        <Footer />
      </div>
      <Toaster position="bottom-right" theme="dark" richColors />
    </>
  );
}
