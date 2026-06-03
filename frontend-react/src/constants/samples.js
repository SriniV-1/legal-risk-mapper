const SAMPLES = {
  contract: {
    label: "SaaS Service Agreement",
    text: `SERVICE AGREEMENT\n\nThis Service Agreement is entered into between Acme Software Inc. ("Company") and the customer ("Client").\n\n1. SERVICES\nCompany provides software-as-a-service access. Services are provided AS-IS without any warranty of fitness for a particular purpose or merchantability.\n\n2. PAYMENT TERMS\nClient shall pay all invoices within Net 30 days. Unpaid balances accrue interest at 18% per annum. Company may unilaterally change pricing at any time with 7 days notice.\n\n3. AUTO-RENEWAL\nThis Agreement automatically renews annually unless cancelled in writing 90 days prior. Early termination fee of 75% of remaining contract value applies.\n\n4. LIABILITY\nIN NO EVENT SHALL COMPANY BE LIABLE FOR CONSEQUENTIAL, INCIDENTAL, OR PUNITIVE DAMAGES. Client shall indemnify and hold harmless Company from any third-party claims.\n\n5. DATA PROCESSING\nCompany collects personal data including usage metrics and user information. This data may be shared with third-party analytics providers. Company may sell aggregated user data.\n\n6. COMPLIANCE\nClient must comply with all applicable laws and regulations, including GDPR and export control requirements.\n\n7. MODIFICATIONS\nCompany reserves the right to modify these terms at its sole discretion at any time without notice.`,
  },
  privacy: {
    label: "Privacy Policy — DataFlow",
    text: `PRIVACY POLICY\n\nWe collect personally identifiable information (PII) including your name, email, location data, and browsing behavior. We track your activity across our platform using cookies and similar tracking technologies.\n\nYour personal data may be shared with third-party advertising partners for targeted marketing. We may sell your data to data brokers. We retain user information indefinitely unless you request deletion.\n\nOur facial recognition feature collects biometric data for personalization. We comply with applicable laws regarding children's data collection.\n\nWe may change this policy from time to time at our discretion without prior notice. Data may be transferred to countries without adequate GDPR protections.`,
  },
  startup: {
    label: "MediLink — Startup Terms",
    text: `MediLink connects patients with healthcare providers via a mobile app. We collect health records, including biometric data and medical history, for personalized care recommendations.\n\nRevenue Model:\n- Subscription fees from providers (automatic renewal, no early termination refund)\n- Sale of anonymized patient data to pharmaceutical companies\n- Licensing fee of $50,000 minimum commitment per enterprise client\n\nCompliance: We believe our platform is broadly compliant with applicable laws. HIPAA requirements will be addressed as we scale.\n\nRisk Factors: Users indemnify MediLink for any claims arising from health recommendations. Our liability is limited to fees paid. Platform provided as-is without warranty.`,
  },
  sneaky: {
    label: "Paraphrased Contract (semantic)",
    text: `Agreement for Platform Access\n\nThe receiving party agrees to make the disclosing party whole for any costs, expenses, or financial losses incurred as a result of any breach of this agreement, without limit as to amount or duration.\n\nUser-specific information gathered during your engagement with our platform may be transmitted to and retained on servers located in jurisdictions outside your country of residence where data protection standards may differ.\n\nThis agreement shall continue for successive annual terms unless either party provides written notice of non-renewal at least ninety days before the end of the then-current term.\n\nWe may gather facial geometry and voice patterns during authentication for improved security and personalization of the user experience.`,
  },
};

export default SAMPLES;
