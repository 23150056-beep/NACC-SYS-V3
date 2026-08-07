"""Static digitization of NACC-SAMD-GF-000 (June 2025) -- "Assessment Tool for the
Certification of AACC Programs and Services" (RACCO I internal readiness self-check).

Extracted from docs/v2-planning/NACC_SAMD-Assessment-Tool-for-Certification-of-AACC-
Programs-and-Services-for-Social-Work-Agencies.md, the official government checklist.
The structure below is fixed by that source document and must not be changed without
re-checking it: KRA I = 11 indicators, KRA II = 51, KRA III = 21 (83 total). The doc's
own summary table (~line 322) and Sub-Total rows (~lines 90, 276, 312) confirm these
counts.
"""

CHECKLIST = [
    {
        "key": "I",
        "title": 'Program Management',
        "items": [
            {
                "key": 'I.1',
                "number": 1,
                "section": '',
                "indicator": 'The Social Work Agency (SWA) holds a valid Certificate of Registration and License to Operate (CRLTO).',
                "means": ['DSWD-issued CRLTO']
            },
            {
                "key": 'I.2',
                "number": 2,
                "section": 'Legal and Institutional Compliance',
                "indicator": "The SWA's Manual of Operations (MOO) is board-approved and formally integrates Adoption and Alternative Child Care (AACC) programs, with clear guidelines to ensure structured, systematic, and compliant implementation. The MOO reflects alignment with applicable laws and policies (e.g., RA 11642, DSWD, and NACC issuances). It is updated as necessary to address organizational changes, accreditation requirements, and recommendations from monitoring bodies.",
                "means": ['Copy of the Board-approved Manual of Operations (MOO), which includes a dedicated section on '
                 'AACC programs and services.',
                 'Copy of the Board Resolution or certified/approved Minutes of the Board Meeting indicating '
                 'formal approval of the incorporation of AACC programs and services in the MOO.']
            },
            {
                "key": 'I.3',
                "number": 3,
                "section": 'Legal and Institutional Compliance',
                "indicator": 'The SWA actively coordinates and complies with NACC, DSWD, LGUs, and other relevant agencies regarding the AACC program implementation.',
                "means": ['MOA/MOU or partnership agreements or any proof of coordination, engagement, or '
                 'agreements/partnership with the DSWD/LGUs/NACC.']
            },
            {
                "key": 'I.4',
                "number": 4,
                "section": 'Resource and Financial Management',
                "indicator": 'The SWA allocates adequate budget, supplies, facilities, and resources to support the implementation, case processing, and sustainability of Adoption and Alternative Child Care (AACC) programs. This includes expenses such as notarial fees (e.g., Deed of Voluntary Commitment, Petition), psychological and developmental evaluations, Certificate of Live Birth (COLB), mailing fees, and other related costs. Documentation must show that these are included under the 70% allocation for direct social welfare services, ensuring compliance with DSWD financial guidelines and promoting efficient fund utilization.',
                "means": ['Approved Annual Work and Financial Plan (WFP) with budget breakdown/allocation for AACC '
                 'Programs.']
            },
            {
                "key": 'I.5',
                "number": 5,
                "section": 'Resource and Financial Management',
                "indicator": "The SWA demonstrates proactive and sustainable resource mobilization strategies to ensure program continuity without compromising the confidentiality of case information, the protection of children's identities, and the ethical use of children's photos and personal information. The agency explicitly prohibits posting and the publication/upload of children's images and personal data on any media, including social media, for fundraising purposes. It ensures full compliance with RA 10173 (Data Privacy Act), RA 11642, and ethical standards in alternative child care.",
                "means": ['Fundraising proposals and reports/documentation',
                 'DSWD-issued solicitation permits, donor agreements/ Child Sponsorship reports (if '
                 'applicable)',
                 'Child Protection Policy and or Data Privacy Policy']
            },
            {
                "key": 'I.6',
                "number": 6,
                "section": 'Human Resource Management and Staff Development',
                "indicator": 'The SWA employs a full-time Registered Social Worker (RSW) who is designated to manage AACC cases, among other case management responsibilities assigned by the agency.',
                "means": ['Valid PRC license, Certificate of Employment, Job Description confirming full-time '
                 'employment',
                 'Service Record, Certificate/s or Record of Assignment in AACC-related functions,']
            },
            {
                "key": 'I.7',
                "number": 7,
                "section": 'Human Resource Management and Staff Development',
                "indicator": 'The RSW has at least one (1) year of relevant experience handling Adoption and Alternative Child Care (AACC) cases.',
                "means": ["Supervisor's Certification (optional but useful for clarification) Caseload Inventory (CLI) "
                 'record']
            },
            {
                "key": 'I.8',
                "number": 8,
                "section": 'Human Resource Management and Staff Development',
                "indicator": 'The RSW has completed a minimum of four (4) hours of relevant AACC training and demonstrates ongoing professional development through continuous participation in AACC-related training and capacity building activities conducted or endorsed by the DSWD Academy and/or NACC.',
                "means": ['Training Certificate/s (clearly showing number of hours and AACC relevance),',
                 'Certificates of Attendance/Completion from DSWD Academy, NACC, or other recognized '
                 'institutions,',
                 'Updated Training Matrix or Individual Learning/ Development Plan.']
            },
            {
                "key": 'I.9',
                "number": 9,
                "section": 'Human Resource Management and Staff Development',
                "indicator": 'A performance review system is in place to ensure continuous improvement and accountability in service delivery.',
                "means": ['Performance evaluation forms HR records of staff assessments']
            },
            {
                "key": 'I.10',
                "number": 10,
                "section": 'Monitoring and Evaluation (M&E)',
                "indicator": 'A functional Monitoring and Evaluation (M&E) system is in place within the SWA to track progress, ensure quality, and evaluate outcomes of AACC programs and services, in alignment with NACC guidelines.',
                "means": ['Agency-developed M&E Tool/Template (Monitoring Forms, Checklists, Evaluation Matrix Minutes '
                 'of the Meeting Documentation of program review or feedback sessions']
            },
            {
                "key": 'I.11',
                "number": 11,
                "section": 'Monitoring and Evaluation (M&E)',
                "indicator": 'Availability of updated records and reports on AACC program implementation.',
                "means": ['Semi-Annual Narrative and Statistical Reports on AACC program implementation.']
            },
        ],
    },
    {
        "key": "II",
        "title": 'Case Management',
        "items": [
            {
                "key": 'II.1',
                "number": 1,
                "section": '',
                "indicator": 'The standard caseload ratio is 1:25 for a full-time registered social worker (RSW) handling cases for AACC.',
                "means": ["RSW's Individual Caseload Report", 'CLI of children']
            },
            {
                "key": 'II.2',
                "number": 2,
                "section": 'Caseload Management',
                "indicator": "When the RSW's caseload exceeds the standard 1:25 ratio, a Social Welfare Assistant or Adoption Para-Social Worker may be engaged to support case management functions under the supervision of a licensed RSW, provided they have relevant education or training and are appropriately oriented in AACC programs and documentation procedures. Social Welfare Assistant and Adoption Para-Social Worker must have completed at least two (2) years of college, preferably with a degree in B.S. Social Work, and have attended at least three (3) training sessions on handling AACC cases.",
                "means": ["Caseload Inventory showing the RSW's current caseload exceeding the 1:25 ratio",
                 'Job Description of the SWA or Para-Social Worker outlining support functions under RSW '
                 'supervision',
                 'Certificate of Orientation or Training related to AACC case management',
                 'Proof of educational attainment (e.g., TOR or diploma showing at least 2 years of college, '
                 'preferably in social work or related field)']
            },
            {
                "key": 'II.3',
                "number": 3,
                "section": 'Institutional Care as Last Resort',
                "indicator": "The SWA implements a structured permanency planning process, ensuring that residential care is temporary and utilized only as a last resort. Case management follows a sequential and goal-oriented approach, beginning with efforts toward family reunification, when feasible, and progressing toward alternative child care options, such as kinship care, foster care, or adoption, based on the child's best interests and assessed needs.",
                "means": ["Child's Case Study Report",
                 'Admission Agreement with the biological family or relatives, indicating the agreed minimum '
                 'length of stay',
                 'Case Management and Intervention Plan (CMIP), outlining the step-by-step assessment of '
                 'permanency options (e.g., reunification, kinship care, foster care, or adoption)']
            },
            {
                "key": 'II.4',
                "number": 4,
                "section": 'Institutional Care as Last Resort',
                "indicator": 'The SWA has established initial processes for implementing AACC programs in compliance with R.A. No. 11642 and other NACC guidelines/policies to ensure legal and regulatory standards. Children eligible for foster care are placed within six (6) months of admission Children assessed for adoption have their CDCLAA petition promptly facilitated. When adoption is not viable, alternative interventions such as kinship care, reunification, or referral to appropriate facilities are pursued in the best interest of the child.',
                "means": ['Agency Policies and Guidelines (internal protocols aligned with R.A. No. 11642 and NACC '
                 'regulations. Case Management Records (documented timelines for kinship care, foster care '
                 'placement, CDCLAA facilitation, and other alternative child care interventions. Child Case '
                 'Folders (individual case documentation, assessments, case management plans, and permanency '
                 'efforts) MOO']
            },
            {
                "key": 'II.5',
                "number": 5,
                "section": 'Institutional Care as Last Resort',
                "indicator": "The SWA initiates a formal request for a Parenting Capability Assessment (PCA) to the concerned LGU/Local Social Welfare and Development Office (LSWDO) prior to recommending kinship care, foster care, or reunification. The PCA is conducted by the LGU Social Worker, and the result is used to evaluate the readiness and capacity of the parent(s) or relative(s) to provide appropriate care for the child. In complex adoption cases, a Parenting Capability Assessment Report (PCAR) is required to evaluate the biological parent(s)' capacity and decision-making regarding the child's adoption.",
                "means": ['PCA request letter from the SWA to the LGU/LSWDO, with an attached standard PCAR template, '
                 'if necessary, to guide the LGU Social Worker in conducting the assessment in alignment with '
                 'AACC standards.',
                 'LGU-issued PCA Report',
                 'Case conference minutes discussing PCA results and decisions on child placement']
            },
            {
                "key": 'II.6',
                "number": 6,
                "section": 'Case Intake and Information Gathering',
                "indicator": "A comprehensive assessment of the child's background, circumstances, and placement options is conducted. This includes interviews with the child (if age-appropriate), the biological parent(s), the referring party, and other key individuals. Home visits are conducted to validate intake data, assess the home environment, and determine the feasibility of family reunification or other placement options.",
                "means": ["Duly accomplished General Intake Sheet (GIS) is filed in the child's case folder (the SWA "
                 'may adopt the NACC-prescribed GIS template and may modify or contextualize it based on the '
                 "agency's operational needs); Intake interview records, Genogram, Ecomap, Home visit feedback "
                 'reports, Barangay certificate, and other collateral information gathered']
            },
            {
                "key": 'II.7',
                "number": 7,
                "section": 'Case Intake and Information Gathering',
                "indicator": 'All required pre-admission documents are secured to ensure compliance with applicable legal and regulatory standards. After admission, additional documents necessary for case management, legal proceedings, and service provision (e.g., medical records, psychological assessments, birth registration updates) are progressively obtained and updated.',
                "means": ['Referral letter, CCSR/SCSR, COLB, Medical records and laboratories including Medico legal '
                 '(as applicable) Newborn screening, Immunization/Vaccination records, Police blotter/ '
                 'Barangay certificate, Court order, School records, Photographs, and Admission Slip.']
            },
            {
                "key": 'II.8',
                "number": 8,
                "section": 'Case Intake and Information Gathering',
                "indicator": "A case conference is conducted either before or after admission, involving the referring party and the SWA's case management team or multidisciplinary team to discuss the child's circumstances and intervention plans.",
                "means": ['Minutes of the case conference and photo documentation, Attendance log/sheets']
            },
            {
                "key": 'II.9',
                "number": 9,
                "section": 'Procedures for Child Admission and Case Management',
                "indicator": "A signed Agreement on the Temporary Shelter/Stay of the Child in the SWA with the agreed timeline/length of stay is executed upon admission. The agreement, signed by the SWA and the parent(s) or referring party, outlines roles, responsibilities, and commitments in the child's care. It emphasizes family reunification as the primary goal, with adoption and alternative child care explored only when reunification is deemed not in the child's best interest.",
                "means": ['Signed Agreement on the Temporary Shelter/Stay of the Child in the SWA.']
            },
            {
                "key": 'II.10',
                "number": 10,
                "section": 'Procedures for Child Admission and Case Management',
                "indicator": "In coordination with the case management or multidisciplinary team, a Case Management and Intervention Plan (CMIP) for children under AACC cases is developed alongside the Initial CCSR upon admission. This plan is reviewed quarterly to assess progress, respond to emerging needs, and implement necessary adjustments in alignment with the child's permanency goals. Depending on the case category and placement plan (adoption or kinship care/foster care), the CMIP includes the Child's Identifying Information, General and Specific Objectives, Tasks/Activities/Helping Interventions or Strategies, Responsible Persons, Time Frame, and Expected Output.",
                "means": ['Accomplished and regularly updated CMIP (the SWA may adopt or customize the NACC-prescribed '
                 "template, provided that the content remains consistent with the NACC's guidelines.)",
                 'Multidisciplinary team evaluation reports.']
            },
            {
                "key": 'II.11',
                "number": 11,
                "section": 'Procedures for Child Admission and Case Management',
                "indicator": "Photo documentation is required upon admission and must be maintained throughout the case management process. Regular milestone tracking through updated photographs is conducted to monitor the child's development. The child's footprints and/or handprints may also be taken upon admission for inclusion in the Lifebook.",
                "means": ["Periodic photographs, Child's Lifebook"]
            },
            {
                "key": 'II.12',
                "number": 12,
                "section": 'Procedures for Child Admission and Case Management',
                "indicator": "A comprehensive health and medical assessment are conducted upon admission. The child's physical and developmental milestone is continuously monitored, with regular updates to ensure proper interventions. NACC-prescribed templates for the Health and Medical Profile, (SWA may adopt and consistently utilize these to ensure standardized documentation and monitoring of the child's health and medical condition in line with AACC requirements for CDCLAA and matching.",
                "means": ['Health and Medical Records Anthropometric Tracking Sheets, and updated Immunization Logbook '
                 'or Records']
            },
            {
                "key": 'II.13',
                "number": 13,
                "section": 'Procedures for Child Admission and Case Management',
                "indicator": 'The SWA conducts social preparation and orientation sessions to help the child understand the purpose of placement, their rights, and the services available to them. When developmentally appropriate, the child is actively engaged in case planning through informed consent procedures. For children aged ten (10) years and above who are eligible for adoption, their written consent to adoption is obtained, documented, and included in the case folder. This process ensures child participation, promotes trust, reduces distress, and empowers the child in decisions affecting their future.',
                "means": ['Case notes and documentation of social',
                 'preparation and orientation sessions, including counseling sessions. (Records should reflect '
                 'objectives, participants, session content, and outcomes to demonstrate informed '
                 'participation and readiness for AACC processes.) Informed consent form signed by the child '
                 '(if developmentally appropriate) Written Consent to Adoption signed by the child (10 years '
                 'old and above) Photo documentation of the activity or session.']
            },
            {
                "key": 'II.14',
                "number": 14,
                "section": 'Procedures for Child Admission and Case Management',
                "indicator": "Upon the child's admission, all initial and available case details must be recorded or encoded in the Caseload Inventory (CLI) to ensure accurate documentation of the child's identity, background, and circumstances. This CLI is regularly updated throughout the case management process to reflect new developments, interventions, and placement progress. The updated CLI is submitted to NACC through the RACCO within the prescribed reporting periods to ensure proper monitoring and technical assistance, as necessary.",
                "means": ['Updated Caseload Inventory (CLI) using the NACC-prescribed template. Email acknowledgment '
                 'from RACCO confirming receipt of the quarterly caseload inventory of children for adoption '
                 'and foster care.']
            },
            {
                "key": 'II.15',
                "number": 15,
                "section": 'Intervention Phase',
                "indicator": "A Child Case Study Report (CCSR) is prepared by the RSW within fifteen (15) days after the child's admission as the basis for the social work intervention. Minimum prescribed content: Identifying Information; Sources of Information and Circumstances of Referral (indicate the circumstances surrounding the referral/admission of the child/adoptee to the Child-Caring Agency, foster home, or guardian, e.g. reason for referral; where the child/adoptee was referred; who was responsible for referral; when was the referral made and when was the child/adoptee finally admitted). Background Information (except for the Current Functioning, all information on the Description of the Child/adoptee upon Admission, Medical History, and Developmental History should be written in the past tense): A. The Child - Medical History, Developmental History, Current Functioning, Description of the child's present environment. B. The Family - tackles the composition and pertinent background information on the child/adoptee's immediate family members and description about the birth parent(s). Termination of Parental Rights (for child/adoptee voluntarily committed by the birthparent/s) or Facts of Findings/Abandonment (for an abandoned child/adoptee with or without known parents). Assessment (summary statement on why the child/adoptee needs adoption or kinship/foster care). Recommendation (summary statement on the social worker's recommendation on the child's placement, including the kind of family that would best meet the needs of the child/adoptee). The CCSR is signed and updated as necessary, or at least semi-annually, reflecting the current functioning and progress of the child based on the result of the evaluation/assessment and CMIP.",
                "means": ['Duly signed and dated CCSR, using the NACC-prescribed template, officially approved and '
                 "compiled in the child's case folder."]
            },
            {
                "key": 'II.16',
                "number": 16,
                "section": 'Intervention Phase',
                "indicator": "All children's COLBs are registered with the concerned Local Civil Registry Office (LCRO). A thorough validation of the child's birth circumstances is conducted to establish identity, legal status, and eligibility for services. This includes verifying birth records, conducting interviews with parents or guardians (if available), and coordinating with relevant authorities or agencies to confirm the child's background.",
                "means": ["Follow-up Report on the Status of the Child's Birth (documented update/report from the SWA "
                 "on cases where the child's COLB remains unavailable 1-3 months after registration with the "
                 'LCR, indicating follow-through actions taken.)',
                 'Birth registration records/COLB',
                 'LCRO and PSA communications (if applicable)']
            },
            {
                "key": 'II.17',
                "number": 17,
                "section": 'Intervention Phase',
                "indicator": "For children aged five (5) years and above, a psychological evaluation is conducted to assess cognitive, emotional, and behavioral well-being. This evaluation helps identify trauma, special needs, and necessary interventions to support the child's mental health and overall development.",
                "means": ['Referral for psychological assessment, Psychological Assessment report (indicating the name, '
                 "PRC license number, and validity of the psychologist's license)"]
            },
            {
                "key": 'II.18',
                "number": 18,
                "section": 'Intervention Phase',
                "indicator": "An Early Childhood Care and Development (ECCD) checklist is completed to evaluate the child's developmental milestones, ensuring appropriate interventions are in place to support their growth and learning.",
                "means": ["Completed ECCD checklist is filed in the child's case folder"]
            },
            {
                "key": 'II.19',
                "number": 19,
                "section": 'Intervention Phase',
                "indicator": "If applicable, a developmental evaluation is conducted for children with special needs or developmental delays, and necessary therapeutic interventions (e.g., speech therapy, occupational therapy, physical therapy) are provided or facilitated in accordance with the child's assessed needs.",
                "means": ['Referral for Developmental Evaluation/ Developmental Evaluation report conducted by a '
                 'licensed developmental pediatrician, with name, PRC license number, and license validity '
                 "indicated in the document. Individual Treatment or Therapy Plan tailored to the child's "
                 'needs, Therapy Session Logs or Progress Reports from service providers, Service Agreement or '
                 'MOU with therapy centers,',
                 'hospitals, or LGU-provided services']
            },
            {
                "key": 'II.20',
                "number": 20,
                "section": 'Children Eligible for Foster Care',
                "indicator": 'Case management in SWA ensures the proper assessment and documentation of children who may be eligible for foster care. This includes children who are abandoned, surrendered, neglected, orphaned, abused, have mild disabilities, or are awaiting adoption. Upon admission, a needs assessment is conducted to determine appropriate foster parent selection. If the child is assessed to be eligible for foster care, the RSW shall prepare the CCSR within fifteen (15) days from the date of admission.',
                "means": ['MOO/Agency Policies and Guidelines (internal protocols aligned with R.A. No. 11642 and AACC '
                 'implementation, Child Case Study Reports, CMIP']
            },
            {
                "key": 'II.21',
                "number": 21,
                "section": 'Children Eligible for Foster Care',
                "indicator": "Required documents for foster care matching are submitted to the RACCO within the prescribed timeline before the scheduled matching conference: Child Case Study Report Recent Health and Medical Profile with immunization records; Original PSA Copy of COLB or COLB of Persons with No Known Parent/s; Recent Photograph; Psychological Evaluation for children five (5) years old and above; School Records for children of school age. PCAR for dependent cases, and Other necessary document Proof of submission/email acknowledgment from the RACCO, copies of the documents submitted are compiled in the child's case folder",
                "means": []
            },
            {
                "key": 'II.22',
                "number": 22,
                "section": 'Children Eligible for Foster Care',
                "indicator": 'The SWA presents eligible children for foster care placement at the Regional Child Placement Committee (RCPC) matching conference.',
                "means": ['Certificate of appearance/attendance to RMC, RACCO communication re: Invitation/Result of '
                 'RMC, Attendance log for Regional Matching Conference.']
            },
            {
                "key": 'II.23',
                "number": 23,
                "section": 'Pre-Placement Process for Children Eligible for Foster Care',
                "indicator": "The SWA ensures that within one week of the Foster Placement Authority (FPA) issuance, the child is prepared for placement through structured pre-placement activities, and the foster parents are fully oriented on the child's case background, turnover procedures, and the temporary nature of foster care.",
                "means": ['Preparation logs and pre-placement reports, Orientation attendance sheets and reports, '
                 'Pre-entrustment conference minutes, Counseling records with foster parents, and the child '
                 '(if applicable) Photo documentation']
            },
            {
                "key": 'II.24',
                "number": 24,
                "section": 'Foster Children Placement, Post-Placement Monitoring, and Endorsement Process',
                "indicator": 'The SWA ensures that the physical entrustment of the child to foster parents is properly documented and facilitated with adjustment activities.',
                "means": ['Turnover report, signed FPA, discharge slip, photo documentation']
            },
            {
                "key": 'II.25',
                "number": 25,
                "section": 'Foster Children Placement, Post-Placement Monitoring, and Endorsement Process',
                "indicator": "The SWA ensures that the Foster Care Supervisory Visit Report provided by the LGU or CPA Foster Care Social Worker is received and properly filed in the child's case folder as part of case documentation.",
                "means": ['Copy of the Foster Care Supervisory Visit Report in the case folder (dated and signed) '
                 'Documentation or log confirming receipt by SWA (e.g., email, transmittal form)']
            },
            {
                "key": 'II.26',
                "number": 26,
                "section": 'Foster Children Placement, Post-Placement Monitoring, and Endorsement Process',
                "indicator": 'For children originating from the SWA who are for adoption and have been placed in foster care, the SWA social worker shall ensure the timely filing and processing of the Petition for CDCLAA, incorporating updated information, particularly the findings from Foster Care Supervisory Visit Reports.',
                "means": ['Updated CCSR incorporating details from Foster Care Supervisory Visit Reports Duly filed '
                 'Petition for CDCLAA, along with all required supporting documents, indicating the date '
                 'received by the RACCO.']
            },
            {
                "key": 'II.27',
                "number": 27,
                "section": 'Foster Children Placement, Post-Placement Monitoring, and Endorsement Process',
                "indicator": "Following the issuance of the CDCLAA, the SWA coordinates with the RACCO, LGU or CPA Foster Care Social Worker for the conduct of a case conference to facilitate the smooth turnover of the child's case. When applicable, the SWA also participates in the matching conference to provide case insights and support best interest matching.",
                "means": ['Case conference documentation (e.g., minutes, attendance sheet,',
                 'agreements made) and photo documentation Coordination letters or email communications with '
                 'LGU/CPA Turnover checklist or documentation indicating transfer of case responsibility']
            },
            {
                "key": 'II.28',
                "number": 28,
                "section": 'Voluntarily Committed or Surrendered Child',
                "indicator": "The SWA secures the child's original copy of COLB, updated colored photos, and necessary documents from the biological parent(s), including a PSA-issued marriage contract or Certificate of No Marriage (CENOMAR), if applicable, valid ID of the biological parent/s or guardian.",
                "means": ['PSA-issued COLB or proof of request, updated 3R-sized colored photos (admission, recent, '
                 'previous placement, if any), PSA-issued Marriage Contract, or CENOMAR of parent(s) issued '
                 'within six (6) months, copies of valid IDs.']
            },
            {
                "key": 'II.29',
                "number": 29,
                "section": 'Voluntarily Committed or Surrendered Child',
                "indicator": "The SWA provides structured and documented counseling and support services to birth parents or legal guardians (as defined under Article 216 of the Family Code) within the first to third month of the child's admission. These services include exploring all possible alternative care options and addressing the emotional aspects of surrender, such as grief, trauma, and loss, to ensure informed, voluntary, and well-considered decisions before the execution of the Deed of Voluntary Commitment (DVC). Ensure the availability of the original and valid copy or certified true copy of the child's Certificate of Live Birth (COLB), as well as the valid and updated identification documents of the biological parent/s or legal guardian prior to the execution of the Deed of Voluntary Commitment (DVC).",
                "means": ['Counseling Sessions records/ logs and photos, Signed Certificate of Counseling with the '
                 'biological parent(s), Documentation of services provided, Case Recordings/Notes of RSW']
            },
            {
                "key": 'II.30',
                "number": 30,
                "section": 'Voluntarily Committed or Surrendered Child',
                "indicator": 'The SWA ensures the proper execution of the Deed of Voluntary Commitment (DVC) in six (6) notarized original copies, accompanied by valid identification documents of the parent(s) or guardian, and a secured Certificate of Authority for Notarial Act (CANA). The execution, signing, and notarization of the DVC shall be conducted on the same day, The biological parent/s or guardian must be physically present and personally appear before the notary public for the notarization of the DVC. Photo documentation of the signing process may also be undertaken as additional proof and supporting documentation',
                "means": ['Notarized DVC (6 original copies), Attached valid ID copies of parent(s), Certificate of '
                 'Authority for Notarial Act (CANA)']
            },
            {
                "key": 'II.31',
                "number": 31,
                "section": 'Voluntarily Committed or Surrendered Child',
                "indicator": 'The SWA files a petition for CDCLAA with a comprehensive CCSR detailing the circumstances of voluntary commitment and ensures that the three-month reglementary period is observed.',
                "means": ['Filed Petition for CDCLAA, with acknowledgment or proof of dossier submission to the RACCO.']
            },
            {
                "key": 'II.32',
                "number": 32,
                "section": 'Involuntarily Committed Children',
                "indicator": 'The SWA ensures that, for involuntarily committed children, a complete petition for CDCLAA is filed within three months from receipt of the court order, with all required legal and documentary submissions.',
                "means": ['Certified true copy of the court order for involuntary commitment, filed petition for CDCLAA '
                 '(noting single petition for sibling groups, if applicable), PSA-issued COLB, Admission and '
                 'recent 3R-sized photos of the child/ren, Comprehensive CCSR, RACCO/ NACC acknowledgment '
                 'receipt']
            },
            {
                "key": 'II.33',
                "number": 33,
                "section": 'Abandoned Children with Facts of Birth',
                "indicator": "Within the first and second months of a child's admission, the SWA shall initiate and document key case management actions, including securing all required documents, conducting home visits to verify the identity or whereabouts of the child's parent(s)/ relatives, and facilitating birth registration. For children with known facts of birth, the SWA ensures the timely application and issuance of the COLB.",
                "means": ['CMIP indicating timeline of actions taken Copies of secured documents (e.g. birth '
                 'certificates, affidavits, medical records, etc.) Birth registration application documents '
                 'and LCR/ PSA-issued COLB Home visit reports with narratives and photos (if applicable) '
                 'Barangay certifications from the last known address of parent(s)/ relatives Documentation of '
                 "follow-up actions in the child's case folder"]
            },
            {
                "key": 'II.34',
                "number": 34,
                "section": 'Abandoned Children with Facts of Birth',
                "indicator": 'The SWA conducts and documents diligent efforts to locate the biological parents or relatives of abandoned child/ren, including home visits, letters to the last known addresses, public announcements, and social media postings, ensuring all actions are thoroughly recorded in the Comprehensive CCSR.',
                "means": ['Home visit feedback reports and barangay certifications',
                 'confirm attempts to locate parents or relatives. Copies of registered mail sent to the last '
                 'known address, including registry receipts and returned mail, or narrative reports if '
                 'undelivered. Official police blotter reports or barangay certifications documenting the '
                 'abandonment. Copies of newspaper publications or Affidavits of Publication detailing the '
                 "child's case. Media certifications with details of radio/TV announcements, including dates "
                 'and stations. Screenshots of social media postings aimed at locating biological parents or '
                 'relatives Comprehensive CCSR encompassing all search efforts and findings.']
            },
            {
                "key": 'II.35',
                "number": 35,
                "section": 'Abandoned Children with Facts of Birth',
                "indicator": "The RSW prepares and submits a comprehensive CCSR within the prescribed timeline, containing complete case details, including the circumstances of abandonment or neglect, the child's biopsychosocial assessment, family background (if applicable), and interventions provided. The CCSR is supported by relevant documents. Furthermore, the RSW ensures that the petition for the issuance of CDCLAA is filed with complete requirements within the third month of the child's admission.",
                "means": ['Duly signed CCSR by the RSW and supervising social worker, and Center Head Attached '
                 'supporting documents, including but not limited to:',
                 '-Certificate of No Marriage, death, or other pertinent Civil Registry Documents (CRDs) '
                 "-Child's health and medical profile -Psychological or psychiatric assessments Copy of the "
                 'petition for CDCLAA with complete supporting documents Official receipt or acknowledgment of '
                 'submission from NACC/ RACCO indicating date of filing.']
            },
            {
                "key": 'II.36',
                "number": 36,
                "section": 'Foundling Cases: Prompt Response, Safe Custody, Immediate Reporting, Implementation of Safe Haven Protocols, and Timely Completion of Initial Case Management and Placement Procedures',
                "indicator": 'The SWA operates as a Safe Haven, providing temporary custody to foundlings and ensuring reporting to mandated agencies (LSWDO, RACCO, NACC) within 24 to 48 hours.',
                "means": ['Case records of foundlings, Intake forms, Admission slip, copy of initial report (Initial '
                 'CSR) to LSWDO/ RACCO/ NACC, Acknowledgement receipts from receiving agencies']
            },
            {
                "key": 'II.37',
                "number": 37,
                "section": 'Foundling Cases: Prompt Response, Safe Custody, Immediate Reporting, Implementation of Safe Haven Protocols, and Timely Completion of Initial Case Management and Placement Procedures',
                "indicator": "The SWA ensures the timely completion and documentation of the child's initial medical, legal, and administrative requirements, including bone or dental aging/assessment, birth registration or application for PSA-issued COLB, and conduct of proactive search and inquiry efforts to establish the identity and locate the biological family, within 15 working days from case intake.",
                "means": ['Medical certificate (e.g., bone aging or dental aging assessment) Local Civil Registry (LCR) '
                 'or PSA-issued COLB, or proof of application Case folder with initial and recent photos of '
                 'the child (3R size)',
                 'Documentation of diligent search and inquiry efforts (e.g., social media or print media '
                 'postings, police blotters, barangay certifications, affidavit of finder) Comprehensive and '
                 'Exhaustive CCSR submitted to RACCO/ NACC Acknowledgment of receipt of submitted reports']
            },
            {
                "key": 'II.38',
                "number": 38,
                "section": 'Foundling Cases: Prompt Response, Safe Custody, Immediate Reporting, Implementation of Safe Haven Protocols, and Timely Completion of Initial Case Management and Placement Procedures',
                "indicator": 'The SWA ensures the timely referral of foundlings to licensed foster parents or other appropriate placements based on thorough assessment and facilitates the filing of a complete petition for CDCLAA with all necessary documents. Additionally, the SWA supports opposition or restoration of parental authority when applicable and provides aftercare and monitoring for reintegrated children.',
                "means": ['Referral form, Foster Placement Authority (FPA) Copy of Comprehensive CCSR and Petition for '
                 'CDCLAA, Receipt or acknowledgment of submission to RACCO/NACC Filed opposition petition (if '
                 'applicable), PCAR by LSWDO, Case conference minutes and photo documentation, Endorsement '
                 'letters, and monitoring reports from LSWDO/ LGU.']
            },
            {
                "key": 'II.39',
                "number": 39,
                "section": 'Petition for CDCLAA Filing',
                "indicator": "The petition for the issuance of the CDCLAA shall be in the form of a duly notarized affidavit executed under oath, containing the relevant facts and circumstances surrounding the child's case. The complete petition, with all required supporting documents, shall be filed with the NACC through the RACCO having jurisdiction over the child's current residence.",
                "means": ['Copy of the notarized Petition for CDCLAA with Certificate of Authority for Notarial Act '
                 '(CANA) Acknowledgment from RACCO of a duly received',
                 'copy of the petition and supporting documents One petition is filed for sibling groups with '
                 'separate CDCLAA Certifications for each child.']
            },
            {
                "key": 'II.40',
                "number": 40,
                "section": 'Opposition and Restoration of Parental Authority',
                "indicator": "The SWA ensures proper handling of opposition cases filed by biological parents within the allowed period, requests and reviews the Parenting Capability Assessment Report (PCAR) before making decisions on the opposition, and coordinates with the LSWDO for the child's reintegration if the opposition is granted.",
                "means": ['Copy of filed opposition petition Parenting Capability Assessment Report (PCAR) Case '
                 'conference minutes Coordination records with LSWDO Monitoring reports from LSWDO/LGU']
            },
            {
                "key": 'II.41',
                "number": 41,
                "section": 'Matching Process',
                "indicator": "The SWA ensures that the child is presented for adoption (within 30 days from receipt of CDCLAA) or foster care matching in accordance with the prescribed timelines and procedures. The Regional Child Placement Committee (RCPC) or the Child Placement Committee (CPC) for interregional and inter-country matching) is responsible for judiciously matching approved Prospective Adoptive Parents (PAPs) and Licensed Foster Parents with children legally available for adoption or eligible for foster care, based on the child's needs and best interest, and the PAPs' or foster parents' capability and commitment to meet those needs and foster a positive parent-child relationship. The matching process does not require religion, religious affiliation, gender orientation, civil status, culture, ethnicity, or linguistic background as mandatory criteria for the selection of PAPs or foster parents, although these factors may be considered when relevant to the child's adjustment and overall well-being.",
                "means": ['Caseload Inventory to verify the timeliness of presenting children for matching in '
                 'accordance with prescribed guidelines. Attendance log as proof of participation in the '
                 'Matching Conference. Presentation materials, such as PowerPoint slides, should be available '
                 "and aligned with the child's case details."]
            },
            {
                "key": 'II.42',
                "number": 42,
                "section": 'Matching Process',
                "indicator": 'The CCSR (prepared within 3 months) is submitted with a complete and updated set of supporting documents required for matching and placement, in accordance with RA 11642 standards. The SWA ensures prompt submission to RACCO and timely compliance with feedback, if any, including correction of insufficiencies or provision of status updates within 15 working days. For children with special needs, or children with disabilities, special home-finding efforts are conducted, and appropriate case updates are regularly submitted to RACCO/NACC. Required supporting documents: Authenticated or COLB in SECPA; Notarized Deed of Voluntary Commitment (DVC) and CANA; Written consent of the child (if 10 years or older); Death certificate of biological parents (if applicable); Certified true copy of CDCLAA; Medical certificate/health profile (issued within the last 6 months); Psychological evaluation (for children 5 years and older, issued within the last 2 years); Recent 5R (127x178mm) photos (close-up and whole-body, taken within the last 6 months with date).',
                "means": ["Complete set of documents in the child's case folder",
                 'Document checklist with dates of submission to RACCO',
                 'Proof of receipt of RACCO to the case of the child for presentation to the RMC',
                 "Copy of RACCO feedback/comments (if any) and SWA's resubmitted or corrected documents, with "
                 'date received',
                 'Status report from SWA (if submission within 15 working days is not feasible)',
                 'Evidence of Special Home Finding (SHF) efforts for children with specific needs (e.g., '
                 'updated CCSR, HMP, psychological evaluation reports, photos/videos submitted to RACCO/NACC)',
                 'Matching conference documentation, records of interregional matching attempts, and '
                 'pre-selection conference (if applicable)']
            },
            {
                "key": 'II.43',
                "number": 43,
                "section": 'Matching Process',
                "indicator": "The SWA ensures timely and active participation in the matching process. The SWA coordinates with RACCO for matching based on the child's best interest, needs, and the adoptive parents' capacity. If the child is not matched after two RCPC matching attempts, the RACCO facilitates endorsement for interregional matching through the CPC. If still unmatched after two interregional attempts (excluding cases under Special Home Finding), the SWA coordinates with RACCO/NACC for intercountry adoption clearance, including participation in a documented pre-selection conference.",
                "means": ['Complete case folder submitted to RACCO/NACC with CDCLAA',
                 'RCPC Matching Conference attendance sheet signed by the SWA representative',
                 'Copies of the Certificate of Matching',
                 'Documentation of two unsuccessful RCPC matching attempts',
                 'Endorsement and transmittal documents for interregional matching',
                 'Pre-selection conference notes or summary of discussions signed by the SWA RSW and '
                 'RACCO/NACC representative',
                 'Intercountry Adoption Clearance endorsement memo (if applicable)']
            },
            {
                "key": 'II.44',
                "number": 44,
                "section": 'Issuance of Pre-Adoptive Placement Authority (PAPA) and Entrustment/ Discharge',
                "indicator": "The RSW ensures that the SWA is promptly informed of the approved matching, and coordination is made for the child's entrustment within 15 working days from PAPA issuance. Pre-placement activities, including video conferencing, at least two consecutive visits, or a two-day stay with the child at the SWA, are conducted. The child's Lifebook, medical records, and other necessary documents are prepared and endorsed to the adoptive parents, along with a discharge slip.",
                "means": ['Notification letter/email to SWA, Acceptance letter from PAPs, copy of signed PAPA, '
                 'entrustment plan, Pre-placement activity log, documentation/photos of visits, copy of '
                 "discharge slip, child's medical records, daily routing, discharge summary"]
            },
            {
                "key": 'II.45',
                "number": 45,
                "section": 'Post-Adoption, Termination, and Closing of the Case',
                "indicator": "Post-placement monitoring reports are received, recorded/updated in the CLI, and compiled in the child's case folder.",
                "means": ['Copy of post-placement reports Proof of coordination or follow-up communication (e.g., email '
                 'or official letter) with the RACCO in cases where the said reports have not yet been '
                 'received by the SWA Updated CLI']
            },
            {
                "key": 'II.46',
                "number": 46,
                "section": 'Post-Adoption, Termination, and Closing of the Case',
                "indicator": 'Cases are formally closed after all necessary interventions, post-placement reports, final placement, or legal adoption completion.',
                "means": ['Copy of the Order of Adoption, Certificate of Finality, and PSA-issued new COLB of the child '
                 'NACC-issued',
                 'Closing Summary report prepared and filed in the case folders and archived securely.']
            },
            {
                "key": 'II.47',
                "number": 47,
                "section": 'Case Recording/ Documentation and Confidentiality',
                "indicator": 'Case folders are securely stored, with complete documents maintained in an organized, accessible, and confidential filing system.',
                "means": ['MOO, Confidentiality policies, storage verification (if applicable)']
            },
            {
                "key": 'II.48',
                "number": 48,
                "section": 'Case Recording/ Documentation and Confidentiality',
                "indicator": 'Accurate and regularly updated database or Caseload Inventory (CLI) of adopted children, including case statuses and essential child information, with access ensured for authorized personnel.',
                "means": ['Database reports, Caseload Inventory (CLI), access logs, and data integrity audit reports.']
            },
            {
                "key": 'II.49',
                "number": 49,
                "section": 'Case Recording/ Documentation and Confidentiality',
                "indicator": "Child Case Study Reports (CCSRs) and related case documents must comprehensively reflect the child's full background, including medical, developmental, psychological, and behavioral history. No critical information shall be intentionally omitted, especially those related to the child's health condition, trauma, or special needs, to ensure informed decision-making by the matching committee and prospective adoptive parents. The deliberate exclusion of such information constitutes unethical practice and compromises the best interest of the child, potentially resulting in adoption disruption. Individual case folders are maintained with General Intake Sheet, Admission Slip, Admission Agreement, CMIP, CCSR, COLB, DVC and CANA, Panawagan/Media certificates, Barangay or Police blotter reports, updated case recordings, home visit records, coordination reports, referral letters, health and medical records, school records, photos and life book, psychological evaluations, PCA/R, and CDCLAA.",
                "means": ['CCSR with consistent and complete attachments',
                 'Supporting medical, psychological, and development reports',
                 "Case conference notes and case manager's narrative assessments",
                 'Consent and disclosure documentation signed by prospective adoptive parents',
                 'Random file audits confirming data accuracy and completeness']
            },
            {
                "key": 'II.50',
                "number": 50,
                "section": 'Case Recording/ Documentation and Confidentiality',
                "indicator": 'There is a written policy and procedures/protocols for case disclosure and confidentiality agreement executed by and among concerned individuals/professionals managing the cases of children. Use of coding systems, specifically control or serial numbers, thereby ensuring that the names of children are kept confidential. Case folders/records are marked "Confidential" and are properly kept and maintained in a location that can be monitored easily and in designated cabinets marked with "for authorized personnel only".',
                "means": ['MOO/ Executed Confidentiality Agreement/Availability of a secured filing cabinet/storage for '
                 'case folders.']
            },
            {
                "key": 'II.51',
                "number": 51,
                "section": 'Case Recording/ Documentation and Confidentiality',
                "indicator": 'All adoption case folders must be preserved in perpetuity and shall not be discarded under any circumstances to protect the rights of adoptees to access their records in the future.',
                "means": ['Case folder retention policy, digital and physical archiving system.']
            },
        ],
    },
    {
        "key": "III",
        "title": 'Helping Strategies and Interventions',
        "items": [
            {
                "key": 'III.1',
                "number": 1,
                "section": 'Comprehensive, Child-Centered, and Trauma-Informed Interventions',
                "indicator": 'Social preparation plans and transition strategies for children moving to adoption, kinship care/foster care, family reunification, or independent living.',
                "means": ['Transition plans, child readiness assessments, inter-agency coordination records']
            },
            {
                "key": 'III.2',
                "number": 2,
                "section": 'Comprehensive, Child-Centered, and Trauma-Informed Interventions',
                "indicator": 'Use of child-centered and trauma-informed approaches based on individual care plans.',
                "means": ['Case conference reports, individualized CMIP, training manuals on trauma-informed care, '
                 'photo documentation, policy documents']
            },
            {
                "key": 'III.3',
                "number": 3,
                "section": 'Comprehensive, Child-Centered, and Trauma-Informed Interventions',
                "indicator": 'Active participation of children in care decisions appropriate to their age and maturity.',
                "means": ['Structured feedback sessions, consultation reports, signed consent forms (if applicable)']
            },
            {
                "key": 'III.4',
                "number": 4,
                "section": 'Comprehensive, Child-Centered, and Trauma-Informed Interventions',
                "indicator": "Programs and policies that respect children's cultural, religious, and familial background.",
                "means": ['Case notes, consent documentation']
            },
            {
                "key": 'III.5',
                "number": 5,
                "section": 'Education and Psychosocial Support',
                "indicator": "Enrollment in formal school, ALS, or SPED aligned with the child's developmental needs.",
                "means": ['School records, ALS/SPED documentation, attendance sheets']
            },
            {
                "key": 'III.6',
                "number": 6,
                "section": 'Education and Psychosocial Support',
                "indicator": 'Availability of educational support: tutorials, remedial classes, life skills, and learning tools.',
                "means": ['Learning development plans, tutorial logs, progress reports, inventory of materials']
            },
            {
                "key": 'III.7',
                "number": 7,
                "section": 'Education and Psychosocial Support',
                "indicator": 'Provision of psychosocial services: counseling, therapy, group activities.',
                "means": ['Counseling session logs, therapeutic intervention records, child feedback']
            },
            {
                "key": 'III.8',
                "number": 8,
                "section": 'Child Protection and Life Skills Development',
                "indicator": 'Implementation of a Child Protection Policy, including incident reporting and staff orientation.',
                "means": ['Signed policies, protocols, staff orientation records, incident reports']
            },
            {
                "key": 'III.9',
                "number": 9,
                "section": 'Child Protection and Life Skills Development',
                "indicator": 'Structured life skills and independent living programs for older children.',
                "means": ['Program modules, activity logs, MOAs with', 'TESDA/LGUs/NGOs, child evaluations']
            },
            {
                "key": 'III.10',
                "number": 10,
                "section": 'Child Protection and Life Skills Development',
                "indicator": 'Mechanisms to prevent abuse and exploitation within care settings.',
                "means": ['Monitoring logs, staff training on positive discipline, policy compliance audits']
            },
            {
                "key": 'III.11',
                "number": 11,
                "section": 'Child Protection and Life Skills Development',
                "indicator": 'Discipline practices emphasize self-regulation and social responsibility, not punitive measures.',
                "means": ['Documentation of behavioral support practices, staff orientation content']
            },
            {
                "key": 'III.12',
                "number": 12,
                "section": 'Health and Emergency Preparedness',
                "indicator": 'Regular health monitoring, immunizations, and referrals for medical needs.',
                "means": ['Health records, referral slips, immunization logs']
            },
            {
                "key": 'III.13',
                "number": 13,
                "section": 'Health and Emergency Preparedness',
                "indicator": 'Established hygiene, safety, and pandemic protocols within the facility.',
                "means": ['Hygiene assessment reports, daily logbooks, health policies']
            },
            {
                "key": 'III.14',
                "number": 14,
                "section": 'Health and Emergency Preparedness',
                "indicator": 'Functional emergency preparedness and crisis response mechanisms.',
                "means": ['Emergency drill logs, crisis intervention protocols, staff training reports']
            },
            {
                "key": 'III.15',
                "number": 15,
                "section": 'Monitoring, Evaluation, and Program Improvement',
                "indicator": 'Mechanisms are in place for tracking and evaluating the effectiveness of interventions, including documentation of outcomes such as improved well-being and stability.',
                "means": ['Evaluation reports, outcome/impact assessments, SWA-developed progress tracking tools or '
                 'templates, case outcome summaries.']
            },
            {
                "key": 'III.16',
                "number": 16,
                "section": 'Monitoring, Evaluation, and Program Improvement',
                "indicator": 'Documentation of gaps, challenges, and service enhancement actions.',
                "means": ['Service improvement reports, year-end evaluations, corrective action plans']
            },
            {
                "key": 'III.17',
                "number": 17,
                "section": 'Monitoring, Evaluation, and Program Improvement',
                "indicator": 'Use of feedback and assessment results to refine program implementation.',
                "means": ['Annual accomplishment reports, management reviews, stakeholder feedback']
            },
            {
                "key": 'III.18',
                "number": 18,
                "section": 'Staff Capacity Building and Development',
                "indicator": 'Regular training and capacity building of personnel on AACC, child protection, and trauma-informed care.',
                "means": ['Attendance sheets, post-activity evaluation reports, training certificates']
            },
            {
                "key": 'III.19',
                "number": 19,
                "section": 'Staff Capacity Building and Development',
                "indicator": 'Staff are updated on emerging child welfare practices and standards.',
                "means": ['Learning session documentation, updated staff development plans']
            },
            {
                "key": 'III.20',
                "number": 20,
                "section": 'Cultural and Community Engagement (Optional Thematic Area if applicable)',
                "indicator": "Respect and integration of cultural practices into the child's care and routine.",
                "means": ['Cultural orientation sessions, collaboration with community/cultural leaders']
            },
            {
                "key": 'III.21',
                "number": 21,
                "section": 'Cultural and Community Engagement (Optional Thematic Area if applicable)',
                "indicator": 'Community partnerships supporting reintegration or independent living.',
                "means": ['MOUs with community groups, transition support referrals, partnership activity records']
            },
        ],
    },
]


TOTAL_ITEMS = sum(len(kra["items"]) for kra in CHECKLIST)
ITEM_INDEX = {item["key"]: item for kra in CHECKLIST for item in kra["items"]}


def validate():
    """Sanity-check the static checklist against the official NACC-SAMD-GF-000 counts
    (KRA I=11, KRA II=51, KRA III=21, 83 total). Exercised by samd/tests/test_checklist.py
    and safe to call at import time in a management command if ever needed."""
    assert len(CHECKLIST) == 3, "expected exactly 3 KRAs"
    expected = {'I': 11, 'II': 51, 'III': 21}
    seen_keys = []
    for kra in CHECKLIST:
        items = kra["items"]
        assert len(items) == expected[kra["key"]], (kra["key"], len(items))
        numbers = [item["number"] for item in items]
        assert numbers == list(range(1, len(items) + 1)), (kra["key"], numbers)
        for item in items:
            assert item["key"] == f'{kra["key"]}.{item["number"]}'
            assert item["indicator"].strip(), item["key"]
            seen_keys.append(item["key"])
    assert len(seen_keys) == len(set(seen_keys)) == TOTAL_ITEMS == 83
    return True

