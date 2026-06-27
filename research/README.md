# Topology Comparision Report

This folder is an Overleaf-ready LaTeX project.

Files:

- `main.tex`: report source.
- `references.bib`: bibliography entries used by the report.

To use it on Overleaf, upload the whole `research/` folder and set `main.tex`
as the main document.

Local build, if a LaTeX distribution is installed:

```bash
cd research
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

The report defines `No. links` as bidirectional physical router-router link
pairs. This differs from the repository benchmark `metrics.txt`, where `links`
counts directed router-router channels.
