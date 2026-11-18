# Security policy

Open Books reads sensitive financial documents, so please report vulnerabilities privately and do not open a public issue.

Use GitHub's **private vulnerability reporting** on this repository (Security tab, "Report a vulnerability"). Include the version,
how to reproduce it and what you think the impact is. Do not attach real financial documents; a synthetic file that shows the
problem is enough.

We treat these as security issues: a tampered document that is released; a crash or resource exhaustion from a hostile file
(oversized inputs, archive or XML bombs, pathological PDFs); data left behind in temporary files; and anything that makes the
engine run code from a document or a model file.

Local use of the packages is on your own machine with your own files. If you run Open Books as a service for other people, you are
responsible for sandboxing it, limiting size and time per request, not logging document content, and isolating tenants.
