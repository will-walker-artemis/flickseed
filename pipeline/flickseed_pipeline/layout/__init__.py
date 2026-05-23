"""Layout: Vignelli grid placement for stations and lines.

Inputs: stations.json, curated lines.json, UMAP positions (hints only).

Constraints (PROJECT.md §7):
  - Each line follows a single angle (0, 45, 90, 135 degrees)
  - Stations on a line have uniform spacing
  - Transfer stations coincide between lines
  - Lines fan out, don't overlap
  - Districts (station clusters) stay roughly coherent

Approach: greedy. Place the longest line first along its preferred angle, anchor
each subsequent line at its transfer station and rotate, resolve collisions by
sliding along axis. Label positions are stored as per-station labelOffset values,
hand-placed (one hour by hand beats weeks of solver tuning).
"""
