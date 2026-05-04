"""
Training Data Generator for Risk Classifier
─────────────────────────────────────────────
Generates a labeled dataset for training a multi-label risk classifier.

Strategy:
  1. Use the 40 canonical clauses from risk_knowledge_base.py as seeds
  2. Define template banks for each risk category with variable slots
  3. Fill slots with random values to create diverse variations
  4. Generate neutral/negative examples from boilerplate contract language
  5. Optionally label real EDGAR chunks via the regex system

Output: data/training/risk_dataset.json
Format: [{"text": "...", "labels": {"Compliance Risk": "High", ...}, "source": "..."}]

Usage:
    python -m scripts.generate_training_data
"""
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ── Slot variables for template filling ──────────────────────────────────────

PARTIES = ["Provider", "Vendor", "Supplier", "Company", "Licensor", "Service Provider",
           "Contractor", "Platform"]
COUNTERPARTIES = ["Customer", "Client", "Licensee", "Subscriber", "User", "Buyer",
                  "Recipient", "End User"]
AMOUNTS = ["$500,000", "$1,000,000", "$100,000", "$2,000,000", "$250,000",
           "the total fees paid", "the aggregate fees paid under this Agreement",
           "two times the annual subscription fee"]
PERIODS = ["twelve (12) months", "six (6) months", "three (3) months",
           "twenty-four (24) months", "the preceding twelve months",
           "the initial term", "the prior calendar year"]
NOTICE_PERIODS = ["thirty (30) days", "sixty (60) days", "ninety (90) days",
                  "fourteen (14) days", "ten (10) business days"]
INTEREST_RATES = ["1.5%", "1%", "2%", "the lesser of 1.5% or the maximum rate",
                  "18% per annum", "the prime rate plus 2%"]
JURISDICTIONS = ["the State of Delaware", "New York", "California",
                 "England and Wales", "the State of Texas", "Singapore"]

def _r(choices):
    return random.choice(choices)


# ── Template banks per risk category ─────────────────────────────────────────

def _compliance_templates() -> List[dict]:
    """Generate Compliance Risk training examples."""
    templates = []

    # High severity
    high_templates = [
        lambda: f"{_r(COUNTERPARTIES)} shall comply with all applicable data protection laws, including the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and any similar regulations in force in the relevant jurisdiction.",
        lambda: f"{_r(COUNTERPARTIES)} is solely responsible for ensuring compliance with HIPAA and all regulations governing protected health information in connection with its use of the Services.",
        lambda: f"Each party shall comply with all applicable anti-bribery and anti-corruption laws, including the U.S. Foreign Corrupt Practices Act (FCPA) and the UK Bribery Act 2010.",
        lambda: f"{_r(COUNTERPARTIES)} must comply with all applicable laws, regulations, rules, and requirements in connection with its use of the Services, including without limitation all export control laws and economic sanctions regulations.",
        lambda: f"The Services may be subject to export control restrictions under the Export Administration Regulations (EAR) and the International Traffic in Arms Regulations (ITAR). {_r(COUNTERPARTIES)} shall not export or re-export any technical data or services in violation thereof.",
        lambda: f"{_r(COUNTERPARTIES)} represents and warrants that it shall comply with all applicable economic sanctions laws and regulations, including those administered by the Office of Foreign Assets Control (OFAC).",
        lambda: f"{_r(COUNTERPARTIES)} must obtain and maintain all licenses, permits, and regulatory approvals required for its use of the Services in each applicable jurisdiction.",
        lambda: f"The parties shall observe all laws, statutes, regulations, and administrative requirements applicable to the performance of their obligations under this Agreement.",
        lambda: f"{_r(COUNTERPARTIES)} shall ensure that its use of the Services complies with PCI-DSS requirements for the processing, storage, and transmission of payment card data.",
        lambda: f"Each party shall comply with all anti-money laundering laws and regulations, including the Bank Secrecy Act and applicable Know Your Customer requirements.",
        lambda: f"{_r(COUNTERPARTIES)} warrants that neither it nor any of its officers or directors appear on any government-maintained list of restricted or prohibited parties, including the OFAC Specially Designated Nationals list.",
        lambda: f"In the event of a conflict between this Agreement and any applicable law, regulation, or governmental requirement, {_r(COUNTERPARTIES)} shall comply with the applicable law.",
    ]

    # Medium severity
    medium_templates = [
        lambda: f"{_r(COUNTERPARTIES)} shall use the Services in accordance with all applicable regulatory requirements and industry standards.",
        lambda: f"Each party shall maintain appropriate records as required by applicable regulatory authorities.",
        lambda: f"{_r(COUNTERPARTIES)} agrees to follow industry-standard practices and recognized codes of conduct applicable to its business operations.",
        lambda: f"The Services shall be performed in compliance with regulatory requirements applicable to {_r(PARTIES)}'s industry.",
        lambda: f"{_r(COUNTERPARTIES)} acknowledges that certain features of the Services may require regulatory approval in certain jurisdictions.",
    ]

    # Low severity
    low_templates = [
        lambda: f"The parties acknowledge that industry standards may evolve over the term of this Agreement.",
        lambda: f"{_r(COUNTERPARTIES)} shall use commercially reasonable efforts to maintain compliance with applicable industry guidelines.",
        lambda: f"The Services are designed to assist {_r(COUNTERPARTIES)} in meeting its compliance obligations, but do not guarantee compliance with any specific regulation.",
    ]

    for t in high_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "High"})
    for t in medium_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Medium"})
    for t in low_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Low"})

    return [{"text": t["text"], "labels": {"Compliance Risk": t["severity"]}, "source": "template"} for t in templates]


def _liability_templates() -> List[dict]:
    """Generate Liability Risk training examples."""
    templates = []

    high_templates = [
        lambda: f"{_r(COUNTERPARTIES)} shall indemnify, defend, and hold harmless {_r(PARTIES)} and its officers, directors, employees, and agents from and against any and all claims, damages, losses, liabilities, costs, and expenses arising out of or relating to {_r(COUNTERPARTIES)}'s use of the Services.",
        lambda: f"The receiving party agrees to make the disclosing party whole for any losses, damages, or costs incurred as a result of any breach of this Agreement.",
        lambda: f"THE SERVICES ARE PROVIDED \"AS IS\" AND \"AS AVAILABLE\" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT.",
        lambda: f"IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY LOST PROFITS, LOST REVENUE, LOSS OF BUSINESS, OR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES.",
        lambda: f"{_r(COUNTERPARTIES)} assumes full responsibility for any consequences arising from its use of the platform and waives all rights to pursue legal action against {_r(PARTIES)}.",
        lambda: f"THE AGGREGATE LIABILITY OF {_r(PARTIES).upper()} ARISING OUT OF OR RELATED TO THIS AGREEMENT SHALL NOT EXCEED THE FEES PAID BY {_r(COUNTERPARTIES).upper()} IN THE {_r(PERIODS).upper()} PRECEDING THE CLAIM.",
        lambda: f"{_r(COUNTERPARTIES)} shall hold {_r(PARTIES)} harmless from any third-party claims arising from {_r(COUNTERPARTIES)}'s breach of its representations, warranties, or obligations under this Agreement.",
        lambda: f"In no event shall {_r(PARTIES)}'s aggregate liability under this Agreement exceed {_r(AMOUNTS)}.",
        lambda: f"Each party shall defend, indemnify, and hold harmless the other party from any third-party claims arising from the indemnifying party's negligence, willful misconduct, or breach of this Agreement.",
        lambda: f"{_r(PARTIES)} SHALL HAVE NO LIABILITY WHATSOEVER FOR ANY DAMAGE, LOSS, OR EXPENSE ARISING OUT OF {_r(COUNTERPARTIES).upper()}'S USE OF THE SERVICES, REGARDLESS OF THE THEORY OF LIABILITY.",
        lambda: f"If any claim is brought against {_r(PARTIES)} as a result of {_r(COUNTERPARTIES)}'s actions or omissions, {_r(COUNTERPARTIES)} shall bear all costs of defense, including reasonable attorneys' fees, and any resulting judgments or settlements.",
        lambda: f"In the event of a breach, the non-breaching party's sole and exclusive remedy shall be the payment of liquidated damages in the amount of {_r(AMOUNTS)}.",
    ]

    medium_templates = [
        lambda: f"Neither party shall be responsible for any delay or failure in performance caused by events beyond its reasonable control, including acts of God, natural disasters, government actions, or labor disputes.",
        lambda: f"{_r(PARTIES)}'s liability under this Agreement shall be limited to direct damages only. The limitation of liability set forth herein shall not apply to breaches of confidentiality.",
        lambda: f"Except as expressly set forth herein, {_r(PARTIES)} makes no representations or warranties of any kind, whether express, implied, or statutory.",
        lambda: f"{_r(PARTIES)} shall not be liable for any failure to perform its obligations if such failure results from circumstances beyond its reasonable control.",
        lambda: f"The warranties set forth in this Agreement are the exclusive warranties provided by {_r(PARTIES)}, and no other warranties, express or implied, are made.",
        lambda: f"Neither party shall be liable for any damages arising from the other party's negligence or failure to comply with its obligations under this Agreement.",
    ]

    low_templates = [
        lambda: f"{_r(PARTIES)} warrants that the Services will conform in all material respects to the specifications set forth in the applicable documentation for a period of {_r(PERIODS)} from the date of delivery.",
        lambda: f"Each party acknowledges that the other party makes no guarantees regarding the results that may be obtained from use of the Services.",
        lambda: f"Warranty claims must be submitted in writing within {_r(NOTICE_PERIODS)} of discovering the defect.",
    ]

    for t in high_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "High"})
    for t in medium_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Medium"})
    for t in low_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Low"})

    return [{"text": t["text"], "labels": {"Liability Risk": t["severity"]}, "source": "template"} for t in templates]


def _privacy_templates() -> List[dict]:
    """Generate Privacy/Data Risk training examples."""
    templates = []

    high_templates = [
        lambda: f"We may collect, store, and process information about you, including your name, email address, IP address, device identifiers, location data, and browsing behavior across our services and third-party platforms.",
        lambda: f"Your personal information may be shared with affiliated companies, business partners, advertising networks, and analytics providers for the purposes of marketing, product improvement, and targeted advertising.",
        lambda: f"We may sell, license, or otherwise transfer your personal data to third-party data brokers and analytics partners for monetization purposes.",
        lambda: f"Personal data collected through the Services may be transferred to and stored on servers located in countries outside your country of residence, including countries that may not provide the same level of data protection.",
        lambda: f"The Service collects biometric identifiers, including facial geometry and fingerprint data, for authentication and identity verification purposes.",
        lambda: f"In the event of a security incident affecting personal data, {_r(PARTIES)} will notify affected individuals and relevant supervisory authorities as required by applicable law.",
        lambda: f"{_r(PARTIES)} processes personally identifiable information (PII) on behalf of {_r(COUNTERPARTIES)}. {_r(COUNTERPARTIES)} is the data controller and {_r(PARTIES)} acts as the data processor.",
        lambda: f"We collect and analyze your browsing history, search queries, purchase patterns, and location data to build a profile of your interests and preferences for targeted advertising.",
        lambda: f"User data, including personal information and usage patterns, may be disclosed to law enforcement or government authorities upon receipt of a valid legal request, without prior notice to the user.",
        lambda: f"{_r(COUNTERPARTIES)} consents to the collection and processing of sensitive personal data, including health information, financial records, and biometric data, in connection with the Services.",
    ]

    medium_templates = [
        lambda: f"We use cookies, pixels, web beacons, and similar tracking technologies to monitor your activity on our website and across third-party sites for analytics and advertising purposes.",
        lambda: f"User records and personal information are retained for the duration of the account and for {_r(PERIODS)} following account termination, unless a longer retention period is required by law.",
        lambda: f"{_r(PARTIES)} engages third-party service providers and subprocessors to assist in the delivery of the Services. A current list of subprocessors is available upon request.",
        lambda: f"Data collected through the Services is retained in accordance with {_r(PARTIES)}'s data retention policy, which may be updated from time to time.",
        lambda: f"We use third-party analytics services, including Google Analytics, to collect information about your use of the Service.",
    ]

    low_templates = [
        lambda: f"The Service uses industry-standard encryption (TLS 1.2 or higher) to protect data in transit between your device and our servers.",
        lambda: f"You may opt out of marketing communications at any time by clicking the unsubscribe link in any promotional email or by contacting us at the address provided.",
        lambda: f"We use cookies to maintain your session and remember your preferences. You may configure your browser to reject cookies, but some features of the Service may not function properly.",
    ]

    for t in high_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "High"})
    for t in medium_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Medium"})
    for t in low_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Low"})

    return [{"text": t["text"], "labels": {"Privacy/Data Risk": t["severity"]}, "source": "template"} for t in templates]


def _financial_templates() -> List[dict]:
    """Generate Financial Risk training examples."""
    templates = []

    high_templates = [
        lambda: f"This Agreement shall automatically renew for successive terms of equal length unless either party provides written notice of non-renewal at least {_r(NOTICE_PERIODS)} prior to the expiration of the then-current term.",
        lambda: f"All payments made under this Agreement are final and non-refundable under any circumstances, including early termination, service failure, or dissatisfaction with the Services.",
        lambda: f"{_r(PARTIES)} reserves the right to adjust pricing, fees, and billing terms at any time upon {_r(NOTICE_PERIODS)} written notice to {_r(COUNTERPARTIES)}.",
        lambda: f"Termination of this Agreement prior to the end of the initial term shall incur an early termination penalty equal to the remaining contract value for the unexpired portion of the term.",
        lambda: f"Late payments shall accrue interest at the rate of {_r(INTEREST_RATES)} per month, or the maximum rate permitted by applicable law, whichever is less.",
        lambda: f"{_r(PARTIES)} may unilaterally increase the subscription fee by up to 15% at each renewal period without requiring {_r(COUNTERPARTIES)}'s consent.",
        lambda: f"In the event of early termination by {_r(COUNTERPARTIES)}, {_r(COUNTERPARTIES)} shall pay a cancellation fee equal to three months of the then-current subscription fee plus any outstanding balance.",
        lambda: f"Overdue amounts shall bear interest at the rate of {_r(INTEREST_RATES)} per month from the due date until paid in full, plus all costs of collection, including reasonable attorneys' fees.",
        lambda: f"{_r(COUNTERPARTIES)} commits to a minimum annual spend of {_r(AMOUNTS)}, regardless of actual usage. Unused credits do not roll over to the next period.",
    ]

    medium_templates = [
        lambda: f"Cancellation of the subscription after the initial term shall be subject to a cancellation fee of one month's subscription fee.",
        lambda: f"{_r(COUNTERPARTIES)} agrees to a minimum purchase commitment of {_r(AMOUNTS)} per year during the term of this Agreement.",
        lambda: f"{_r(PARTIES)} reserves the right to withhold payment or offset amounts owed to {_r(COUNTERPARTIES)} against any disputed claims or outstanding obligations.",
        lambda: f"All invoices are payable within thirty (30) days of the invoice date. Late payments may be subject to a late fee of {_r(INTEREST_RATES)} per month.",
        lambda: f"All amounts are denominated in U.S. dollars. Currency conversion risks are borne by {_r(COUNTERPARTIES)} for payments made in other currencies.",
        lambda: f"Non-refundable setup fees of {_r(AMOUNTS)} are due upon execution of this Agreement.",
        lambda: f"If {_r(COUNTERPARTIES)} downgrades its plan during the term, {_r(COUNTERPARTIES)} shall continue to pay the higher rate until the end of the current billing cycle.",
        lambda: f"Upon termination, {_r(COUNTERPARTIES)} shall pay for all Services rendered through the termination date plus any applicable wind-down costs.",
        lambda: f"{_r(PARTIES)} may assess a convenience fee for payments made by credit card or other non-standard payment methods.",
        lambda: f"Price adjustments shall take effect at the beginning of each renewal term upon {_r(NOTICE_PERIODS)} prior written notice.",
        lambda: f"Disputed invoices must be reported within {_r(NOTICE_PERIODS)} of receipt. Failure to dispute within this period constitutes acceptance.",
        lambda: f"{_r(COUNTERPARTIES)} shall maintain a security deposit equal to one month's fees for the duration of the Agreement.",
        lambda: f"Volume discounts are contingent upon meeting minimum order thresholds. Failure to meet thresholds may result in retroactive price adjustments.",
        lambda: f"Any taxes, duties, or government-imposed fees arising from this Agreement shall be the sole responsibility of {_r(COUNTERPARTIES)}.",
    ]

    low_templates = [
        lambda: f"All invoices are due and payable within thirty (30) days of the date of invoice. Payment shall be made by wire transfer or ACH to the account designated by {_r(PARTIES)}.",
        lambda: f"Funds held in escrow shall be released upon mutual written agreement of the parties or upon final resolution of any dispute.",
        lambda: f"{_r(COUNTERPARTIES)} shall reimburse {_r(PARTIES)} for reasonable, pre-approved out-of-pocket expenses incurred in connection with the Services.",
        lambda: f"Payment terms are net 30 from the date of invoice unless otherwise agreed in writing by both parties.",
        lambda: f"Annual subscription fees are billed in advance on the anniversary of the Effective Date.",
        lambda: f"{_r(PARTIES)} shall provide {_r(COUNTERPARTIES)} with itemized invoices detailing all charges for the applicable billing period.",
        lambda: f"Fees for additional users or capacity above the contracted amounts shall be billed at the rates set forth in the Order Form.",
        lambda: f"Travel and accommodation expenses shall be reimbursed at cost, subject to {_r(COUNTERPARTIES)}'s standard travel policy.",
    ]

    for t in high_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "High"})
    for t in medium_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Medium"})
    for t in low_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Low"})

    return [{"text": t["text"], "labels": {"Financial Risk": t["severity"]}, "source": "template"} for t in templates]


def _ambiguity_templates() -> List[dict]:
    """Generate Contractual Ambiguity training examples."""
    templates = []

    high_templates = [
        lambda: f"{_r(PARTIES)} may modify, update, or discontinue these terms at any time, with changes becoming effective immediately upon posting to {_r(PARTIES)}'s website.",
        lambda: f"{_r(PARTIES)} may take such actions as it deems necessary or appropriate in its sole and absolute discretion to protect its interests and the interests of its users.",
        lambda: f"Continued use of the Services after any changes to these terms constitutes your acceptance of the modified terms.",
        lambda: f"{_r(PARTIES)} may, at its sole discretion, suspend, restrict, or terminate {_r(COUNTERPARTIES)}'s access to the Services at any time and for any reason, with or without notice.",
        lambda: f"The scope, features, and pricing of the Services are subject to change at any time without prior notice to {_r(COUNTERPARTIES)}.",
        lambda: f"{_r(PARTIES)} reserves the right to determine, in its sole discretion, whether {_r(COUNTERPARTIES)}'s use of the Services violates the terms of this Agreement.",
        lambda: f"By continuing to access the platform after modifications are posted, {_r(COUNTERPARTIES)} agrees to be bound by the revised terms without further notice or consent.",
        lambda: f"{_r(PARTIES)} may assign, transfer, or delegate any of its rights or obligations under this Agreement to any third party at its sole discretion without notice.",
    ]

    medium_templates = [
        lambda: f"The Services will be delivered on a commercially reasonable basis within a reasonable timeframe, subject to {_r(PARTIES)}'s standard processes and procedures.",
        lambda: f"Obligations under this Agreement are subject to such conditions and limitations as {_r(PARTIES)} may establish from time to time.",
        lambda: f"The scope of Services includes, without limitation, such activities as the parties may mutually determine to be appropriate.",
        lambda: f"A material breach of this Agreement shall be determined by the non-breaching party in good faith, taking into account all relevant circumstances.",
        lambda: f"{_r(PARTIES)} shall use reasonable efforts to provide the Services in accordance with the specifications, subject to availability and operational requirements.",
        lambda: f"The parties shall negotiate in good faith to resolve any disputes arising under this Agreement, using customary commercial practices.",
        lambda: f"The term 'material adverse change' shall have the meaning customarily attributed to such term in agreements of this type.",
    ]

    low_templates = [
        lambda: f"This Agreement, including but not limited to the terms and conditions set forth herein, constitutes the entire agreement between the parties.",
        lambda: f"{_r(PARTIES)} shall use commercially reasonable efforts to maintain service availability, subject to scheduled maintenance windows communicated from time to time.",
        lambda: f"The parties shall cooperate in good faith to implement the terms of this Agreement and resolve any issues that may arise.",
        lambda: f"Performance standards are based on generally accepted industry practices as applied to services of a similar nature and scope.",
        lambda: f"Response times for support requests shall be reasonable and consistent with {_r(PARTIES)}'s published service level targets.",
        lambda: f"The term 'business day' means any day other than a Saturday, Sunday, or public holiday in {_r(JURISDICTIONS)}.",
        lambda: f"Minor updates and patches may be applied from time to time without advance notice to {_r(COUNTERPARTIES)}.",
    ]

    for t in high_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "High"})
    for t in medium_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Medium"})
    for t in low_templates:
        for _ in range(random.randint(3, 5)):
            templates.append({"text": t(), "severity": "Low"})

    return [{"text": t["text"], "labels": {"Contractual Ambiguity": t["severity"]}, "source": "template"} for t in templates]


def _negative_examples() -> List[dict]:
    """Generate neutral/negative examples — standard contract boilerplate with no risk."""
    ALL_CATEGORIES = ["Compliance Risk", "Liability Risk", "Privacy/Data Risk",
                      "Financial Risk", "Contractual Ambiguity"]
    empty_labels = {c: None for c in ALL_CATEGORIES}

    neutral_clauses = [
        "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of laws principles.",
        "Any notices required or permitted under this Agreement shall be in writing and delivered by certified mail, overnight courier, or email to the addresses set forth on the signature page.",
        "This Agreement may be executed in counterparts, each of which shall be deemed an original, and all of which together shall constitute one and the same instrument.",
        "The headings in this Agreement are for convenience only and shall not affect the interpretation of this Agreement.",
        "If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.",
        "This Agreement constitutes the entire agreement between the parties with respect to the subject matter hereof and supersedes all prior and contemporaneous agreements and understandings.",
        "No waiver of any provision of this Agreement shall be effective unless in writing and signed by the party against whom the waiver is sought to be enforced.",
        "Neither party may assign this Agreement without the prior written consent of the other party, except in connection with a merger, acquisition, or sale of substantially all of its assets.",
        "The term of this Agreement shall commence on the Effective Date and continue for a period of twelve months.",
        "All intellectual property rights in the Services shall remain the exclusive property of the Provider.",
        "The Provider shall deliver the Services in accordance with the specifications set forth in Exhibit A.",
        "Customer shall designate a primary contact for purposes of communication under this Agreement.",
        "The parties agree to maintain the confidentiality of all proprietary information exchanged under this Agreement for a period of three years following termination.",
        "Provider shall maintain commercially reasonable security measures to protect Customer data during the term of this Agreement.",
        "This Agreement may not be modified except by a written instrument signed by both parties.",
        "The Effective Date of this Agreement shall be the date of the last signature below.",
        "Provider shall provide Customer with reasonable access to technical support during normal business hours.",
        "Customer shall be responsible for providing accurate and complete information necessary for the delivery of the Services.",
        "The parties acknowledge that this Agreement does not create a partnership, joint venture, or agency relationship between them.",
        "Any dispute arising under this Agreement shall be resolved by binding arbitration in accordance with the rules of the American Arbitration Association.",
        "Provider shall deliver monthly usage reports to Customer in a format reasonably acceptable to Customer.",
        "Customer acknowledges that it has read and understands the terms of this Agreement.",
        "The recitals set forth above are incorporated into and made a part of this Agreement.",
        "Provider shall assign qualified personnel to perform the Services described herein.",
        "The parties agree to cooperate in the transition of Services upon termination of this Agreement.",
        f"The initial term of this Agreement is {_r(PERIODS)}, commencing on the Effective Date.",
        "Customer shall provide Provider with access to its facilities and systems as reasonably necessary for Provider to perform the Services.",
        "Provider represents that it has the authority and capacity to enter into this Agreement and perform its obligations hereunder.",
        "The exhibits and schedules attached hereto are incorporated by reference and made a part of this Agreement.",
        "Customer shall pay all undisputed invoices in accordance with the payment terms set forth in Schedule B.",
        "The Services shall include implementation, training, and ongoing technical support as described in the Statement of Work.",
        "Provider shall use commercially reasonable efforts to meet the delivery milestones set forth in the project timeline.",
        "Customer grants Provider a limited license to use Customer's trademarks solely for the purpose of performing the Services.",
        "Each party represents that it is duly organized and validly existing under the laws of its jurisdiction of incorporation.",
        "The parties agree that the United Nations Convention on Contracts for the International Sale of Goods does not apply to this Agreement.",
        "Provider shall maintain insurance coverage in the amounts and types specified in Exhibit C.",
        "Customer may request additional services beyond the scope of this Agreement, subject to a separate Statement of Work and fees.",
        "The parties agree to execute any additional documents reasonably necessary to effectuate the purposes of this Agreement.",
        "Provider shall notify Customer promptly of any changes in its key personnel assigned to perform the Services.",
        "This Agreement shall be binding upon and inure to the benefit of the parties and their respective successors and permitted assigns.",
        "The failure of either party to enforce any provision of this Agreement shall not constitute a waiver of such provision.",
        "All rights and remedies under this Agreement are cumulative and not exclusive of any other rights or remedies.",
        "Customer shall return or destroy all Provider confidential information within thirty days following termination of this Agreement.",
        "The parties agree to resolve disputes through mediation before resorting to arbitration or litigation.",
        "Provider shall comply with Customer's reasonable workplace policies while performing Services on Customer's premises.",
        "The Agreement may be amended only by a written instrument signed by authorized representatives of both parties.",
        f"This Agreement shall be governed by and construed in accordance with the laws of {_r(JURISDICTIONS)}.",
        "Each party shall bear its own costs and expenses in connection with the negotiation, execution, and performance of this Agreement.",
        "The Effective Date and term of this Agreement are as set forth on the Order Form attached hereto.",
    ]

    examples = []
    for clause in neutral_clauses:
        examples.append({"text": clause, "labels": dict(empty_labels), "source": "negative"})
    # Generate variations with party name swaps (3x more than before)
    for _ in range(60):
        clause = random.choice(neutral_clauses)
        clause = clause.replace("Provider", _r(PARTIES)).replace("Customer", _r(COUNTERPARTIES))
        examples.append({"text": clause, "labels": dict(empty_labels), "source": "negative"})

    return examples


def _multi_label_examples() -> List[dict]:
    """Generate examples that trigger MULTIPLE risk categories simultaneously."""
    ALL_CATEGORIES = ["Compliance Risk", "Liability Risk", "Privacy/Data Risk",
                      "Financial Risk", "Contractual Ambiguity"]

    multi_examples = [
        {
            "text": f"{_r(COUNTERPARTIES)} shall indemnify {_r(PARTIES)} for any claims arising from {_r(COUNTERPARTIES)}'s failure to comply with applicable data protection laws, including GDPR and CCPA. {_r(PARTIES)}'s aggregate liability for data protection claims shall not exceed {_r(AMOUNTS)}.",
            "labels": {"Compliance Risk": "High", "Liability Risk": "High", "Privacy/Data Risk": "High"},
        },
        {
            "text": f"{_r(PARTIES)} may modify its data collection and sharing practices at any time as it deems appropriate. Personal information may be shared with third-party advertising partners without additional notice.",
            "labels": {"Privacy/Data Risk": "High", "Contractual Ambiguity": "High"},
        },
        {
            "text": f"This Agreement shall automatically renew unless terminated by {_r(COUNTERPARTIES)} upon {_r(NOTICE_PERIODS)} notice. Early termination fees apply. {_r(PARTIES)} may adjust pricing at its sole discretion upon renewal.",
            "labels": {"Financial Risk": "High", "Contractual Ambiguity": "High"},
        },
        {
            "text": f"{_r(COUNTERPARTIES)} shall bear all costs associated with maintaining regulatory compliance, including HIPAA, and shall indemnify {_r(PARTIES)} for any regulatory fines arising from {_r(COUNTERPARTIES)}'s non-compliance.",
            "labels": {"Compliance Risk": "High", "Liability Risk": "High"},
        },
        {
            "text": f"THE SERVICES ARE PROVIDED AS-IS. {_r(PARTIES)} MAKES NO WARRANTIES AND SHALL HAVE NO LIABILITY. {_r(COUNTERPARTIES)} AGREES TO PAY ALL FEES FOR THE MINIMUM COMMITMENT PERIOD REGARDLESS OF SERVICE QUALITY.",
            "labels": {"Liability Risk": "High", "Financial Risk": "High"},
        },
        {
            "text": f"We collect personal data including biometric identifiers. This data may be shared with third parties. All payments for data processing services are non-refundable.",
            "labels": {"Privacy/Data Risk": "High", "Financial Risk": "Medium"},
        },
        {
            "text": f"{_r(PARTIES)} may change its compliance requirements from time to time as it deems appropriate, and {_r(COUNTERPARTIES)} must comply with all such changes at its own expense.",
            "labels": {"Compliance Risk": "Medium", "Contractual Ambiguity": "High", "Financial Risk": "Medium"},
        },
        {
            "text": f"{_r(COUNTERPARTIES)} shall indemnify {_r(PARTIES)} against all claims and shall comply with applicable export control laws. This obligation survives termination of the Agreement indefinitely.",
            "labels": {"Liability Risk": "High", "Compliance Risk": "High"},
        },
    ]

    # Generate a few random variants of each
    results = []
    for ex in multi_examples:
        # Fill in None for categories not mentioned
        full_labels = {c: ex["labels"].get(c) for c in ALL_CATEGORIES}
        results.append({"text": ex["text"], "labels": full_labels, "source": "multi_label"})
        # One variant with party swap
        variant = ex["text"].replace("Provider", _r(PARTIES)).replace("Customer", _r(COUNTERPARTIES))
        results.append({"text": variant, "labels": full_labels, "source": "multi_label"})

    return results


def _canonical_examples() -> List[dict]:
    """Convert canonical clauses from knowledge base into training examples."""
    ALL_CATEGORIES = ["Compliance Risk", "Liability Risk", "Privacy/Data Risk",
                      "Financial Risk", "Contractual Ambiguity"]

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.services.risk_knowledge_base import CANONICAL_CLAUSES

    examples = []
    for c in CANONICAL_CLAUSES:
        labels = {cat: None for cat in ALL_CATEGORIES}
        labels[c["category"]] = c["severity"]
        examples.append({
            "text": c["text"],
            "labels": labels,
            "source": "canonical",
        })
    return examples


def generate_dataset(seed: int = 42) -> List[dict]:
    """Generate the full training dataset."""
    random.seed(seed)

    ALL_CATEGORIES = ["Compliance Risk", "Liability Risk", "Privacy/Data Risk",
                      "Financial Risk", "Contractual Ambiguity"]

    dataset = []

    # Canonical clauses (40 examples)
    dataset.extend(_canonical_examples())

    # Template-generated per-category examples
    for gen_fn in [_compliance_templates, _liability_templates, _privacy_templates,
                   _financial_templates, _ambiguity_templates]:
        examples = gen_fn()
        # Ensure all categories present in labels (None for unlabeled)
        for ex in examples:
            for cat in ALL_CATEGORIES:
                ex["labels"].setdefault(cat, None)
        dataset.extend(examples)

    # Multi-label examples
    dataset.extend(_multi_label_examples())

    # Negative examples
    dataset.extend(_negative_examples())

    # Shuffle
    random.shuffle(dataset)

    return dataset


def main():
    dataset = generate_dataset()

    # Stats
    ALL_CATEGORIES = ["Compliance Risk", "Liability Risk", "Privacy/Data Risk",
                      "Financial Risk", "Contractual Ambiguity"]

    print("=" * 60)
    print("TRAINING DATA GENERATION")
    print("=" * 60)
    print(f"Total examples: {len(dataset)}")
    print()

    # Per-category counts
    for cat in ALL_CATEGORIES:
        positives = [d for d in dataset if d["labels"].get(cat) is not None]
        sevs = {}
        for d in positives:
            s = d["labels"][cat]
            sevs[s] = sevs.get(s, 0) + 1
        print(f"  {cat}: {len(positives)} positive ({sevs})")

    negatives = [d for d in dataset if all(v is None for v in d["labels"].values())]
    print(f"\n  Negative (no risk): {len(negatives)}")

    by_source = {}
    for d in dataset:
        by_source[d["source"]] = by_source.get(d["source"], 0) + 1
    print(f"\n  By source: {by_source}")

    # Save
    out_path = Path(__file__).resolve().parent.parent / "data" / "training" / "risk_dataset.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"\nSaved to {out_path}")
    print(f"File size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
