# PPT outline (10 slides)

1. **Title** - Linux Process Tree Visualizer, Team 3 Section 9, member names
2. **Problem statement** - hierarchy of running processes, parent-child, real time
3. **Why it matters** - debugging, zombies/orphans, teaching process concepts
4. **OS concepts** - PID/PPID, fork/exec/wait, states, zombie, orphan, `/proc`
5. **System design** - diagram: /proc -> sampler -> cache -> API -> UI (use the one in docs/REPORT.md)
6. **Implementation** - stat parsing trick, CPU % formula, PID-reuse guard, diffing snapshots
7. **Technologies** - Python stdlib, vanilla JS, SVG, Git
8. **Features and screenshots** - tree list, graph, filter, detail panel, colours (add 2-3 screenshots)
9. **Testing and results** - the table from the report; mention 5 automated tests passing
10. **Impact, safety, future work + team roles** - who built what; Q and A
