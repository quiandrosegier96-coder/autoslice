"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { getSiteConfig, type SiteConfig } from "@/lib/api";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

// ── Design tokens ────────────────────────────────────────────────────────────
const BG      = "#050508";
const SURFACE = "#0c0c10";
const BRAND   = "#e02424";

// ── Landing translations ──────────────────────────────────────────────────────
const LANDING_T = {
  nl: {
    nav_features:"Features", nav_how:"Hoe het werkt", nav_pricing:"Prijzen", nav_login:"Inloggen", nav_cta:"Gratis starten",
    hero_badge:"Windows app — nu beschikbaar", hero_h1a:"Van Bambu naar", hero_h1b:"in seconden.",
    hero_sub:"AutoSlice converteert elk Bambu of MakerWorld .3mf bestand automatisch naar een geoptimaliseerd Anycubic printprofiel — met AI-analyse, multicolor support en meer.",
    hero_dl:"Downloaden voor Windows", hero_feat_btn:"Bekijk features",
    hero_free:"Gratis te gebruiken · Geen creditcard vereist · Automatische updates",
    hero_soon:"Linux & iOS — binnenkort beschikbaar", hero_based:"Gebaseerd op 128+ reviews",
    trust:"Compatibel met",
    feat_badge:"Features", feat_h2:"Alles wat je nodig hebt", feat_sub:"Van conversie tot AI-analyse — AutoSlice dekt het volledige 3D-print workflow.",
    feat1_t:"Directe 3MF conversie", feat1_d:"Upload elk Bambu of MakerWorld .3mf bestand en ontvang binnen seconden een kant-en-klaar Anycubic printprofiel.",
    feat2_t:"AI-model analyse", feat2_d:"AutoSlice analyseert automatisch overhangen, bruggen, dunne wanden en printbaarheid — en past instellingen aan.",
    feat3_t:"Multicolor support", feat3_d:"Volledige ondersteuning voor ACE Pro en ACE Pro 2 met tot 8 kleurslots, filamentwissel en flush-instellingen.",
    feat4_t:"Preset systeem", feat4_d:"Sla je printerinstellingen op als preset, hernoem ze, stel een standaard in en importeer/exporteer als JSON.",
    feat5_t:"Automatische updates", feat5_d:"AutoSlice controleert op nieuwe versies bij elke start. Updates worden op de achtergrond gedownload en geïnstalleerd.",
    feat6_t:"Veilig & privé", feat6_d:"Alle verwerking gebeurt lokaal op jouw machine. Geen bestanden naar de cloud. Jouw 3D-modellen blijven van jou.",
    how_badge:"Hoe het werkt", how_h2:"Drie stappen naar de perfecte print",
    step1_t:"Upload je bestand", step1_d:"Sleep een .3mf bestand van Bambu Studio of MakerWorld in het uploadvenster.",
    step2_t:"AI analyseert het model", step2_d:"AutoSlice berekent printbaarheid, detecteert overhangen, optimaliseert oriëntatie en kiest de beste instellingen.",
    step3_t:"Download en print", step3_d:"Ontvang een geoptimaliseerd .3mf profiel voor jouw Anycubic printer. Direct starten met printen.",
    prev_badge:"AI Analyse", prev_h2:"Slimmere prints door diepgaande modelanalyse",
    prev_sub:"AutoSlice verwerkt elk model door een uitgebreide analyse-engine die printbaarheid beoordeelt, overhangende geometrie detecteert en automatisch de beste printoriëntatie berekent.",
    prev_score:"Printbaarheidscore", prev_overhang:"Overhang risico", prev_support_lbl:"Support aanwezigheid",
    multi_badge:"Multicolor", multi_h2a:"Volledig multicolor", multi_h2b:"zonder compromissen",
    multi_sub:"Werk met ACE Pro en ACE Pro 2 configuraties tot 8 kleurslots. AutoSlice vertaalt Bambu-kleurinformatie automatisch naar de juiste Anycubic filamentslots.",
    multi_b1:"Automatische kleurdetectie uit .3mf bronbestand", multi_b2:"Instelbare flush-volumes per filamentwissel",
    multi_b3:"Dubbele unit ondersteuning (8 slots)", multi_b4:"Aangepaste filamenttypes per slot (PLA, PETG, TPU)",
    price_badge:"Prijzen", price_h2:"Simpele, eerlijke prijzen", price_sub:"Begin gratis. Upgrade wanneer je klaar bent.", price_popular:"Meest populair",
    p0_name:"Starter", p0_price:"Gratis", p0_sub:"Voor altijd", p0_cta:"Gratis starten",
    p0_f1:"15 conversies per maand", p0_f2:"Basisprinter instellingen", p0_f3:"3 opgeslagen presets", p0_f4:"Community support", p0_f5:"Automatische updates",
    p1_name:"Pro", p1_price:"€7,99", p1_sub:"per maand", p1_cta:"Pro proberen",
    p1_f1:"Onbeperkte conversies", p1_f2:"AI-model analyse", p1_f3:"Onbeperkte presets", p1_f4:"Prioriteit support", p1_f5:"Geavanceerde oriëntatie-optimalisatie", p1_f6:"Import / export presets",
    p2_name:"Team", p2_price:"€24,99", p2_sub:"per maand", p2_cta:"Contact opnemen",
    p2_f1:"Alles in Pro", p2_f2:"Tot 5 gebruikers", p2_f3:"Gedeelde presets", p2_f4:"Centraal gebruikersbeheer", p2_f5:"Prioriteit support",
    dl_h2:"Klaar om te starten?", dl_sub:"Download AutoSlice gratis voor Windows en begin vandaag nog met het converteren van je Bambu-modellen.",
    dl_btn:"Downloaden voor Windows", dl_login_lnk:"Al een account? Inloggen",
    dl_specs:"Windows 10/11 · 64-bit · ~180 MB · Automatische updates inbegrepen", dl_soon:"Linux & iOS — binnenkort beschikbaar",
    foot_brand:"De slimste manier om Bambu 3MF-bestanden te converteren naar Anycubic-printprofielen.",
    foot_product:"Product", foot_account:"Account", foot_more:"Meer",
    foot_features:"Features", foot_how:"Hoe het werkt", foot_pricing:"Prijzen",
    foot_register:"Registreren", foot_login:"Inloggen", foot_support:"Support", foot_privacy:"Privacy", foot_terms:"Voorwaarden",
    foot_copy:"Gemaakt door Quiandro Segier & Yoni Smets.",
    rev_h2:"Reviews van onze gebruikers", rev_sub:"Wat 3D-print enthousiastelingen zeggen over AutoSlice.",
    rev_based:"Gebaseerd op", rev_count_suffix:"+ reviews", rev_write:"Schrijf een review",
    modal_title:"Schrijf een review", modal_name_lbl:"Naam", modal_name_ph:"Jouw naam…",
    modal_rating_lbl:"Beoordeling", modal_text_lbl:"Review", modal_text_ph:"Deel jouw ervaring met AutoSlice…", modal_submit:"Review plaatsen",
    blog_badge:"Blog", blog_h2:"Laatste nieuws", blog_sub:"Tips, tutorials en updates over AutoSlice en 3D printen.", blog_read:"Lees meer →",
    blog1_cat:"Tutorial", blog1_title:"Bambu naar Anycubic converteren: stap voor stap", blog1_date:"15 april 2026",
    blog1_excerpt:"Leer hoe je elk Bambu Studio of MakerWorld .3mf bestand omzet naar een kant-en-klaar Anycubic printprofiel in minder dan een minuut.",
    blog2_cat:"Handleiding", blog2_title:"Multicolor printen met ACE Pro 2 en AutoSlice", blog2_date:"3 april 2026",
    blog2_excerpt:"Alles over het instellen van 8 kleurslots, filamentwissel en flush-volumes voor perfecte multicolor prints.",
    blog3_cat:"Update", blog3_title:"AutoSlice 1.5: AI-analyse, presets en meer", blog3_date:"20 maart 2026",
    blog3_excerpt:"Een overzicht van alle nieuwe functies in versie 1.5: verbeterde AI-analyse, exporteerbare presets en de nieuwe community-pagina.",
  },
  en: {
    nav_features:"Features", nav_how:"How it works", nav_pricing:"Pricing", nav_login:"Log in", nav_cta:"Start for free",
    hero_badge:"Windows app — now available", hero_h1a:"From Bambu to", hero_h1b:"in seconds.",
    hero_sub:"AutoSlice automatically converts any Bambu or MakerWorld .3mf file into an optimized Anycubic print profile — with AI analysis, multicolor support and more.",
    hero_dl:"Download for Windows", hero_feat_btn:"View features",
    hero_free:"Free to use · No credit card required · Automatic updates",
    hero_soon:"Linux & iOS — coming soon", hero_based:"Based on 128+ reviews",
    trust:"Compatible with",
    feat_badge:"Features", feat_h2:"Everything you need", feat_sub:"From conversion to AI analysis — AutoSlice covers the full 3D print workflow.",
    feat1_t:"Direct 3MF conversion", feat1_d:"Upload any Bambu or MakerWorld .3mf file and receive a ready-to-use Anycubic print profile within seconds.",
    feat2_t:"AI model analysis", feat2_d:"AutoSlice automatically analyzes overhangs, bridges, thin walls and printability — and adjusts settings accordingly.",
    feat3_t:"Multicolor support", feat3_d:"Full support for ACE Pro and ACE Pro 2 with up to 8 color slots, filament changes and flush settings.",
    feat4_t:"Preset system", feat4_d:"Save your printer settings as presets, rename them, set a default and import/export as JSON.",
    feat5_t:"Automatic updates", feat5_d:"AutoSlice checks for new versions on every start. Updates are downloaded and installed in the background.",
    feat6_t:"Safe & private", feat6_d:"All processing happens locally on your machine. No files sent to the cloud. Your 3D models stay yours.",
    how_badge:"How it works", how_h2:"Three steps to the perfect print",
    step1_t:"Upload your file", step1_d:"Drag a .3mf file from Bambu Studio or MakerWorld into the upload window.",
    step2_t:"AI analyzes the model", step2_d:"AutoSlice calculates printability, detects overhangs, optimizes orientation and chooses the best settings.",
    step3_t:"Download and print", step3_d:"Receive an optimized .3mf profile for your Anycubic printer. Start printing right away.",
    prev_badge:"AI Analysis", prev_h2:"Smarter prints through deep model analysis",
    prev_sub:"AutoSlice processes every model through a comprehensive analysis engine that evaluates printability, detects overhanging geometry and automatically calculates the best print orientation.",
    prev_score:"Printability score", prev_overhang:"Overhang risk", prev_support_lbl:"Support presence",
    multi_badge:"Multicolor", multi_h2a:"Full multicolor", multi_h2b:"without compromise",
    multi_sub:"Work with ACE Pro and ACE Pro 2 configurations up to 8 color slots. AutoSlice automatically translates Bambu color information to the correct Anycubic filament slots.",
    multi_b1:"Automatic color detection from .3mf source file", multi_b2:"Configurable flush volumes per filament change",
    multi_b3:"Dual unit support (8 slots)", multi_b4:"Custom filament types per slot (PLA, PETG, TPU)",
    price_badge:"Pricing", price_h2:"Simple, honest pricing", price_sub:"Start free. Upgrade when you're ready.", price_popular:"Most popular",
    p0_name:"Starter", p0_price:"Free", p0_sub:"Forever", p0_cta:"Start for free",
    p0_f1:"15 conversions per month", p0_f2:"Basic printer settings", p0_f3:"3 saved presets", p0_f4:"Community support", p0_f5:"Automatic updates",
    p1_name:"Pro", p1_price:"€7.99", p1_sub:"per month", p1_cta:"Try Pro",
    p1_f1:"Unlimited conversions", p1_f2:"AI model analysis", p1_f3:"Unlimited presets", p1_f4:"Priority support", p1_f5:"Advanced orientation optimization", p1_f6:"Import / export presets",
    p2_name:"Team", p2_price:"€24.99", p2_sub:"per month", p2_cta:"Contact us",
    p2_f1:"Everything in Pro", p2_f2:"Up to 5 users", p2_f3:"Shared presets", p2_f4:"Central user management", p2_f5:"Priority support",
    dl_h2:"Ready to get started?", dl_sub:"Download AutoSlice free for Windows and start converting your Bambu models today.",
    dl_btn:"Download for Windows", dl_login_lnk:"Already have an account? Log in",
    dl_specs:"Windows 10/11 · 64-bit · ~180 MB · Automatic updates included", dl_soon:"Linux & iOS — coming soon",
    foot_brand:"The smartest way to convert Bambu 3MF files to Anycubic print profiles.",
    foot_product:"Product", foot_account:"Account", foot_more:"More",
    foot_features:"Features", foot_how:"How it works", foot_pricing:"Pricing",
    foot_register:"Register", foot_login:"Log in", foot_support:"Support", foot_privacy:"Privacy", foot_terms:"Terms",
    foot_copy:"Made by Quiandro Segier & Yoni Smets.",
    rev_h2:"Reviews from our users", rev_sub:"What 3D printing enthusiasts say about AutoSlice.",
    rev_based:"Based on", rev_count_suffix:"+ reviews", rev_write:"Write a review",
    modal_title:"Write a review", modal_name_lbl:"Name", modal_name_ph:"Your name…",
    modal_rating_lbl:"Rating", modal_text_lbl:"Review", modal_text_ph:"Share your experience with AutoSlice…", modal_submit:"Post review",
    blog_badge:"Blog", blog_h2:"Latest news", blog_sub:"Tips, tutorials and updates about AutoSlice and 3D printing.", blog_read:"Read more →",
    blog1_cat:"Tutorial", blog1_title:"Converting Bambu to Anycubic: step by step", blog1_date:"April 15, 2026",
    blog1_excerpt:"Learn how to convert any Bambu Studio or MakerWorld .3mf file into a ready-to-use Anycubic print profile in under a minute.",
    blog2_cat:"Guide", blog2_title:"Multicolor printing with ACE Pro 2 and AutoSlice", blog2_date:"April 3, 2026",
    blog2_excerpt:"Everything about setting up 8 color slots, filament changes and flush volumes for perfect multicolor prints.",
    blog3_cat:"Update", blog3_title:"AutoSlice 1.5: AI analysis, presets and more", blog3_date:"March 20, 2026",
    blog3_excerpt:"An overview of all new features in version 1.5: improved AI analysis, exportable presets and the new community page.",
  },
  fr: {
    nav_features:"Fonctionnalités", nav_how:"Comment ça marche", nav_pricing:"Tarifs", nav_login:"Se connecter", nav_cta:"Commencer gratuitement",
    hero_badge:"Application Windows — disponible maintenant", hero_h1a:"De Bambu vers", hero_h1b:"en quelques secondes.",
    hero_sub:"AutoSlice convertit automatiquement tout fichier Bambu ou MakerWorld .3mf en un profil d'impression Anycubic optimisé — avec analyse IA, support multicolore et plus encore.",
    hero_dl:"Télécharger pour Windows", hero_feat_btn:"Voir les fonctionnalités",
    hero_free:"Gratuit · Aucune carte de crédit · Mises à jour automatiques",
    hero_soon:"Linux & iOS — bientôt disponible", hero_based:"Basé sur 128+ avis",
    trust:"Compatible avec",
    feat_badge:"Fonctionnalités", feat_h2:"Tout ce dont vous avez besoin", feat_sub:"De la conversion à l'analyse IA — AutoSlice couvre l'intégralité du flux d'impression 3D.",
    feat1_t:"Conversion 3MF directe", feat1_d:"Téléchargez n'importe quel fichier Bambu ou MakerWorld .3mf et recevez un profil Anycubic prêt à imprimer en quelques secondes.",
    feat2_t:"Analyse IA du modèle", feat2_d:"AutoSlice analyse automatiquement les surplombs, ponts, parois minces et l'imprimabilité — et ajuste les paramètres.",
    feat3_t:"Support multicolore", feat3_d:"Prise en charge complète de l'ACE Pro et ACE Pro 2 avec jusqu'à 8 emplacements de couleur, changement de filament et paramètres de purge.",
    feat4_t:"Système de préréglages", feat4_d:"Enregistrez vos paramètres imprimante comme préréglages, renommez-les, définissez un par défaut et importez/exportez en JSON.",
    feat5_t:"Mises à jour automatiques", feat5_d:"AutoSlice vérifie les nouvelles versions à chaque démarrage. Les mises à jour sont téléchargées et installées en arrière-plan.",
    feat6_t:"Sécurisé & privé", feat6_d:"Tout le traitement se fait localement sur votre machine. Aucun fichier envoyé dans le cloud. Vos modèles 3D restent les vôtres.",
    how_badge:"Comment ça marche", how_h2:"Trois étapes vers l'impression parfaite",
    step1_t:"Téléversez votre fichier", step1_d:"Faites glisser un fichier .3mf de Bambu Studio ou MakerWorld dans la fenêtre de téléversement.",
    step2_t:"L'IA analyse le modèle", step2_d:"AutoSlice calcule l'imprimabilité, détecte les surplombs, optimise l'orientation et choisit les meilleurs paramètres.",
    step3_t:"Téléchargez et imprimez", step3_d:"Recevez un profil .3mf optimisé pour votre imprimante Anycubic. Commencez à imprimer immédiatement.",
    prev_badge:"Analyse IA", prev_h2:"Des impressions plus intelligentes grâce à une analyse approfondie",
    prev_sub:"AutoSlice traite chaque modèle via un moteur d'analyse complet qui évalue l'imprimabilité, détecte la géométrie en surplomb et calcule automatiquement la meilleure orientation d'impression.",
    prev_score:"Score d'imprimabilité", prev_overhang:"Risque de surplomb", prev_support_lbl:"Présence de supports",
    multi_badge:"Multicolore", multi_h2a:"Multicolore complet", multi_h2b:"sans compromis",
    multi_sub:"Travaillez avec des configurations ACE Pro et ACE Pro 2 jusqu'à 8 emplacements de couleur. AutoSlice traduit automatiquement les informations de couleur Bambu vers les bons emplacements de filament Anycubic.",
    multi_b1:"Détection automatique des couleurs depuis le fichier .3mf source", multi_b2:"Volumes de purge configurables par changement de filament",
    multi_b3:"Support double unité (8 emplacements)", multi_b4:"Types de filaments personnalisés par emplacement (PLA, PETG, TPU)",
    price_badge:"Tarifs", price_h2:"Des prix simples et honnêtes", price_sub:"Commencez gratuitement. Passez à la version supérieure quand vous êtes prêt.", price_popular:"Le plus populaire",
    p0_name:"Starter", p0_price:"Gratuit", p0_sub:"Pour toujours", p0_cta:"Commencer gratuitement",
    p0_f1:"15 conversions par mois", p0_f2:"Paramètres imprimante de base", p0_f3:"3 préréglages enregistrés", p0_f4:"Support communautaire", p0_f5:"Mises à jour automatiques",
    p1_name:"Pro", p1_price:"€7,99", p1_sub:"par mois", p1_cta:"Essayer Pro",
    p1_f1:"Conversions illimitées", p1_f2:"Analyse IA du modèle", p1_f3:"Préréglages illimités", p1_f4:"Support prioritaire", p1_f5:"Optimisation avancée de l'orientation", p1_f6:"Import / export de préréglages",
    p2_name:"Team", p2_price:"€24,99", p2_sub:"par mois", p2_cta:"Nous contacter",
    p2_f1:"Tout dans Pro", p2_f2:"Jusqu'à 5 utilisateurs", p2_f3:"Préréglages partagés", p2_f4:"Gestion centralisée des utilisateurs", p2_f5:"Support prioritaire",
    dl_h2:"Prêt à commencer ?", dl_sub:"Téléchargez AutoSlice gratuitement pour Windows et commencez dès aujourd'hui à convertir vos modèles Bambu.",
    dl_btn:"Télécharger pour Windows", dl_login_lnk:"Déjà un compte ? Se connecter",
    dl_specs:"Windows 10/11 · 64-bit · ~180 Mo · Mises à jour automatiques incluses", dl_soon:"Linux & iOS — bientôt disponible",
    foot_brand:"La façon la plus intelligente de convertir des fichiers Bambu 3MF en profils d'impression Anycubic.",
    foot_product:"Produit", foot_account:"Compte", foot_more:"Plus",
    foot_features:"Fonctionnalités", foot_how:"Comment ça marche", foot_pricing:"Tarifs",
    foot_register:"S'inscrire", foot_login:"Se connecter", foot_support:"Support", foot_privacy:"Confidentialité", foot_terms:"Conditions",
    foot_copy:"Créé par Quiandro Segier & Yoni Smets.",
    rev_h2:"Avis de nos utilisateurs", rev_sub:"Ce que les passionnés d'impression 3D disent d'AutoSlice.",
    rev_based:"Basé sur", rev_count_suffix:"+ avis", rev_write:"Écrire un avis",
    modal_title:"Écrire un avis", modal_name_lbl:"Nom", modal_name_ph:"Votre nom…",
    modal_rating_lbl:"Note", modal_text_lbl:"Avis", modal_text_ph:"Partagez votre expérience avec AutoSlice…", modal_submit:"Publier l'avis",
    blog_badge:"Blog", blog_h2:"Dernières actualités", blog_sub:"Conseils, tutoriels et mises à jour sur AutoSlice et l'impression 3D.", blog_read:"Lire la suite →",
    blog1_cat:"Tutoriel", blog1_title:"Convertir Bambu en Anycubic : étape par étape", blog1_date:"15 avril 2026",
    blog1_excerpt:"Apprenez à convertir n'importe quel fichier Bambu Studio ou MakerWorld .3mf en un profil d'impression Anycubic prêt à l'emploi en moins d'une minute.",
    blog2_cat:"Guide", blog2_title:"Impression multicolore avec ACE Pro 2 et AutoSlice", blog2_date:"3 avril 2026",
    blog2_excerpt:"Tout sur la configuration de 8 emplacements de couleur, les changements de filament et les volumes de purge pour des impressions multicolores parfaites.",
    blog3_cat:"Mise à jour", blog3_title:"AutoSlice 1.5 : analyse IA, préréglages et plus", blog3_date:"20 mars 2026",
    blog3_excerpt:"Un aperçu de toutes les nouvelles fonctionnalités de la version 1.5 : analyse IA améliorée, préréglages exportables et la nouvelle page communauté.",
  },
  de: {
    nav_features:"Funktionen", nav_how:"So funktioniert es", nav_pricing:"Preise", nav_login:"Anmelden", nav_cta:"Kostenlos starten",
    hero_badge:"Windows-App — jetzt verfügbar", hero_h1a:"Von Bambu zu", hero_h1b:"in Sekunden.",
    hero_sub:"AutoSlice konvertiert automatisch jede Bambu- oder MakerWorld-.3mf-Datei in ein optimiertes Anycubic-Druckprofil — mit KI-Analyse, Multicolor-Unterstützung und mehr.",
    hero_dl:"Für Windows herunterladen", hero_feat_btn:"Funktionen ansehen",
    hero_free:"Kostenlos · Keine Kreditkarte · Automatische Updates",
    hero_soon:"Linux & iOS — demnächst verfügbar", hero_based:"Basierend auf 128+ Bewertungen",
    trust:"Kompatibel mit",
    feat_badge:"Funktionen", feat_h2:"Alles, was Sie brauchen", feat_sub:"Von der Konvertierung bis zur KI-Analyse — AutoSlice deckt den gesamten 3D-Druck-Workflow ab.",
    feat1_t:"Direkte 3MF-Konvertierung", feat1_d:"Laden Sie eine beliebige Bambu- oder MakerWorld-.3mf-Datei hoch und erhalten Sie innerhalb von Sekunden ein fertiges Anycubic-Druckprofil.",
    feat2_t:"KI-Modellanalyse", feat2_d:"AutoSlice analysiert automatisch Überhänge, Brücken, dünne Wände und Druckbarkeit — und passt die Einstellungen an.",
    feat3_t:"Multicolor-Unterstützung", feat3_d:"Vollständige Unterstützung für ACE Pro und ACE Pro 2 mit bis zu 8 Farbslots, Filamentwechsel und Flush-Einstellungen.",
    feat4_t:"Preset-System", feat4_d:"Speichern Sie Ihre Druckereinstellungen als Presets, benennen Sie sie um, legen Sie einen Standard fest und importieren/exportieren Sie als JSON.",
    feat5_t:"Automatische Updates", feat5_d:"AutoSlice prüft bei jedem Start auf neue Versionen. Updates werden im Hintergrund heruntergeladen und installiert.",
    feat6_t:"Sicher & privat", feat6_d:"Alle Verarbeitung erfolgt lokal auf Ihrem Gerät. Keine Dateien in die Cloud. Ihre 3D-Modelle bleiben Ihre.",
    how_badge:"So funktioniert es", how_h2:"Drei Schritte zum perfekten Druck",
    step1_t:"Datei hochladen", step1_d:"Ziehen Sie eine .3mf-Datei aus Bambu Studio oder MakerWorld in das Upload-Fenster.",
    step2_t:"KI analysiert das Modell", step2_d:"AutoSlice berechnet Druckbarkeit, erkennt Überhänge, optimiert die Ausrichtung und wählt die besten Einstellungen.",
    step3_t:"Herunterladen und drucken", step3_d:"Erhalten Sie ein optimiertes .3mf-Profil für Ihren Anycubic-Drucker. Sofort mit dem Drucken beginnen.",
    prev_badge:"KI-Analyse", prev_h2:"Intelligentere Drucke durch tiefgreifende Modellanalyse",
    prev_sub:"AutoSlice verarbeitet jedes Modell durch eine umfassende Analyse-Engine, die Druckbarkeit bewertet, überhängende Geometrie erkennt und automatisch die beste Druckausrichtung berechnet.",
    prev_score:"Druckbarkeitsbewertung", prev_overhang:"Überhang-Risiko", prev_support_lbl:"Stützstruktur-Anteil",
    multi_badge:"Multicolor", multi_h2a:"Vollständiges Multicolor", multi_h2b:"ohne Kompromisse",
    multi_sub:"Arbeiten Sie mit ACE Pro- und ACE Pro 2-Konfigurationen bis zu 8 Farbslots. AutoSlice übersetzt Bambu-Farbinformationen automatisch in die richtigen Anycubic-Filamentslots.",
    multi_b1:"Automatische Farberkennung aus .3mf-Quelldatei", multi_b2:"Einstellbare Spülvolumen pro Filamentwechsel",
    multi_b3:"Doppeleinheit-Unterstützung (8 Slots)", multi_b4:"Benutzerdefinierte Filamenttypen pro Slot (PLA, PETG, TPU)",
    price_badge:"Preise", price_h2:"Einfache, faire Preise", price_sub:"Kostenlos starten. Upgraden wenn Sie bereit sind.", price_popular:"Beliebteste Wahl",
    p0_name:"Starter", p0_price:"Kostenlos", p0_sub:"Für immer", p0_cta:"Kostenlos starten",
    p0_f1:"15 Konvertierungen pro Monat", p0_f2:"Basis-Druckereinstellungen", p0_f3:"3 gespeicherte Presets", p0_f4:"Community-Support", p0_f5:"Automatische Updates",
    p1_name:"Pro", p1_price:"€7,99", p1_sub:"pro Monat", p1_cta:"Pro testen",
    p1_f1:"Unbegrenzte Konvertierungen", p1_f2:"KI-Modellanalyse", p1_f3:"Unbegrenzte Presets", p1_f4:"Prioritäts-Support", p1_f5:"Erweiterte Ausrichtungsoptimierung", p1_f6:"Presets importieren / exportieren",
    p2_name:"Team", p2_price:"€24,99", p2_sub:"pro Monat", p2_cta:"Kontakt aufnehmen",
    p2_f1:"Alles in Pro", p2_f2:"Bis zu 5 Benutzer", p2_f3:"Geteilte Presets", p2_f4:"Zentrale Benutzerverwaltung", p2_f5:"Prioritäts-Support",
    dl_h2:"Bereit loszulegen?", dl_sub:"Laden Sie AutoSlice kostenlos für Windows herunter und beginnen Sie noch heute mit der Konvertierung Ihrer Bambu-Modelle.",
    dl_btn:"Für Windows herunterladen", dl_login_lnk:"Bereits ein Konto? Anmelden",
    dl_specs:"Windows 10/11 · 64-bit · ~180 MB · Automatische Updates inklusive", dl_soon:"Linux & iOS — demnächst verfügbar",
    foot_brand:"Der intelligenteste Weg, Bambu-3MF-Dateien in Anycubic-Druckprofile zu konvertieren.",
    foot_product:"Produkt", foot_account:"Konto", foot_more:"Mehr",
    foot_features:"Funktionen", foot_how:"So funktioniert es", foot_pricing:"Preise",
    foot_register:"Registrieren", foot_login:"Anmelden", foot_support:"Support", foot_privacy:"Datenschutz", foot_terms:"AGB",
    foot_copy:"Erstellt von Quiandro Segier & Yoni Smets.",
    rev_h2:"Bewertungen unserer Nutzer", rev_sub:"Was 3D-Druck-Enthusiasten über AutoSlice sagen.",
    rev_based:"Basierend auf", rev_count_suffix:"+ Bewertungen", rev_write:"Bewertung schreiben",
    modal_title:"Bewertung schreiben", modal_name_lbl:"Name", modal_name_ph:"Ihr Name…",
    modal_rating_lbl:"Bewertung", modal_text_lbl:"Rezension", modal_text_ph:"Teilen Sie Ihre Erfahrung mit AutoSlice…", modal_submit:"Bewertung posten",
    blog_badge:"Blog", blog_h2:"Neueste Beiträge", blog_sub:"Tipps, Tutorials und Updates zu AutoSlice und 3D-Druck.", blog_read:"Weiterlesen →",
    blog1_cat:"Tutorial", blog1_title:"Bambu zu Anycubic konvertieren: Schritt für Schritt", blog1_date:"15. April 2026",
    blog1_excerpt:"Lernen Sie, wie Sie jede Bambu Studio- oder MakerWorld-.3mf-Datei in weniger als einer Minute in ein fertiges Anycubic-Druckprofil umwandeln.",
    blog2_cat:"Anleitung", blog2_title:"Multicolor-Druck mit ACE Pro 2 und AutoSlice", blog2_date:"3. April 2026",
    blog2_excerpt:"Alles über die Einrichtung von 8 Farbslots, Filamentwechsel und Spülvolumen für perfekte Multicolor-Drucke.",
    blog3_cat:"Update", blog3_title:"AutoSlice 1.5: KI-Analyse, Presets und mehr", blog3_date:"20. März 2026",
    blog3_excerpt:"Eine Übersicht aller neuen Funktionen in Version 1.5: verbesserte KI-Analyse, exportierbare Presets und die neue Community-Seite.",
  },
  es: {
    nav_features:"Características", nav_how:"Cómo funciona", nav_pricing:"Precios", nav_login:"Iniciar sesión", nav_cta:"Empezar gratis",
    hero_badge:"Aplicación Windows — ya disponible", hero_h1a:"De Bambu a", hero_h1b:"en segundos.",
    hero_sub:"AutoSlice convierte automáticamente cualquier archivo Bambu o MakerWorld .3mf en un perfil de impresión Anycubic optimizado — con análisis IA, soporte multicolor y más.",
    hero_dl:"Descargar para Windows", hero_feat_btn:"Ver características",
    hero_free:"Gratis · Sin tarjeta de crédito · Actualizaciones automáticas",
    hero_soon:"Linux & iOS — próximamente", hero_based:"Basado en 128+ reseñas",
    trust:"Compatible con",
    feat_badge:"Características", feat_h2:"Todo lo que necesitas", feat_sub:"De la conversión al análisis IA — AutoSlice cubre todo el flujo de trabajo de impresión 3D.",
    feat1_t:"Conversión 3MF directa", feat1_d:"Sube cualquier archivo Bambu o MakerWorld .3mf y recibe un perfil de impresión Anycubic listo en segundos.",
    feat2_t:"Análisis IA del modelo", feat2_d:"AutoSlice analiza automáticamente voladizos, puentes, paredes delgadas e imprimibilidad — y ajusta la configuración.",
    feat3_t:"Soporte multicolor", feat3_d:"Soporte completo para ACE Pro y ACE Pro 2 con hasta 8 ranuras de color, cambios de filamento y configuración de purga.",
    feat4_t:"Sistema de preajustes", feat4_d:"Guarda la configuración de tu impresora como preajustes, renómbralos, establece uno predeterminado e importa/exporta como JSON.",
    feat5_t:"Actualizaciones automáticas", feat5_d:"AutoSlice verifica nuevas versiones en cada inicio. Las actualizaciones se descargan e instalan en segundo plano.",
    feat6_t:"Seguro y privado", feat6_d:"Todo el procesamiento ocurre localmente en tu máquina. Sin archivos en la nube. Tus modelos 3D son tuyos.",
    how_badge:"Cómo funciona", how_h2:"Tres pasos hacia la impresión perfecta",
    step1_t:"Sube tu archivo", step1_d:"Arrastra un archivo .3mf de Bambu Studio o MakerWorld a la ventana de carga.",
    step2_t:"La IA analiza el modelo", step2_d:"AutoSlice calcula imprimibilidad, detecta voladizos, optimiza orientación y elige la mejor configuración.",
    step3_t:"Descarga e imprime", step3_d:"Recibe un perfil .3mf optimizado para tu impresora Anycubic. Comienza a imprimir de inmediato.",
    prev_badge:"Análisis IA", prev_h2:"Impresiones más inteligentes mediante análisis profundo del modelo",
    prev_sub:"AutoSlice procesa cada modelo a través de un motor de análisis completo que evalúa imprimibilidad, detecta geometría en voladizo y calcula automáticamente la mejor orientación de impresión.",
    prev_score:"Puntuación de imprimibilidad", prev_overhang:"Riesgo de voladizo", prev_support_lbl:"Presencia de soportes",
    multi_badge:"Multicolor", multi_h2a:"Multicolor completo", multi_h2b:"sin compromisos",
    multi_sub:"Trabaja con configuraciones ACE Pro y ACE Pro 2 de hasta 8 ranuras de color. AutoSlice traduce automáticamente la información de color de Bambu a las ranuras de filamento correctas de Anycubic.",
    multi_b1:"Detección automática de color desde archivo .3mf fuente", multi_b2:"Volúmenes de purga configurables por cambio de filamento",
    multi_b3:"Soporte de unidad doble (8 ranuras)", multi_b4:"Tipos de filamento personalizados por ranura (PLA, PETG, TPU)",
    price_badge:"Precios", price_h2:"Precios simples y justos", price_sub:"Empieza gratis. Actualiza cuando estés listo.", price_popular:"Más popular",
    p0_name:"Starter", p0_price:"Gratis", p0_sub:"Para siempre", p0_cta:"Empezar gratis",
    p0_f1:"15 conversiones por mes", p0_f2:"Configuración básica de impresora", p0_f3:"3 preajustes guardados", p0_f4:"Soporte comunitario", p0_f5:"Actualizaciones automáticas",
    p1_name:"Pro", p1_price:"€7,99", p1_sub:"por mes", p1_cta:"Probar Pro",
    p1_f1:"Conversiones ilimitadas", p1_f2:"Análisis IA del modelo", p1_f3:"Preajustes ilimitados", p1_f4:"Soporte prioritario", p1_f5:"Optimización avanzada de orientación", p1_f6:"Importar / exportar preajustes",
    p2_name:"Team", p2_price:"€24,99", p2_sub:"por mes", p2_cta:"Contactar",
    p2_f1:"Todo en Pro", p2_f2:"Hasta 5 usuarios", p2_f3:"Preajustes compartidos", p2_f4:"Gestión central de usuarios", p2_f5:"Soporte prioritario",
    dl_h2:"¿Listo para empezar?", dl_sub:"Descarga AutoSlice gratis para Windows y empieza hoy a convertir tus modelos Bambu.",
    dl_btn:"Descargar para Windows", dl_login_lnk:"¿Ya tienes cuenta? Iniciar sesión",
    dl_specs:"Windows 10/11 · 64-bit · ~180 MB · Actualizaciones automáticas incluidas", dl_soon:"Linux & iOS — próximamente",
    foot_brand:"La forma más inteligente de convertir archivos Bambu 3MF en perfiles de impresión Anycubic.",
    foot_product:"Producto", foot_account:"Cuenta", foot_more:"Más",
    foot_features:"Características", foot_how:"Cómo funciona", foot_pricing:"Precios",
    foot_register:"Registrarse", foot_login:"Iniciar sesión", foot_support:"Soporte", foot_privacy:"Privacidad", foot_terms:"Términos",
    foot_copy:"Hecho por Quiandro Segier & Yoni Smets.",
    rev_h2:"Reseñas de nuestros usuarios", rev_sub:"Lo que los entusiastas de la impresión 3D dicen sobre AutoSlice.",
    rev_based:"Basado en", rev_count_suffix:"+ reseñas", rev_write:"Escribir una reseña",
    modal_title:"Escribir una reseña", modal_name_lbl:"Nombre", modal_name_ph:"Tu nombre…",
    modal_rating_lbl:"Valoración", modal_text_lbl:"Reseña", modal_text_ph:"Comparte tu experiencia con AutoSlice…", modal_submit:"Publicar reseña",
    blog_badge:"Blog", blog_h2:"Últimas noticias", blog_sub:"Consejos, tutoriales y actualizaciones sobre AutoSlice e impresión 3D.", blog_read:"Leer más →",
    blog1_cat:"Tutorial", blog1_title:"Convertir Bambu a Anycubic: paso a paso", blog1_date:"15 de abril de 2026",
    blog1_excerpt:"Aprende a convertir cualquier archivo Bambu Studio o MakerWorld .3mf en un perfil de impresión Anycubic listo en menos de un minuto.",
    blog2_cat:"Guía", blog2_title:"Impresión multicolor con ACE Pro 2 y AutoSlice", blog2_date:"3 de abril de 2026",
    blog2_excerpt:"Todo sobre la configuración de 8 ranuras de color, cambios de filamento y volúmenes de purga para impresiones multicolor perfectas.",
    blog3_cat:"Actualización", blog3_title:"AutoSlice 1.5: análisis IA, preajustes y más", blog3_date:"20 de marzo de 2026",
    blog3_excerpt:"Un resumen de todas las nuevas funciones en la versión 1.5: análisis IA mejorado, preajustes exportables y la nueva página de comunidad.",
  },
  ko: {
    nav_features:"기능", nav_how:"사용 방법", nav_pricing:"가격", nav_login:"로그인", nav_cta:"무료로 시작",
    hero_badge:"Windows 앱 — 지금 사용 가능", hero_h1a:"Bambu에서", hero_h1b:"로, 몇 초 만에.",
    hero_sub:"AutoSlice는 모든 Bambu 또는 MakerWorld .3mf 파일을 최적화된 Anycubic 프린트 프로필로 자동 변환합니다 — AI 분석, 멀티컬러 지원 등.",
    hero_dl:"Windows용 다운로드", hero_feat_btn:"기능 보기",
    hero_free:"무료 사용 · 신용카드 불필요 · 자동 업데이트",
    hero_soon:"Linux & iOS — 곧 출시", hero_based:"128개 이상의 리뷰 기반",
    trust:"호환 가능",
    feat_badge:"기능", feat_h2:"필요한 모든 것", feat_sub:"변환부터 AI 분석까지 — AutoSlice가 전체 3D 프린팅 워크플로우를 다룹니다.",
    feat1_t:"직접 3MF 변환", feat1_d:"Bambu 또는 MakerWorld .3mf 파일을 업로드하면 몇 초 안에 Anycubic 프린트 프로필을 받을 수 있습니다.",
    feat2_t:"AI 모델 분석", feat2_d:"AutoSlice는 오버행, 브리지, 얇은 벽, 출력 가능성을 자동으로 분석하고 설정을 조정합니다.",
    feat3_t:"멀티컬러 지원", feat3_d:"최대 8개 색상 슬롯, 필라멘트 교체, 플러시 설정을 지원하는 ACE Pro 및 ACE Pro 2 완전 지원.",
    feat4_t:"프리셋 시스템", feat4_d:"프린터 설정을 프리셋으로 저장하고, 이름 변경, 기본값 설정, JSON으로 가져오기/내보내기 가능.",
    feat5_t:"자동 업데이트", feat5_d:"AutoSlice는 매 시작 시 새 버전을 확인합니다. 업데이트는 백그라운드에서 다운로드 및 설치됩니다.",
    feat6_t:"안전하고 개인적", feat6_d:"모든 처리는 로컬 기기에서 이루어집니다. 클라우드에 파일 전송 없음. 3D 모델은 당신의 것입니다.",
    how_badge:"사용 방법", how_h2:"완벽한 출력을 위한 세 단계",
    step1_t:"파일 업로드", step1_d:"Bambu Studio 또는 MakerWorld의 .3mf 파일을 업로드 창으로 드래그하세요.",
    step2_t:"AI가 모델 분석", step2_d:"AutoSlice는 출력 가능성을 계산하고, 오버행을 감지하며, 방향을 최적화하고, 최적 설정을 선택합니다.",
    step3_t:"다운로드 및 출력", step3_d:"Anycubic 프린터에 최적화된 .3mf 프로필을 받으세요. 바로 출력을 시작하세요.",
    prev_badge:"AI 분석", prev_h2:"심층 모델 분석을 통한 스마트한 출력",
    prev_sub:"AutoSlice는 출력 가능성을 평가하고, 오버행 형상을 감지하며, 최적 출력 방향을 자동 계산하는 포괄적인 분석 엔진을 통해 모든 모델을 처리합니다.",
    prev_score:"출력 가능성 점수", prev_overhang:"오버행 위험", prev_support_lbl:"서포트 존재",
    multi_badge:"멀티컬러", multi_h2a:"완전한 멀티컬러", multi_h2b:"타협 없이",
    multi_sub:"최대 8개 색상 슬롯의 ACE Pro 및 ACE Pro 2 구성으로 작업하세요. AutoSlice가 Bambu 색상 정보를 올바른 Anycubic 필라멘트 슬롯으로 자동 변환합니다.",
    multi_b1:".3mf 소스 파일에서 자동 색상 감지", multi_b2:"필라멘트 교체당 플러시 볼륨 조정 가능",
    multi_b3:"이중 유닛 지원 (8 슬롯)", multi_b4:"슬롯별 맞춤 필라멘트 타입 (PLA, PETG, TPU)",
    price_badge:"가격", price_h2:"단순하고 합리적인 가격", price_sub:"무료로 시작하세요. 준비되면 업그레이드하세요.", price_popular:"가장 인기",
    p0_name:"Starter", p0_price:"무료", p0_sub:"영구", p0_cta:"무료로 시작",
    p0_f1:"월 15회 변환", p0_f2:"기본 프린터 설정", p0_f3:"프리셋 3개 저장", p0_f4:"커뮤니티 지원", p0_f5:"자동 업데이트",
    p1_name:"Pro", p1_price:"€7.99", p1_sub:"월", p1_cta:"Pro 체험",
    p1_f1:"무제한 변환", p1_f2:"AI 모델 분석", p1_f3:"무제한 프리셋", p1_f4:"우선 지원", p1_f5:"고급 방향 최적화", p1_f6:"프리셋 가져오기 / 내보내기",
    p2_name:"Team", p2_price:"€24.99", p2_sub:"월", p2_cta:"문의하기",
    p2_f1:"Pro의 모든 것", p2_f2:"최대 5명 사용자", p2_f3:"공유 프리셋", p2_f4:"중앙 사용자 관리", p2_f5:"우선 지원",
    dl_h2:"시작할 준비가 되셨나요?", dl_sub:"Windows용 AutoSlice를 무료로 다운로드하고 오늘 바로 Bambu 모델 변환을 시작하세요.",
    dl_btn:"Windows용 다운로드", dl_login_lnk:"이미 계정이 있으신가요? 로그인",
    dl_specs:"Windows 10/11 · 64-bit · ~180 MB · 자동 업데이트 포함", dl_soon:"Linux & iOS — 곧 출시",
    foot_brand:"Bambu 3MF 파일을 Anycubic 프린트 프로필로 변환하는 가장 스마트한 방법.",
    foot_product:"제품", foot_account:"계정", foot_more:"더 보기",
    foot_features:"기능", foot_how:"사용 방법", foot_pricing:"가격",
    foot_register:"회원가입", foot_login:"로그인", foot_support:"지원", foot_privacy:"개인정보", foot_terms:"약관",
    foot_copy:"Quiandro Segier & Yoni Smets 제작.",
    rev_h2:"사용자 리뷰", rev_sub:"3D 프린팅 애호가들이 AutoSlice에 대해 말하는 것.",
    rev_based:"기반", rev_count_suffix:"+ 리뷰", rev_write:"리뷰 작성",
    modal_title:"리뷰 작성", modal_name_lbl:"이름", modal_name_ph:"이름을 입력하세요…",
    modal_rating_lbl:"평점", modal_text_lbl:"리뷰", modal_text_ph:"AutoSlice 경험을 공유하세요…", modal_submit:"리뷰 게시",
    blog_badge:"블로그", blog_h2:"최신 소식", blog_sub:"AutoSlice와 3D 프린팅에 관한 팁, 튜토리얼 및 업데이트.", blog_read:"더 읽기 →",
    blog1_cat:"튜토리얼", blog1_title:"Bambu를 Anycubic으로 변환하기: 단계별 가이드", blog1_date:"2026년 4월 15일",
    blog1_excerpt:"Bambu Studio 또는 MakerWorld의 .3mf 파일을 1분 이내에 Anycubic 프린트 프로필로 변환하는 방법을 알아보세요.",
    blog2_cat:"가이드", blog2_title:"ACE Pro 2와 AutoSlice로 멀티컬러 프린팅", blog2_date:"2026년 4월 3일",
    blog2_excerpt:"완벽한 멀티컬러 프린팅을 위한 8개 색상 슬롯 설정, 필라멘트 교체, 플러시 볼륨에 관한 모든 것.",
    blog3_cat:"업데이트", blog3_title:"AutoSlice 1.5: AI 분석, 프리셋 등", blog3_date:"2026년 3월 20일",
    blog3_excerpt:"버전 1.5의 모든 새 기능 개요: 개선된 AI 분석, 내보낼 수 있는 프리셋, 새 커뮤니티 페이지.",
  },
};

type LT = typeof LANDING_T.nl;

function useLT(): LT {
  const { lang } = useLang();
  return (LANDING_T as Record<string, LT>)[lang] ?? LANDING_T.nl;
}

// ── Scroll-fade hook ─────────────────────────────────────────────────────────
function useFadeIn() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } }, { threshold: 0.12 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, visible };
}

// ── Reusable atoms ───────────────────────────────────────────────────────────
function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-semibold uppercase tracking-[0.1em]"
      style={{ borderColor: "rgba(224,36,36,0.3)", background: "rgba(224,36,36,0.08)", color: BRAND }}>
      {children}
    </span>
  );
}

function GradBtn({ href, children, outline, download }: { href: string; children: React.ReactNode; outline?: boolean; download?: boolean }) {
  const base = "inline-flex items-center gap-2 px-6 h-11 rounded-xl font-semibold text-sm transition-all duration-150 active:scale-[0.97]";
  const isExternal = href.startsWith("http");
  const extraProps = isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {};
  if (outline) return (
    <Link href={href} {...extraProps} className={`${base} border text-zinc-300 hover:text-white hover:bg-white/[0.05]`}
      style={{ borderColor: "rgba(255,255,255,0.12)" }}>
      {children}
    </Link>
  );
  return (
    <Link href={href} {...extraProps} className={`${base} text-white shadow-[0_0_24px_rgba(224,36,36,0.4)] hover:shadow-[0_0_36px_rgba(224,36,36,0.6)] hover:-translate-y-0.5`}
      style={{ background: "linear-gradient(135deg,#e02424,#b81c1c)" }}>
      {children}
    </Link>
  );
}

// ── Review types & seed data ─────────────────────────────────────────────────
interface Review {
  id: string;
  name: string;
  rating: number;
  text: string;
  date: string;
}

const INITIAL_REVIEWS: Review[] = [
  {
    id: "1",
    name: "Jeroen V.",
    rating: 5,
    text: "Super handige tool! Bespaart me echt uren werk. Mijn multicolor prints komen er perfect uit.",
    date: "15 april 2026",
  },
  {
    id: "2",
    name: "Sarah M.",
    rating: 4,
    text: "Eindelijk een manier om Bambu prints direct naar de Kobra 3 te converteren. Werkt perfect!",
    date: "11 april 2026",
  },
  {
    id: "3",
    name: "Thomas B.",
    rating: 5,
    text: "De AI-analyse is ongelofelijk nauwkeurig. Minder mislukte prints, meer tijd voor ontwerpen.",
    date: "3 april 2026",
  },
  {
    id: "4",
    name: "Lisa K.",
    rating: 4,
    text: "Preset systeem is top — ik sla al mijn printerprofielen op en laad ze in één klik.",
    date: "28 maart 2026",
  },
  {
    id: "5",
    name: "Max R.",
    rating: 5,
    text: "Automatische oriëntatie-optimalisatie heeft mij al meerdere mislukte prints bespaard. Aanrader!",
    date: "19 maart 2026",
  },
  {
    id: "6",
    name: "Emma D.",
    rating: 4,
    text: "Eenvoudig in gebruik, mooie interface en de conversie gaat razendsnel. Echt handig!",
    date: "10 maart 2026",
  },
];

// ── Star rating atom ──────────────────────────────────────────────────────────
function StarRating({ rating, max = 5, size = "sm" }: { rating: number; max?: number; size?: "xs" | "sm" | "md" }) {
  const cls = size === "xs" ? "w-3 h-3" : size === "sm" ? "w-4 h-4" : "w-6 h-6";
  const STAR = "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z";
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: max }, (_, i) => (
        <svg key={i} className={cls} viewBox="0 0 20 20"
          fill={i < rating ? "#FFD700" : "none"}
          stroke={i < rating ? "#FFD700" : "#4b5563"}
          strokeWidth={i < rating ? 0 : 1.5}>
          <path d={STAR} />
        </svg>
      ))}
    </div>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────
function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const { lang, setLang } = useLang();
  const lt = useLT();

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <header className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${scrolled ? "border-b" : ""}`}
      style={{ background: scrolled ? "rgba(5,5,8,0.85)" : "transparent", backdropFilter: scrolled ? "blur(16px)" : "none", borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">

        {/* Logo */}
        <Link href="/landing" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center transition-shadow duration-200 group-hover:shadow-[0_0_20px_rgba(224,36,36,0.5)]"
            style={{ background: BRAND, boxShadow: "0 0 14px rgba(224,36,36,0.35)" }}>
            <svg viewBox="0 0 24 24" fill="white" className="w-4 h-4">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span className="text-[15px] font-bold text-white tracking-tight">
            Auto<span style={{ color: BRAND }}>Slice</span>
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-7">
          {([[`#features`,lt.nav_features],[`#how`,lt.nav_how],[`#pricing`,lt.nav_pricing]] as [string,string][]).map(([href,label]) => (
            <a key={href} href={href} className="text-sm text-zinc-500 hover:text-white transition-colors duration-150">{label}</a>
          ))}
        </nav>

        {/* Language switcher */}
        <div className="hidden md:flex items-center gap-0.5 bg-white/5 border border-white/[0.08] rounded-full px-2 py-1.5 backdrop-blur-sm">
          {LANGS.map(({ code, label }) => (
            <button key={code} onClick={() => setLang(code as Lang)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-150 ${
                lang === code ? "bg-brand text-white shadow-[0_0_10px_rgba(224,36,36,0.4)]" : "text-zinc-500 hover:text-zinc-300"
              }`}>
              {label}
            </button>
          ))}
        </div>

        {/* Desktop CTA */}
        <div className="hidden md:flex items-center gap-3">
          <Link href="/login" className="text-sm text-zinc-400 hover:text-white transition-colors">{lt.nav_login}</Link>
          <GradBtn href="/register">{lt.nav_cta}</GradBtn>
        </div>

        {/* Mobile hamburger */}
        <button onClick={() => setOpen(!open)} className="md:hidden text-zinc-400 hover:text-white transition-colors">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={open ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t px-6 py-4 space-y-3" style={{ background: "rgba(5,5,8,0.95)", borderColor: "rgba(255,255,255,0.07)" }}>
          {([[`#features`,lt.nav_features],[`#how`,lt.nav_how],[`#pricing`,lt.nav_pricing]] as [string,string][]).map(([href,label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)} className="block text-sm text-zinc-400 hover:text-white py-1 transition-colors">{label}</a>
          ))}
          {/* Mobile language switcher */}
          <div className="flex items-center gap-0.5 bg-white/5 border border-white/[0.08] rounded-full px-2 py-1.5 w-fit">
            {LANGS.map(({ code, label }) => (
              <button key={code} onClick={() => setLang(code as Lang)}
                className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-150 ${
                  lang === code ? "bg-brand text-white shadow-[0_0_10px_rgba(224,36,36,0.4)]" : "text-zinc-500 hover:text-zinc-300"
                }`}>
                {label}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-2 pt-2 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
            <Link href="/login" className="text-sm text-zinc-400 py-1">{lt.nav_login}</Link>
            <GradBtn href="/register">{lt.nav_cta}</GradBtn>
          </div>
        </div>
      )}
    </header>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function Hero() {
  const lt = useLT();
  return (
    <section className="relative min-h-screen flex items-center pt-24 pb-16 overflow-hidden">

      {/* Background glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] rounded-full opacity-30"
          style={{ background: "radial-gradient(ellipse, rgba(224,36,36,0.18) 0%, transparent 70%)" }} />
        <div className="absolute bottom-0 right-0 w-[600px] h-[400px] opacity-20"
          style={{ background: "radial-gradient(ellipse at right bottom, rgba(224,36,36,0.15) 0%, transparent 70%)" }} />
      </div>

      <div className="relative max-w-6xl mx-auto px-6 w-full">
        <div className="flex flex-col lg:flex-row items-center gap-16">

          {/* Left: copy */}
          <div className="flex-1 text-center lg:text-left">
            <div className="mb-6">
              <Badge>
                <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4"/></svg>
                {lt.hero_badge}
              </Badge>
            </div>

            <h1 className="text-5xl lg:text-[62px] font-extrabold text-white leading-[1.05] tracking-tight mb-6">
              {lt.hero_h1a}{" "}
              <span className="relative">
                <span style={{ color: BRAND }}>Anycubic</span>
                <svg className="absolute -bottom-2 left-0 w-full" viewBox="0 0 200 8" fill="none">
                  <path d="M2 6 Q100 2 198 6" stroke={BRAND} strokeWidth="2.5" strokeLinecap="round" opacity="0.5"/>
                </svg>
              </span>
              {" "}{lt.hero_h1b}
            </h1>

            <p className="text-lg text-zinc-400 leading-relaxed mb-8 max-w-lg mx-auto lg:mx-0">
              {lt.hero_sub}
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-3 justify-center lg:justify-start">
              <a href="/api/download" download
                className="inline-flex items-center gap-2.5 px-6 h-11 rounded-xl font-semibold text-sm text-white transition-all duration-150 active:scale-[0.97] hover:bg-white/[0.08] hover:-translate-y-0.5"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.18)" }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                {lt.hero_dl}
              </a>
              <GradBtn href="#features" outline>
                {lt.hero_feat_btn}
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                </svg>
              </GradBtn>
            </div>

            <p className="mt-3 text-xs text-zinc-600">{lt.hero_free}</p>
            <p className="mt-1 text-xs text-zinc-700">{lt.hero_soon}</p>

            {/* Mini star rating */}
            <div className="mt-5 flex items-center gap-2.5 justify-center lg:justify-start">
              <StarRating rating={5} size="sm" />
              <span className="text-sm font-bold text-white">4,3/5</span>
              <span className="text-xs text-zinc-500">{lt.hero_based}</span>
            </div>
          </div>

          {/* Right: App window mockup */}
          <div className="flex-1 w-full max-w-[600px]">
            <AppWindowMockup />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── App window CSS mockup ─────────────────────────────────────────────────────
function AppWindowMockup() {
  return (
    <div className="relative w-full rounded-2xl overflow-hidden shadow-[0_32px_80px_rgba(0,0,0,0.7),0_0_0_1px_rgba(255,255,255,0.06)]">
      {/* Outer glow */}
      <div className="absolute -inset-[1px] rounded-2xl pointer-events-none"
        style={{ background: "linear-gradient(135deg, rgba(224,36,36,0.2), transparent 50%)", zIndex: -1 }} />

      {/* Title bar */}
      <div className="flex items-center justify-between px-4 h-9 shrink-0 select-none"
        style={{ background: "#030305", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-xl flex items-center justify-center" style={{ background: BRAND }}>
            <svg viewBox="0 0 24 24" fill="white" className="w-1.5 h-1.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
          </div>
          <span className="text-[10px] font-bold tracking-widest" style={{ color: "rgba(255,255,255,0.25)" }}>AUTOSLICE</span>
        </div>
        <div className="flex items-center gap-1.5">
          {["rgba(255,255,255,0.08)","rgba(255,255,255,0.08)","rgba(224,36,36,0.4)"].map((c,i) => (
            <div key={i} className="w-3 h-3 rounded-[3px]" style={{ background: c }} />
          ))}
        </div>
      </div>

      {/* App body */}
      <div className="flex h-[380px]" style={{ background: BG }}>

        {/* Sidebar */}
        <div className="w-[52px] shrink-0 flex flex-col items-center py-4 gap-1"
          style={{ background: "#07070b", borderRight: "1px solid rgba(255,255,255,0.05)" }}>
          {[
            { icon: "M13 10V3L4 14h7v7l9-11h-7z", active: true },
            { icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z", active: false },
            { icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z", active: false },
            { icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z", active: false },
          ].map((item, i) => (
            <div key={i} className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: item.active ? "rgba(224,36,36,0.16)" : "transparent" }}>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                style={{ color: item.active ? BRAND : "rgba(255,255,255,0.2)" }}>
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon}/>
              </svg>
            </div>
          ))}
        </div>

        {/* Main content */}
        <div className="flex-1 flex flex-col p-4 overflow-hidden">

          {/* Top bar */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-bold text-white">3MF Converter</div>
              <div className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>Converteer Bambu naar Anycubic</div>
            </div>
            {/* Step pills */}
            <div className="flex items-center gap-1.5">
              {["Instellingen","Bestand","Genereren"].map((s,i) => (
                <div key={i} className="flex items-center gap-1">
                  <div className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${i === 0 ? "text-white" : "text-zinc-700"}`}
                    style={{ background: i === 0 ? "rgba(224,36,36,0.2)" : "rgba(255,255,255,0.04)", border: `1px solid ${i===0?"rgba(224,36,36,0.35)":"rgba(255,255,255,0.07)"}` }}>
                    {i+1} {s}
                  </div>
                  {i < 2 && <div className="w-3 h-px" style={{ background: "rgba(255,255,255,0.1)" }}/>}
                </div>
              ))}
            </div>
          </div>

          {/* Upload zone */}
          <div className="rounded-xl border-2 border-dashed flex flex-col items-center justify-center py-7 mb-3"
            style={{ borderColor: "rgba(224,36,36,0.3)", background: "rgba(224,36,36,0.03)" }}>
            <div className="w-8 h-8 rounded-full flex items-center justify-center mb-2"
              style={{ background: "rgba(224,36,36,0.1)", border: "1px solid rgba(224,36,36,0.25)" }}>
              <svg className="w-4 h-4" fill="none" stroke={BRAND} viewBox="0 0 24 24" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
              </svg>
            </div>
            <div className="text-xs font-semibold text-white mb-0.5">Sleep je .3mf bestand hier</div>
            <div className="text-[9px]" style={{ color: "rgba(255,255,255,0.3)" }}>of klik om te bladeren</div>
          </div>

          {/* Settings row */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Printer", value: "Kobra 3 Combo" },
              { label: "Filament", value: "PLA · 0.4mm" },
              { label: "Buildplaat", value: "Textured PEI" },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg px-2.5 py-2"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <div className="text-[8px] font-semibold uppercase tracking-wider mb-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>{label}</div>
                <div className="text-[10px] font-medium text-white truncate">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Animated glow bar at bottom */}
      <div className="h-[2px]" style={{ background: `linear-gradient(90deg, transparent, ${BRAND}, transparent)` }}/>
    </div>
  );
}

// ── Trust / compatibility bar ─────────────────────────────────────────────────
function TrustBar() {
  const lt = useLT();
  const brands = ["Bambu Lab X1C","MakerWorld","Anycubic Kobra","ACE Pro","Kobra 3 Max","MakerBot"];
  return (
    <div className="border-y py-5" style={{ borderColor: "rgba(255,255,255,0.05)", background: "rgba(255,255,255,0.015)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <p className="text-center text-[10px] text-zinc-600 uppercase tracking-[0.18em] font-semibold mb-5">
          {lt.trust}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
          {brands.map((b) => (
            <span key={b} className="text-[13px] font-semibold" style={{ color: "rgba(255,255,255,0.2)" }}>{b}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Features ──────────────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: "M13 10V3L4 14h7v7l9-11h-7z",
    title: "Directe 3MF conversie",
    desc: "Upload elk Bambu of MakerWorld .3mf bestand en ontvang binnen seconden een kant-en-klaar Anycubic printprofiel.",
    accent: BRAND,
  },
  {
    icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    title: "AI-model analyse",
    desc: "AutoSlice analyseert automatisch overhangen, bruggen, dunne wanden en printbaarheid — en past instellingen aan.",
    accent: "#8b5cf6",
  },
  {
    icon: "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    title: "Multicolor support",
    desc: "Volledige ondersteuning voor ACE Pro en ACE Pro 2 met tot 8 kleurslots, filamentwissel en flush-instellingen.",
    accent: "#06b6d4",
  },
  {
    icon: "M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01",
    title: "Preset systeem",
    desc: "Sla je printerinstellingen op als preset, hernoem ze, stel een standaard in en importeer/exporteer als JSON.",
    accent: "#f59e0b",
  },
  {
    icon: "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
    title: "Automatische updates",
    desc: "AutoSlice controleert op nieuwe versies bij elke start. Updates worden op de achtergrond gedownload en geïnstalleerd.",
    accent: "#10b981",
  },
  {
    icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
    title: "Veilig & privé",
    desc: "Alle verwerking gebeurt lokaal op jouw machine. Geen bestanden naar de cloud. Jouw 3D-modellen blijven van jou.",
    accent: "#f43f5e",
  },
];

function Features() {
  const { ref, visible } = useFadeIn();
  const lt = useLT();
  const titles = [lt.feat1_t, lt.feat2_t, lt.feat3_t, lt.feat4_t, lt.feat5_t, lt.feat6_t];
  const descs  = [lt.feat1_d, lt.feat2_d, lt.feat3_d, lt.feat4_d, lt.feat5_d, lt.feat6_d];
  return (
    <section id="features" className="py-28" ref={ref}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <Badge>{lt.feat_badge}</Badge>
          <h2 className="text-4xl font-extrabold text-white mt-5 mb-4 tracking-tight">
            {lt.feat_h2}
          </h2>
          <p className="text-zinc-500 text-lg max-w-xl mx-auto">
            {lt.feat_sub}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <FeatureCard key={i} {...f} title={titles[i]} desc={descs[i]} delay={i * 80} visible={visible} />
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureCard({ icon, title, desc, accent, delay, visible }: typeof FEATURES[0] & { delay: number; visible: boolean }) {
  return (
    <div className={`group rounded-2xl p-6 border transition-all duration-700 hover:-translate-y-1`}
      style={{
        background: "rgba(255,255,255,0.02)",
        borderColor: "rgba(255,255,255,0.06)",
        transitionDelay: `${delay}ms`,
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(20px)",
      }}>
      <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-all duration-200 group-hover:scale-110"
        style={{ background: `${accent}18`, border: `1px solid ${accent}30` }}>
        <svg className="w-5 h-5" fill="none" stroke={accent} strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d={icon}/>
        </svg>
      </div>
      <h3 className="text-[15px] font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-zinc-500 leading-relaxed">{desc}</p>
    </div>
  );
}

// ── How it works ──────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Upload je bestand", desc: "Sleep een .3mf bestand van Bambu Studio of MakerWorld in het uploadvenster." },
  { n: "02", title: "AI analyseert het model", desc: "AutoSlice berekent printbaarheid, detecteert overhangen, optimaliseert oriëntatie en kiest de beste instellingen." },
  { n: "03", title: "Download en print", desc: "Ontvang een geoptimaliseerd .3mf profiel voor jouw Anycubic printer. Direct starten met printen." },
];

function HowItWorks() {
  const { ref, visible } = useFadeIn();
  const lt = useLT();
  const steps = [
    { n: "01", title: lt.step1_t, desc: lt.step1_d },
    { n: "02", title: lt.step2_t, desc: lt.step2_d },
    { n: "03", title: lt.step3_t, desc: lt.step3_d },
  ];
  return (
    <section id="how" className="py-28" ref={ref}
      style={{ background: "linear-gradient(180deg, transparent, rgba(224,36,36,0.02) 50%, transparent)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <Badge>{lt.how_badge}</Badge>
          <h2 className="text-4xl font-extrabold text-white mt-5 mb-4 tracking-tight">
            {lt.how_h2}
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {steps.map((s, i) => (
            <div key={s.n}
              className="relative transition-all duration-700"
              style={{ transitionDelay: `${i * 120}ms`, opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(24px)" }}>
              {/* Connector line */}
              {i < 2 && (
                <div className="hidden lg:block absolute top-7 left-full w-full h-px -translate-x-8 -translate-y-0"
                  style={{ background: "linear-gradient(90deg, rgba(224,36,36,0.3), transparent)" }}/>
              )}

              <div className="rounded-2xl p-7 h-full border"
                style={{ background: "rgba(255,255,255,0.02)", borderColor: "rgba(255,255,255,0.06)" }}>
                <div className="text-5xl font-black mb-5 leading-none"
                  style={{ background: `linear-gradient(135deg, ${BRAND}, rgba(224,36,36,0.3))`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                  {s.n}
                </div>
                <h3 className="text-lg font-bold text-white mb-3">{s.title}</h3>
                <p className="text-sm text-zinc-500 leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Screenshot / app preview ──────────────────────────────────────────────────
function AppPreview() {
  const { ref, visible } = useFadeIn();
  const lt = useLT();
  return (
    <section className="py-28 overflow-hidden" ref={ref}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <div className="flex flex-col lg:flex-row items-center gap-16">

            {/* Left: text */}
            <div className="flex-1 lg:max-w-[420px]">
              <Badge>{lt.prev_badge}</Badge>
              <h2 className="text-4xl font-extrabold text-white mt-5 mb-5 tracking-tight leading-tight">
                {lt.prev_h2}
              </h2>
              <p className="text-zinc-500 leading-relaxed mb-8">
                {lt.prev_sub}
              </p>

              <div className="space-y-4">
                {[
                  { label: lt.prev_score,       color: "#10b981", val: 88 },
                  { label: lt.prev_overhang,    color: BRAND,    val: 23 },
                  { label: lt.prev_support_lbl, color: "#f59e0b", val: 45 },
                ].map(({ label, color, val }) => (
                  <div key={label}>
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-zinc-400 font-medium">{label}</span>
                      <span className="font-bold" style={{ color }}>{val}%</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                      <div className="h-full rounded-full transition-all duration-1000"
                        style={{ width: visible ? `${val}%` : "0%", background: color, transitionDelay: "400ms" }}/>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: analysis mockup */}
            <div className="flex-1 w-full max-w-[520px]">
              <AnalysisMockup />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AnalysisMockup() {
  const items = [
    { icon: "M9 12l2 2 4-4", label: "Mesh is waterdicht", ok: true },
    { icon: "M12 9v2m0 4h.01", label: "Matige overhangen gedetecteerd", ok: false },
    { icon: "M9 12l2 2 4-4", label: "Brim aanbevolen", ok: true },
    { icon: "M9 12l2 2 4-4", label: "Oriëntatie geoptimaliseerd (−34% support)", ok: true },
    { icon: "M12 9v2m0 4h.01", label: "Dunne wanden: 1 zone", ok: false },
  ];
  return (
    <div className="rounded-2xl overflow-hidden shadow-[0_24px_60px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.06)]">
      {/* Window chrome */}
      <div className="px-4 h-9 flex items-center gap-2" style={{ background: "#030305", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        {[BRAND,"rgba(255,255,255,0.08)","rgba(255,255,255,0.08)"].map((c,i) => (
          <div key={i} className="w-2.5 h-2.5 rounded-full" style={{ background: c }}/>
        ))}
        <span className="ml-2 text-[10px] font-medium" style={{ color: "rgba(255,255,255,0.2)" }}>Analyse resultaten — vase_mode_pot.3mf</span>
      </div>

      <div className="p-5" style={{ background: SURFACE }}>
        {/* Score ring */}
        <div className="flex items-center gap-5 mb-5 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="relative w-16 h-16 shrink-0">
            <svg viewBox="0 0 36 36" className="w-16 h-16 -rotate-90">
              <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3"/>
              <circle cx="18" cy="18" r="14" fill="none" stroke="#10b981" strokeWidth="3"
                strokeDasharray="88 100" strokeLinecap="round"/>
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-black text-white">88</span>
            </div>
          </div>
          <div>
            <p className="text-[11px] text-zinc-500 uppercase tracking-wider font-semibold mb-0.5">Printbaarheid</p>
            <p className="text-xl font-black" style={{ color: "#10b981" }}>Goed</p>
            <p className="text-[11px] text-zinc-600 mt-0.5">4 van 5 criteria geslaagd</p>
          </div>
        </div>

        {/* Check items */}
        <div className="space-y-2">
          {items.map(({ icon, label, ok }) => (
            <div key={label} className="flex items-center gap-3 px-3 py-2 rounded-lg"
              style={{ background: ok ? "rgba(16,185,129,0.05)" : "rgba(224,36,36,0.05)", border: `1px solid ${ok ? "rgba(16,185,129,0.12)" : "rgba(224,36,36,0.12)"}` }}>
              <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                style={{ background: ok ? "rgba(16,185,129,0.15)" : "rgba(224,36,36,0.15)" }}>
                <svg className="w-3 h-3" fill="none" stroke={ok ? "#10b981" : BRAND} strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={icon}/>
                </svg>
              </div>
              <span className="text-[12px] font-medium" style={{ color: ok ? "#a7f3d0" : "#fca5a5" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Multicolor showcase ───────────────────────────────────────────────────────
function MultiColorSection() {
  const { ref, visible } = useFadeIn();
  const lt = useLT();
  const colors = ["#e02424","#3b82f6","#10b981","#f59e0b","#8b5cf6","#f43f5e","#ffffff","#1a1a2e"];
  return (
    <section className="py-28" ref={ref}
      style={{ background: "linear-gradient(180deg, transparent, rgba(6,182,212,0.02) 50%, transparent)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`flex flex-col lg:flex-row items-center gap-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>

          {/* Left: color slot mockup */}
          <div className="flex-1 max-w-[480px] w-full">
            <div className="rounded-2xl p-6 border shadow-[0_24px_60px_rgba(0,0,0,0.5)]"
              style={{ background: SURFACE, borderColor: "rgba(255,255,255,0.07)" }}>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider">ACE Pro 2 — 8 slots</p>
                  <p className="text-[11px] text-zinc-600 mt-0.5">Dubbele unit actief</p>
                </div>
                <div className="px-2 py-1 rounded-full text-[9px] font-bold" style={{ background: "rgba(6,182,212,0.12)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.25)" }}>
                  ACTIEF
                </div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                {colors.map((c, i) => (
                  <div key={i} className="rounded-xl p-2.5 flex flex-col gap-2"
                    style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${c}30` }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] font-bold" style={{ color: "rgba(255,255,255,0.4)" }}>Slot {i+1}</span>
                      <div className="w-2 h-2 rounded-full" style={{ background: c, boxShadow: `0 0 5px ${c}80` }}/>
                    </div>
                    <div className="h-7 rounded-lg" style={{ background: c, boxShadow: `0 2px 10px ${c}40` }}/>
                    <div className="h-5 rounded text-[8px] font-medium flex items-center justify-center"
                      style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.5)" }}>
                      PLA
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: text */}
          <div className="flex-1">
            <Badge>{lt.multi_badge}</Badge>
            <h2 className="text-4xl font-extrabold text-white mt-5 mb-5 tracking-tight leading-tight">
              {lt.multi_h2a}<br/>{lt.multi_h2b}
            </h2>
            <p className="text-zinc-500 leading-relaxed mb-8">
              {lt.multi_sub}
            </p>
            <ul className="space-y-3">
              {[lt.multi_b1, lt.multi_b2, lt.multi_b3, lt.multi_b4].map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <div className="w-5 h-5 rounded-full flex items-center justify-center mt-0.5 shrink-0"
                    style={{ background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.25)" }}>
                    <svg className="w-2.5 h-2.5" fill="none" stroke="#06b6d4" strokeWidth={2.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                  </div>
                  <span className="text-sm text-zinc-400">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Pricing ───────────────────────────────────────────────────────────────────
const PLANS = [
  {
    name: "Starter",
    price: "Gratis",
    sub: "Voor altijd",
    color: "rgba(255,255,255,0.08)",
    border: "rgba(255,255,255,0.08)",
    badge: null,
    features: [
      "15 conversies per maand",
      "Basisprinter instellingen",
      "3 opgeslagen presets",
      "Community support",
      "Automatische updates",
    ],
    cta: "Gratis starten",
    ctaHref: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: "€7,99",
    sub: "per maand",
    color: "rgba(224,36,36,0.08)",
    border: "rgba(224,36,36,0.35)",
    badge: "Meest populair",
    features: [
      "Onbeperkte conversies",
      "AI-model analyse",
      "Onbeperkte presets",
      "Prioriteit support",
      "Geavanceerde oriëntatie-optimalisatie",
      "Import / export presets",
    ],
    cta: "Pro proberen",
    ctaHref: "/register",
    highlight: true,
  },
  {
    name: "Team",
    price: "€24,99",
    sub: "per maand",
    color: "rgba(139,92,246,0.06)",
    border: "rgba(139,92,246,0.25)",
    badge: null,
    features: [
      "Alles in Pro",
      "Tot 5 gebruikers",
      "Gedeelde presets",
      "Centraal gebruikersbeheer",
      "Prioriteit support",
    ],
    cta: "Contact opnemen",
    ctaHref: "/register",
    highlight: false,
  },
];

function Pricing() {
  const { ref, visible } = useFadeIn();
  const lt = useLT();
  const plans = [
    { name: lt.p0_name, price: lt.p0_price, sub: lt.p0_sub, color: "rgba(255,255,255,0.08)", border: "rgba(255,255,255,0.08)", badge: null,
      features: [lt.p0_f1, lt.p0_f2, lt.p0_f3, lt.p0_f4, lt.p0_f5], cta: lt.p0_cta, ctaHref: "/register", highlight: false },
    { name: lt.p1_name, price: lt.p1_price, sub: lt.p1_sub, color: "rgba(224,36,36,0.08)", border: "rgba(224,36,36,0.35)", badge: lt.price_popular,
      features: [lt.p1_f1, lt.p1_f2, lt.p1_f3, lt.p1_f4, lt.p1_f5, lt.p1_f6], cta: lt.p1_cta, ctaHref: "/register", highlight: true },
    { name: lt.p2_name, price: lt.p2_price, sub: lt.p2_sub, color: "rgba(139,92,246,0.06)", border: "rgba(139,92,246,0.25)", badge: null,
      features: [lt.p2_f1, lt.p2_f2, lt.p2_f3, lt.p2_f4, lt.p2_f5], cta: lt.p2_cta, ctaHref: "/register", highlight: false },
  ];
  return (
    <section id="pricing" className="py-28" ref={ref}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <Badge>{lt.price_badge}</Badge>
          <h2 className="text-4xl font-extrabold text-white mt-5 mb-4 tracking-tight">
            {lt.price_h2}
          </h2>
          <p className="text-zinc-500 text-lg max-w-md mx-auto">
            {lt.price_sub}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {plans.map((plan, i) => (
            <div key={plan.name}
              className={`relative rounded-2xl p-7 flex flex-col transition-all duration-700 ${plan.highlight ? "scale-[1.02]" : ""}`}
              style={{
                background: plan.color,
                border: `1px solid ${plan.border}`,
                boxShadow: plan.highlight ? "0 0 48px rgba(224,36,36,0.15)" : "none",
                transitionDelay: `${i * 80}ms`,
                opacity: visible ? 1 : 0,
                transform: visible ? (plan.highlight ? "scale(1.02)" : "translateY(0)") : "translateY(20px)",
              }}>

              {plan.badge && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[10px] font-bold text-white"
                  style={{ background: BRAND, boxShadow: "0 4px 16px rgba(224,36,36,0.4)" }}>
                  {plan.badge}
                </div>
              )}

              <div className="mb-7">
                <p className="text-sm font-bold text-zinc-300 mb-3">{plan.name}</p>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-4xl font-extrabold text-white">{plan.price}</span>
                  <span className="text-sm text-zinc-500">{plan.sub}</span>
                </div>
              </div>

              <ul className="space-y-3 flex-1 mb-8">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5">
                    <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" stroke={plan.highlight ? BRAND : "#6b7280"} strokeWidth={2.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                    <span className="text-sm text-zinc-400">{f}</span>
                  </li>
                ))}
              </ul>

              <Link href={plan.ctaHref}
                className="w-full flex items-center justify-center h-11 rounded-xl font-semibold text-sm transition-all duration-150 active:scale-[0.97]"
                style={plan.highlight
                  ? { background: "linear-gradient(135deg,#e02424,#b81c1c)", color: "#fff", boxShadow: "0 4px 20px rgba(224,36,36,0.4)" }
                  : { background: "rgba(255,255,255,0.05)", color: "#a1a1aa", border: "1px solid rgba(255,255,255,0.08)" }}>
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Download CTA ──────────────────────────────────────────────────────────────
function DownloadCTA() {
  const { ref, visible } = useFadeIn();
  const lt = useLT();
  return (
    <section ref={ref} className="py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div className={`relative rounded-3xl overflow-hidden p-14 text-center transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}
          style={{ background: "linear-gradient(135deg, rgba(224,36,36,0.12) 0%, rgba(224,36,36,0.04) 60%, rgba(255,255,255,0.02) 100%)", border: "1px solid rgba(224,36,36,0.2)" }}>

          {/* BG glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] pointer-events-none"
            style={{ background: "radial-gradient(ellipse, rgba(224,36,36,0.15) 0%, transparent 70%)" }}/>

          <div className="relative">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
              style={{ background: BRAND, boxShadow: "0 0 40px rgba(224,36,36,0.5)" }}>
              <svg viewBox="0 0 24 24" fill="white" className="w-8 h-8">
                <path d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <h2 className="text-4xl font-extrabold text-white mb-4 tracking-tight">
              {lt.dl_h2}
            </h2>
            <p className="text-zinc-400 text-lg mb-8 max-w-lg mx-auto">
              {lt.dl_sub}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a href="/api/download" download
                className="inline-flex items-center gap-2.5 px-6 h-11 rounded-xl font-semibold text-sm text-white transition-all duration-150 active:scale-[0.97] hover:bg-white/[0.08] hover:-translate-y-0.5"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.18)" }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                {lt.dl_btn}
              </a>
              <GradBtn href="/login" outline>{lt.dl_login_lnk}</GradBtn>
            </div>
            <p className="mt-4 text-xs text-zinc-600">{lt.dl_specs}</p>
            <p className="mt-1 text-xs text-zinc-700">{lt.dl_soon}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
function LandingFooter() {
  const lt = useLT();
  return (
    <footer className="border-t py-14" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex flex-col lg:flex-row gap-12 mb-10">

          {/* Brand */}
          <div className="lg:w-[260px] shrink-0">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: BRAND }}>
                <svg viewBox="0 0 24 24" fill="white" className="w-3.5 h-3.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
              </div>
              <span className="font-bold text-white">Auto<span style={{ color: BRAND }}>Slice</span></span>
            </div>
            <p className="text-sm text-zinc-600 leading-relaxed">{lt.foot_brand}</p>
          </div>

          {/* Links */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-10 flex-1">
            {[
              { heading: lt.foot_product, items: [["#features",lt.foot_features],["#how",lt.foot_how],["#pricing",lt.foot_pricing]] },
              { heading: lt.foot_account, items: [["/register",lt.foot_register],["/login",lt.foot_login]] },
              { heading: lt.foot_more,    items: [["mailto:support@autoslice.be",lt.foot_support],["https://github.com/quiandrosegier96-coder/autoslice","GitHub"]] },
            ].map(({ heading, items }) => (
              <div key={heading}>
                <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-4">{heading}</p>
                <ul className="space-y-2.5">
                  {items.map(([href, label]) => (
                    <li key={label}>
                      <a href={href} className="text-sm text-zinc-600 hover:text-zinc-300 transition-colors">{label}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-8 border-t text-xs text-zinc-700"
          style={{ borderColor: "rgba(255,255,255,0.05)" }}>
          <p>© {new Date().getFullYear()} AutoSlice. {lt.foot_copy}</p>
          <div className="flex items-center gap-5">
            <a href="#" className="hover:text-zinc-400 transition-colors">{lt.foot_privacy}</a>
            <a href="#" className="hover:text-zinc-400 transition-colors">{lt.foot_terms}</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Review modal ─────────────────────────────────────────────────────────────
function ReviewModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (r: Review) => void }) {
  const lt = useLT();
  const [name, setName]             = useState("");
  const [rating, setRating]         = useState(5);
  const [text, setText]             = useState("");
  const [hoverRating, setHoverRating] = useState(0);
  const STAR = "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !text.trim()) return;
    const now = new Date();
    onSubmit({
      id: `${Date.now()}-${Math.random()}`,
      name: name.trim(),
      rating,
      text: text.trim(),
      date: now.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" }),
    });
  }

  const active = hoverRating || rating;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-md rounded-2xl p-7 relative"
        style={{
          background: "#0c0c10",
          border: "1px solid rgba(255,255,255,0.1)",
          boxShadow: "0 32px_80px rgba(0,0,0,0.6)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white">{lt.modal_title}</h3>
          <button onClick={onClose} className="text-zinc-600 hover:text-zinc-300 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div>
            <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-2">
              {lt.modal_name_lbl}
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={lt.modal_name_ph}
              style={{
                padding: "10px 14px",
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#e4e4e8",
                borderRadius: "12px",
                width: "100%",
                fontSize: "14px",
                outline: "none",
              }}
            />
          </div>

          {/* Star rating selector */}
          <div>
            <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-3">
              {lt.modal_rating_lbl}
            </label>
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  onClick={() => setRating(star)}
                  className="transition-transform hover:scale-110"
                >
                  <svg className="w-8 h-8" viewBox="0 0 20 20"
                    fill={active >= star ? "#FFD700" : "none"}
                    stroke={active >= star ? "#FFD700" : "#4b5563"}
                    strokeWidth={active >= star ? 0 : 1.5}>
                    <path d={STAR} />
                  </svg>
                </button>
              ))}
              <span className="text-sm text-zinc-400 ml-1 tabular-nums">{active}/5</span>
            </div>
          </div>

          {/* Review text */}
          <div>
            <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-2">
              {lt.modal_text_lbl}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={lt.modal_text_ph}
              rows={4}
              style={{
                padding: "10px 14px",
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#e4e4e8",
                borderRadius: "12px",
                width: "100%",
                fontSize: "14px",
                outline: "none",
                resize: "none",
                fontFamily: "inherit",
              }}
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!name.trim() || !text.trim()}
            className="w-full h-11 rounded-xl font-semibold text-sm text-white transition-all duration-150
                       disabled:opacity-40 disabled:cursor-not-allowed hover:-translate-y-0.5"
            style={{
              background: "linear-gradient(135deg,#e02424,#b81c1c)",
              boxShadow: "0 0 20px rgba(224,36,36,0.35)",
            }}
          >
            {lt.modal_submit}
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Review section ────────────────────────────────────────────────────────────
// Always visible — no opacity-0 or IntersectionObserver gate on the wrapper.
// Fetches /api/reviews/public on mount; falls back to 4.3 / 128 on any error.
function ReviewSection() {
  const lt = useLT();
  const [avgRating,   setAvgRating]   = useState(4.3);
  const [totalCount,  setTotalCount]  = useState(128);
  const [reviews,     setReviews]     = useState<Review[]>(INITIAL_REVIEWS);
  const [showModal,   setShowModal]   = useState(false);

  // Debug marker — confirms this component actually mounted
  console.log("ReviewSection rendered");

  useEffect(() => {
    fetch("/api/reviews/public")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setAvgRating(data.average_rating ?? 4.3);
        setTotalCount(data.total_reviews  ?? 128);
        if (Array.isArray(data.reviews) && data.reviews.length > 0) {
          setReviews(
            data.reviews.map((r: { id: number; name: string; rating: number; text: string; created_at: string }) => ({
              id:     String(r.id),
              name:   r.name,
              rating: r.rating,
              text:   r.text,
              date:   new Date(r.created_at).toLocaleDateString("nl-NL", {
                day: "numeric", month: "long", year: "numeric",
              }),
            }))
          );
        }
      })
      .catch(() => {
        // Network error — keep fallback values already in state
      });
  }, []);

  const displayReviews = reviews.length > 0 ? reviews : INITIAL_REVIEWS;
  const fullStars      = Math.round(avgRating);
  const avgDisplay     = avgRating.toFixed(1).replace(".", ",");

  return (
    <section
      id="reviews"
      style={{ paddingTop: "80px", paddingBottom: "80px" }}
    >
      <div style={{ maxWidth: "1152px", margin: "0 auto", padding: "0 24px" }}>

        {/* Prominent card — always rendered, always visible, red border */}
        <div style={{
          border:       "1px solid rgba(239,68,68,0.35)",
          borderRadius: "24px",
          background:   "rgba(12,12,16,0.95)",
          padding:      "48px 40px",
          boxShadow:    "0 0 60px rgba(224,36,36,0.07), 0 24px 60px rgba(0,0,0,0.5)",
        }}>

          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: "40px" }}>
            <Badge>Reviews</Badge>
            <h2 style={{
              fontSize: "clamp(28px,4vw,38px)", fontWeight: 800, color: "#ffffff",
              margin: "20px 0 12px", letterSpacing: "-0.02em",
            }}>
              {lt.rev_h2}
            </h2>
            <p style={{ color: "#71717a", fontSize: "16px" }}>
              {lt.rev_sub}
            </p>
          </div>

          {/* Summary row */}
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            gap: "10px", marginBottom: "40px",
          }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span style={{ fontSize: "72px", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
                {avgDisplay}
              </span>
              <span style={{ fontSize: "28px", color: "#71717a", fontWeight: 600 }}>/5</span>
            </div>
            <StarRating rating={fullStars} size="md" />
            <p style={{ color: "#71717a", fontSize: "14px", margin: 0 }}>
              {lt.rev_based} {totalCount}{lt.rev_count_suffix}
            </p>
            <button
              onClick={() => setShowModal(true)}
              style={{
                marginTop: "8px",
                display:        "inline-flex",
                alignItems:     "center",
                gap:            "8px",
                padding:        "0 20px",
                height:         "40px",
                borderRadius:   "12px",
                fontWeight:     600,
                fontSize:       "14px",
                color:          "#ffffff",
                background:     "linear-gradient(135deg,#e02424,#b81c1c)",
                boxShadow:      "0 0 24px rgba(224,36,36,0.35)",
                border:         "none",
                cursor:         "pointer",
                fontFamily:     "inherit",
              }}
            >
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              {lt.rev_write}
            </button>
          </div>

          {/* Review cards grid */}
          <div style={{
            display:               "grid",
            gridTemplateColumns:   "repeat(auto-fill, minmax(270px, 1fr))",
            gap:                   "16px",
          }}>
            {displayReviews.slice(0, 6).map((review) => (
              <div
                key={review.id}
                style={{
                  borderRadius: "16px",
                  border:       "1px solid rgba(255,255,255,0.07)",
                  background:   "rgba(255,255,255,0.025)",
                  padding:      "20px",
                  display:      "flex",
                  flexDirection:"column",
                  gap:          "12px",
                }}
              >
                <StarRating rating={review.rating} size="sm" />
                <p style={{ fontSize: "14px", color: "#d4d4d8", lineHeight: "1.65", flex: 1, margin: 0 }}>
                  &ldquo;{review.text}&rdquo;
                </p>
                <div style={{
                  display:        "flex",
                  alignItems:     "center",
                  justifyContent: "space-between",
                  paddingTop:     "12px",
                  borderTop:      "1px solid rgba(255,255,255,0.06)",
                }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "#a1a1aa" }}>— {review.name}</span>
                  <span style={{ fontSize: "11px", color: "#52525b" }}>{review.date}</span>
                </div>
              </div>
            ))}
          </div>

        </div>
      </div>

      {showModal && (
        <ReviewModal
          onClose={() => setShowModal(false)}
          onSubmit={(r) => {
            setReviews((prev) => [r, ...prev]);
            setShowModal(false);
          }}
        />
      )}
    </section>
  );
}

// ── Blog ─────────────────────────────────────────────────────────────────────
const BLOG_CAT_COLORS: Record<string, { bg: string; text: string }> = {
  Tutorial:   { bg: "rgba(59,130,246,0.12)",  text: "#60a5fa" },
  Tutoriel:   { bg: "rgba(59,130,246,0.12)",  text: "#60a5fa" },
  튜토리얼:   { bg: "rgba(59,130,246,0.12)",  text: "#60a5fa" },
  Guide:      { bg: "rgba(34,197,94,0.12)",   text: "#4ade80" },
  Handleiding:{ bg: "rgba(34,197,94,0.12)",   text: "#4ade80" },
  Anleitung:  { bg: "rgba(34,197,94,0.12)",   text: "#4ade80" },
  Guía:       { bg: "rgba(34,197,94,0.12)",   text: "#4ade80" },
  가이드:     { bg: "rgba(34,197,94,0.12)",   text: "#4ade80" },
  Update:     { bg: "rgba(251,191,36,0.12)",  text: "#fbbf24" },
  "Mise à jour":{ bg: "rgba(251,191,36,0.12)", text: "#fbbf24" },
  업데이트:   { bg: "rgba(251,191,36,0.12)",  text: "#fbbf24" },
  Actualización:{ bg: "rgba(251,191,36,0.12)", text: "#fbbf24" },
};

function BlogCard({ cat, title, date, excerpt, readLabel }: {
  cat: string; title: string; date: string; excerpt: string; readLabel: string;
}) {
  const color = BLOG_CAT_COLORS[cat] ?? { bg: "rgba(224,36,36,0.1)", text: BRAND };
  return (
    <div style={{
      background:   "rgba(255,255,255,0.025)",
      border:       "1px solid rgba(255,255,255,0.07)",
      borderRadius: "20px",
      padding:      "28px",
      display:      "flex",
      flexDirection:"column",
      gap:          "16px",
      transition:   "border-color 0.2s, transform 0.2s",
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(224,36,36,0.3)"; (e.currentTarget as HTMLDivElement).style.transform = "translateY(-3px)"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)"; (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)"; }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
        <span style={{
          display: "inline-block", padding: "3px 10px", borderRadius: "20px",
          fontSize: "11px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
          background: color.bg, color: color.text,
        }}>
          {cat}
        </span>
        <span style={{ fontSize: "12px", color: "#52525b" }}>{date}</span>
      </div>
      <h3 style={{ fontSize: "17px", fontWeight: 700, color: "#f4f4f5", lineHeight: 1.35, margin: 0 }}>
        {title}
      </h3>
      <p style={{ fontSize: "14px", color: "#71717a", lineHeight: 1.65, margin: 0, flex: 1 }}>
        {excerpt}
      </p>
      <span style={{ fontSize: "13px", fontWeight: 600, color: BRAND, marginTop: "4px" }}>
        {readLabel}
      </span>
    </div>
  );
}

function BlogSection() {
  const lt = useLT();
  const { ref, visible } = useFadeIn();
  const posts = [
    { cat: lt.blog1_cat, title: lt.blog1_title, date: lt.blog1_date, excerpt: lt.blog1_excerpt },
    { cat: lt.blog2_cat, title: lt.blog2_title, date: lt.blog2_date, excerpt: lt.blog2_excerpt },
    { cat: lt.blog3_cat, title: lt.blog3_title, date: lt.blog3_date, excerpt: lt.blog3_excerpt },
  ];
  return (
    <section ref={ref} style={{
      paddingTop: "80px", paddingBottom: "80px",
      opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(28px)",
      transition: "opacity 0.6s ease, transform 0.6s ease",
    }}>
      <div style={{ maxWidth: "1152px", margin: "0 auto", padding: "0 24px" }}>
        <div style={{ textAlign: "center", marginBottom: "48px" }}>
          <Badge>{lt.blog_badge}</Badge>
          <h2 style={{
            fontSize: "clamp(28px,4vw,40px)", fontWeight: 800, color: "#ffffff",
            margin: "20px 0 12px", letterSpacing: "-0.02em",
          }}>
            {lt.blog_h2}
          </h2>
          <p style={{ color: "#71717a", fontSize: "16px", maxWidth: "480px", margin: "0 auto" }}>
            {lt.blog_sub}
          </p>
        </div>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: "20px",
        }}>
          {posts.map((p, i) => (
            <BlogCard key={i} cat={p.cat} title={p.title} date={p.date} excerpt={p.excerpt} readLabel={lt.blog_read} />
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function LandingPage() {
  const [cfg, setCfg] = useState<SiteConfig | null>(null);
  useEffect(() => { getSiteConfig().then(setCfg).catch(() => {}); }, []);

  const show = (key: keyof SiteConfig) => cfg === null || cfg[key] !== false;

  return (
    <div className="min-h-screen overflow-x-hidden" style={{ background: BG, color: "#e4e4e8", fontFamily: "Inter, system-ui, sans-serif" }}>
      <Navbar />
      <Hero />
      {show("landing_trustbar")   && <TrustBar />}
      <ReviewSection />
      {show("landing_features")   && <Features />}
      {show("landing_how")        && <HowItWorks />}
      {show("landing_apppreview") && <AppPreview />}
      {show("landing_multicolor") && <MultiColorSection />}
      {show("landing_pricing")    && <Pricing />}
      {show("landing_blog")       && <BlogSection />}
      {show("landing_downloadcta")&& <DownloadCTA />}
      <LandingFooter />
    </div>
  );
}
