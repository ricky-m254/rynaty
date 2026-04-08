# RynatySpace Technologies Corporate Website

## Overview
Production-quality corporate website for Rynaty Space Technologies built as a React + Vite artifact at `/rynaty/`.

## Artifacts

### Rynaty Space Technologies Website (`/rynaty/`)
- **Dir**: `artifacts/rynaty-space/`
- **Type**: React + Vite SPA
- **Stack**: React 19, Vite, Tailwind CSS 4, Framer Motion, Lucide React, Sonner

### API Server (`/`)
- **Dir**: `artifacts/api-server/`
- **Stack**: Express + TypeScript, Drizzle ORM

### Canvas / Mockup Sandbox (`/__mockup`)
- **Dir**: `artifacts/mockup-sandbox/`
- **Stack**: React + Vite, Canvas

## Website Sections
1. **Hero** — Starfield canvas animation, RSP logo, "Powering Africa's Digital Future" tagline, 2 CTA buttons
2. **Products** — 5 product cards with AI-generated images (School Management, Library Pro, Accounts Pro, Device Management, E-Wallet)
3. **Features** — 7 feature cards with Lucide icons (Student Info, Finance, Biometric, SMS, Library, Staff/Payroll, Cloud/Offline)
4. **Hardware & Integration** — 4 hardware items with AI images (Biometric, CCTV, RFID, Network)
5. **Cloud & Web Solutions** — 4 cloud items with AI images (SaaS, Portals, Hosting, Backup)
6. **Professional Services** — 5 service cards with AI images (Custom Dev, Installation, Training, Support, Consultancy)
7. **Vision** — 3 vision pillars with AI images (Smart School, Africa Expansion, EdTech Innovation)
8. **Contact** — Contact details (phone: 0707032911, email: emurithi593@gmail.com) + form with inline success message + sonner toast
9. **Footer** — Brand logo, nav links, copyright

## AI-Generated Assets
All images are stored in `artifacts/rynaty-space/public/assets/`:
- Products (5): `product-school-mgmt.png`, `product-library.png`, `product-accounts.png`, `product-device-mgmt.png`, `product-ewallet.png`
- Hardware (4): `hardware-biometric.png`, `hardware-cctv.png`, `hardware-rfid.png`, `hardware-network.png`
- Cloud (4): `cloud-saas.png`, `cloud-portals.png`, `cloud-hosting.png`, `cloud-backup.png`
- Services (5): `service-custom-dev.png`, `service-installation.png`, `service-training.png`, `service-support.png`, `service-consultancy.png`
- Vision (3): `vision-smart-school.png`, `vision-africa.png`, `vision-edtech.png`
- Logos: `rsp-logo.png`, `rs-logo.png`

## Brand Identity
- Background: `#0d1117` (near-black)
- Accent: `#22c55e` (green)
- Text: White / slate-300 / slate-400
- Cards: `#0f1823` with `#1e2d3d` borders

## Features
- Sticky navbar with active section highlighting via IntersectionObserver
- Smooth scroll navigation
- Framer Motion scroll-triggered fade-in/slide-up animations
- Canvas starfield animation in hero
- Fully responsive (mobile + desktop)
- Contact form with sonner toast + inline success message
