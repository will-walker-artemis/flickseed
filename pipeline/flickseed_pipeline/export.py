"""Export: assemble the final data/layout.json — the renderer contract.

This is the only thing the React app reads. Shape (to be finalised as the
upstream stages firm up):

    {
      "stations":  [{ id, name, x, y, films, lines, labelOffset, ... }],
      "lines":     [{ id, name, color, stations, angle, ... }],
      "districts": [{ id, hull, ... }]
    }
"""
