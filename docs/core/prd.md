# Cecilia Clinic Supply Renewal

Cecilia scores annual clinic supply agreements and ranks which ones to work before term.

The book is community clinics, specialty clinics, and health systems. Each record is a clinic agreement: stocked cabinets, how many of those cabinets are actually ordering, named buyers, recent orders, service tickets, invoice failures, and days left on the term.

The lapse model is logistic regression trained on labeled history. The current book has no lapse label. The save desk multiplies lapse probability by contract value at risk and by how soon the term ends.

A clinic analysis adds prior notes, the supply playbooks, a reviewed action list, and a short report. A follow-up ticket is created only when someone asks for it.
